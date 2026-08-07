from __future__ import annotations
import base64, importlib.util, json, os, sqlite3, subprocess, sys, tempfile, threading, time, unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

PACK=Path(__file__).resolve().parents[1]
TRUSTED=PACK/'trusted-controller'; VALIDATOR=PACK/'trusted-validation-runner'
sys.path.insert(0,str(PACK/'tests'));sys.path.insert(0,str(TRUSTED));sys.path.insert(0,str(VALIDATOR))
import secure_runtime as sr
import evidence_registry as er
import trusted_validation_runner as tvr
from security_fixtures import keypair, write_external_fixture

class V5SecurityClosureTests(unittest.TestCase):
    def test_all_schema_fragments_resolve_with_signed_fixtures(self):
        import jsonschema
        from referencing import Registry,Resource
        schemas={};registry=Registry();schema_dir=PACK/'repository-overlay/automation/schemas'
        for path in schema_dir.glob('*.json'):
            value=json.loads(path.read_text());jsonschema.Draft202012Validator.check_schema(value);schemas[path.name]=value;resource=Resource.from_contents(value);registry=registry.with_resource(path.name,resource)
            if isinstance(value.get('$id'),str):registry=registry.with_resource(value['$id'],resource)
        sig={'key_id':'owner-key','ed25519':'A'*88};now=datetime.now(timezone.utc).isoformat();h='a'*64
        fixtures={
          'canonical-policy-record.schema.json':{'format_version':'4.0','record_id':'policy-record-123456','source_document_name':'master.docx','source_document_sha256':h,'source_manifest_sha256':h,'canonical_policy_sha256':h,'section_map_sha256':h,'feature_inventory_sha256':h,'canonical_render_algorithm':'AZPR_DOCX_SUPPORTED_OOXML_UTF8_V3','source_unit_count':2,'mapped_source_unit_count':2,'canonical_byte_length':42,'completeness_statement':'EXACT_SUPPORTED_OOXML_RENDER_VERIFIED','unsupported_feature_count':0,'review_statement':'Every supported OOXML source byte span and feature inventory was independently reviewed.','approved_at':now,'expires_at':now,'signatures':[sig,dict(sig,key_id='security-key')]},
          'validation-image-attestation.schema.json':{'format_version':'1.0','attestation_id':'validation-image-123456','image_reference':'registry.invalid/azpr@sha256:'+h,'image_digest':'sha256:'+h,'dockerfile_sha256':h,'sbom_sha256':h,'build_provenance_sha256':h,'created_at':now,'signatures':[sig,dict(sig,key_id='security-key')]},
          'roadmap-regeneration-authorization.schema.json':{'format_version':'1.0','authorization_id':'roadmap-auth-123456','repository_id':'azpr-repository','target_commit':'b'*40,'target_tree':'c'*40,'prompt_004_status':'COMPLETED_APPROVED_RECONCILED','prompt_004_decision_path':'docs/prompt-004.json','prompt_004_decision_sha256':h,'prompt_catalog_sha256':h,'canonical_policy_record_sha256':h,'installation_manifest_sha256':h,'security_test_report_sha256':h,'issued_at':now,'expires_at':now,'nonce':'n'*24,'signatures':[sig,dict(sig,key_id='security-key')]}
        }
        for name,value in fixtures.items():
            with self.subTest(name=name):jsonschema.Draft202012Validator(schemas[name],registry=registry).validate(value)
        broken=dict(fixtures['canonical-policy-record.schema.json']);broken['signatures']=[{'key_id':'x','ed25519':'bad'},sig]
        with self.assertRaises(jsonschema.ValidationError):jsonschema.Draft202012Validator(schemas['canonical-policy-record.schema.json'],registry=registry).validate(broken)

    def test_duplicate_cryptographic_key_material_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);_priv,pub,_=keypair(root,'one')
            ring=root/'ring.json';ring.write_text(json.dumps({'format_version':'1.0','keys':[{'key_id':'k1','signer_id':'owner','roles':['policy-owner'],'public_key_pem':pub.read_text()},{'key_id':'k2','signer_id':'security','roles':['security-approver'],'public_key_pem':pub.read_text()}]}))
            with self.assertRaisesRegex(sr.SecurityError,'Duplicate Ed25519 public-key material'):sr.load_public_keyring(ring)

    def test_anchor_concurrency_acknowledges_each_exact_head(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);priv,pub,_=keypair(root,'journal');store=sr.DurableEventStore(root/'events.sqlite3',private_key=priv,public_key=pub,key_id='journal',store_id='concurrency-test')
            first_publish=threading.Event();release=threading.Event();published=[];errors=[]
            def anchor(operation,payload):
                if operation=='publish':
                    published.append(payload['sequence'])
                    if payload['sequence']==1:first_publish.set();release.wait(10)
                return {'operation':operation,'journal_id':payload['journal_id'],'sequence':payload['sequence'],'head_sha256':payload['head_sha256']}
            def append(index):
                try:store.append('TEST',{'index':index},run_id=f'run-{index:08d}')
                except Exception as exc:errors.append(exc)
            with mock.patch.object(sr,'_invoke_anchor',side_effect=anchor):
                t1=threading.Thread(target=append,args=(1,));t1.start();self.assertTrue(first_publish.wait(5))
                t2=threading.Thread(target=append,args=(2,));t2.start()
                deadline=time.time()+5
                while time.time()<deadline:
                    c=sqlite3.connect(store.path);count=c.execute('SELECT COUNT(*) FROM event').fetchone()[0];c.close()
                    if count==2:break
                    time.sleep(.02)
                self.assertEqual(count,2);release.set();t1.join(10);t2.join(10)
                self.assertFalse(errors)
                c=sqlite3.connect(store.path);rows=c.execute('SELECT seq,anchor_status,anchor_receipt_json FROM event ORDER BY seq').fetchall();c.close()
                self.assertEqual([r[1] for r in rows],['ANCHORED','ANCHORED']);self.assertEqual(json.loads(rows[0][2])['sequence'],1);self.assertEqual(json.loads(rows[1][2])['sequence'],2);self.assertEqual(published,[1,2])

    def test_evidence_commit_interruption_resumes_without_reapply(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);fixture=write_external_fixture(sr,PACK,root);jpriv,jpub,_=keypair(root,'journal');epriv,epub,_=keypair(root,'evidence')
            ring=root/'ring.json';ring.write_text(json.dumps({'format_version':'1.0','keys':[{'key_id':'evidence','signer_id':'runner','roles':['external-evidence'],'public_key_pem':epub.read_text()}]}))
            op=er.OperationRegistry(root/'operations',schema_path=PACK/'repository-overlay/automation/schemas/operation-registration.schema.json',journal_private_key=jpriv,journal_public_key=jpub,journal_key_id='journal');op.register(fixture['ticket'],run_id='register-operation-123456')
            t=fixture['ticket'];now=datetime.now(timezone.utc).isoformat();payload={'format_version':'1.0','evidence_id':'evidence-resume','operation_registration_id':t['registration_id'],'stage_id':t['stage_id'],'evidence_for_stage_id':t['evidence_for_stage_id'],'environment':t['environment'],'repository_id':t['repository_id'],'source_commit':t['source_commit'],'source_tree':t['source_tree'],'controller_policy_identity_sha256':t['controller_policy_identity_sha256'],'overall_status':'APPLY_COMPLETE','plan_sha256':t['plan_sha256'],'capability_manifest_sha256':t['capability_manifest_sha256'],'target_attestation_sha256':t['target_attestation_sha256'],'target_sha256':t['target_sha256'],'operations_sha256':t['operations_sha256'],'capability_nonce':t['capability_nonce'],'started_at':now,'completed_at':now,'target':fixture['target'],'adapter_results':[{'adapter':'mock','operation':'noop','status':'APPLIED','preflight_sha256':'4'*64,'result_sha256':'5'*64}],'rollback_ready':True,'output_hashes':{}}
            signed=sr.sign_manifest(payload,private_key_path=epriv,key_id='evidence');path=root/'evidence.json';path.write_text(json.dumps(signed));registry=er.EvidenceRegistry(root/'registry',schema_path=PACK/'repository-overlay/automation/schemas/evidence.schema.json',keyring_path=ring,journal_private_key=jpriv,journal_public_key=jpub,journal_key_id='journal',operation_registry=op)
            original=op.attach_evidence_atomic
            def commit_then_interrupt(*args,**kwargs):original(*args,**kwargs);raise RuntimeError('simulated process interruption after commit')
            with mock.patch.object(op,'attach_evidence_atomic',side_effect=commit_then_interrupt):
                with self.assertRaisesRegex(RuntimeError,'interruption'):registry.ingest(path,required_roles=['external-evidence'],run_id='ingest-first-123456',registration_id=t['registration_id'])
            recovered=registry.ingest(path,required_roles=['external-evidence'],run_id='ingest-retry-123456',registration_id=t['registration_id'])
            self.assertTrue(recovered['idempotent_recovery']);self.assertEqual(op.get(t['registration_id'])['_registry_status'],'EVIDENCE_ATTACHED')

    def test_validation_identity_is_the_captured_snapshot_not_later_head(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/'repo';root.mkdir();subprocess.run(['/usr/bin/git','init','-q'],cwd=root,check=True);subprocess.run(['/usr/bin/git','config','user.email','test@azpr.invalid'],cwd=root,check=True);subprocess.run(['/usr/bin/git','config','user.name','AZPR'],cwd=root,check=True)
            (root/'a.txt').write_text('A');subprocess.run(['/usr/bin/git','add','.'],cwd=root,check=True);subprocess.run(['/usr/bin/git','commit','-qm','A'],cwd=root,check=True);commit_a=subprocess.check_output(['/usr/bin/git','rev-parse','HEAD'],cwd=root,text=True).strip();tree_a=subprocess.check_output(['/usr/bin/git','rev-parse','HEAD^{tree}'],cwd=root,text=True).strip()
            dest=Path(td)/'snapshot';dest.mkdir();identity=tvr.snapshot_repository(root,dest,include_identity=True)
            (root/'a.txt').write_text('B');subprocess.run(['/usr/bin/git','add','.'],cwd=root,check=True);subprocess.run(['/usr/bin/git','commit','-qm','B'],cwd=root,check=True)
            self.assertEqual(identity['source_commit'],commit_a);self.assertEqual(identity['source_tree'],tree_a);self.assertEqual((dest/'a.txt').read_text(),'A')

    def test_production_agent_execution_is_pinned_and_nonroot(self):
        controller=(PACK/'trusted-controller/controller.py').read_text();installer=(PACK/'trusted-installation/install.py').read_text();loader=(PACK/'trusted-controller/trusted_installation.py').read_text()
        self.assertIn('component("codex_binary")',controller);self.assertNotIn('shutil.which("codex")',controller);self.assertIn('run_as_uid=agent_uid',controller);self.assertIn("'agent_uid'",loader);self.assertIn("'codex_binary'",loader);self.assertIn('agent UID/GID must be explicit non-root values',installer)

    def test_installer_authenticates_before_writing_and_activates_generation_atomically(self):
        source=(PACK/'trusted-installation/install.py').read_text();auth=source.index('bundle=authenticate_bundle');create=source.index("GENERATIONS.mkdir");activate=source.index('atomic_activate(lock)')
        self.assertLess(auth,create);self.assertLess(create,activate);self.assertIn("set(actual)!=expected",source);self.assertIn("os.replace(staging,final)",source);self.assertIn("os.replace(tmp,ACTIVE_LOCK)",source);self.assertIn("bundle_attestation",source)


    def test_installer_rejects_mutable_or_manifest_mismatched_bundle_source(self):
        import importlib.util
        spec=importlib.util.spec_from_file_location('azpr_installer_v5',PACK/'trusted-installation/install.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        fixture=PACK/'tests/fixtures/root-owned-bundle-auth';bundle=fixture/'release'
        att_path=fixture/'attestation.json';pub_path=fixture/'release-signing.pub.pem'
        original_lstat=module.os.lstat; mutable=(bundle/'controller.py').absolute()
        def trusted_metadata(path, *, mutable_controller=False):
            info=original_lstat(path);values=list(info)
            values[0]=info.st_mode & ~0o022;values[4]=0;values[5]=0
            if mutable_controller and Path(path).absolute()==mutable: values[0]|=0o022
            return os.stat_result(values)
        with mock.patch.object(module.os,'lstat',side_effect=lambda path:trusted_metadata(path)):
            authenticated=module.authenticate_bundle(str(bundle),att_path,pub_path,'release-key')
            self.assertEqual(authenticated.read('controller.py'),b'trusted-controller-bytes');authenticated.close()
        with mock.patch.object(module.os,'lstat',side_effect=lambda path:trusted_metadata(path,mutable_controller=True)):
            with self.assertRaises(SystemExit):module.authenticate_bundle(str(bundle),att_path,pub_path,'release-key')

    def test_direct_source_entrypoints_fail_closed(self):
        controller=subprocess.run([sys.executable,str(PACK/'trusted-controller/controller.py'),'status'],cwd=PACK,capture_output=True,text=True,env={**os.environ,'AZPR_PRODUCTION_MODE':'0'})
        self.assertNotEqual(controller.returncode,0);self.assertIn('Direct source-tree controller CLI execution is disabled',controller.stderr)
        runner=subprocess.run([sys.executable,str(PACK/'external-capability-runner/capability_runner.py'),'--help'],cwd=PACK,capture_output=True,text=True,env={**os.environ,'AZPR_PRODUCTION_MODE':'0'})
        self.assertNotEqual(runner.returncode,0)

    def test_supply_chain_uses_signed_offline_mirror_and_reproducible_resolution(self):
        source=(PACK/'operator-tools/build_supply_chain_bundle.py').read_text()
        for token in ('--offline-mirror','--mirror-attestation','--mirror-public-key','--no-index','PIP_NO_INDEX','dependency resolution is not reproducible','resolution_passes','reproducible'):
            self.assertIn(token,source)

if __name__=='__main__':unittest.main(verbosity=2)
