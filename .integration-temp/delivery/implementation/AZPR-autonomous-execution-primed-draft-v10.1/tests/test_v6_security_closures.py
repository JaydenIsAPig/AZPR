from __future__ import annotations
import hashlib, importlib.util, io, json, os, subprocess, sys, tempfile, unittest, zipfile
from pathlib import Path
from unittest import mock

PACK=Path(__file__).resolve().parents[1]
TRUSTED=PACK/'trusted-controller'; VALIDATOR=PACK/'trusted-validation-runner'; EXTERNAL=PACK/'external-capability-runner'
sys.path.insert(0,str(TRUSTED));sys.path.insert(0,str(VALIDATOR));sys.path.insert(0,str(EXTERNAL))
import secure_runtime as sr
import trusted_validation_runner as tvr


def load_module(name:str,path:Path):
    spec=importlib.util.spec_from_file_location(name,path);assert spec and spec.loader
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module);return module

installer=load_module('azpr_v6_installer',PACK/'trusted-installation/install.py')
capability_runner=load_module('azpr_v6_capability_runner',EXTERNAL/'capability_runner.py')


def init_repo(root:Path)->None:
    subprocess.run(['/usr/bin/git','init','-q'],cwd=root,check=True)
    subprocess.run(['/usr/bin/git','config','user.email','security@azpr.invalid'],cwd=root,check=True)
    subprocess.run(['/usr/bin/git','config','user.name','AZPR Security'],cwd=root,check=True)
    (root/'allowed.txt').write_text('base\n')
    subprocess.run(['/usr/bin/git','add','allowed.txt'],cwd=root,check=True)
    subprocess.run(['/usr/bin/git','commit','-qm','base'],cwd=root,check=True)


def make_docx(paragraphs:list[str])->bytes:
    body=''.join(f'<w:p><w:r><w:t>{text}</w:t></w:r></w:p>' for text in paragraphs)
    xml=('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
         '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
         f'<w:body>{body}</w:body></w:document>').encode()
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w') as z:z.writestr('word/document.xml',xml)
    return out.getvalue()


class V6SecurityClosureTests(unittest.TestCase):
    def test_git_info_exclude_cannot_hide_persistent_agent_file(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);init_repo(root)
            (root/'allowed.txt').write_text('changed\n');(root/'hidden.py').write_text('print("persistent")\n')
            (root/'.git/info/exclude').write_text('hidden.py\n')
            complete=sr.complete_worktree_paths(root)
            validator=tvr._worktree_paths(root)
            metrics=sr.git_diff_metrics(root,byte_limit=1024*1024)
            self.assertIn('hidden.py',complete);self.assertIn('hidden.py',validator)
            self.assertGreaterEqual(metrics['untracked_bytes'],len((root/'hidden.py').read_bytes())+len('hidden.py')+1)
            subprocess.run(['/usr/bin/git','clean','-fd'],cwd=root,check=True,stdout=subprocess.PIPE)
            self.assertTrue((root/'hidden.py').exists(),'reproduces why legacy git clean -fd was unsafe')
            subprocess.run(['/usr/bin/git','clean','-ffdx'],cwd=root,check=True,stdout=subprocess.PIPE)
            self.assertFalse((root/'hidden.py').exists())

    def test_git_metadata_inventory_detects_exclude_and_config_mutation(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);init_repo(root);before=sr.git_metadata_inventory(root)
            (root/'.git/info/exclude').write_text('hidden.py\n')
            with self.assertRaises(sr.SecurityError):sr.verify_git_metadata_inventory(root,before)
            after=sr.git_metadata_inventory(root)
            subprocess.run(['/usr/bin/git','config','core.excludesFile',str(root/'global-ignore')],cwd=root,check=True)
            with self.assertRaises(sr.SecurityError):sr.verify_git_metadata_inventory(root,after)

    def test_git_metadata_write_access_is_rejected_for_agent_identity(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);init_repo(root)
            # Deliberately expose one administrative file to the configured non-root identity.
            os.chmod(root/'.git/info/exclude',0o666)
            with self.assertRaises(sr.SecurityError):
                sr.assert_git_metadata_protected(root,agent_uid=65534,agent_gid=65534,owner_uid=os.geteuid())

    def test_private_key_validator_rejects_readable_modes_and_proves_agent_denial(self):
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);key=root/'runtime.pem'
            raw=Ed25519PrivateKey.generate().private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption())
            key.write_bytes(raw)
            original_lstat=installer.os.lstat
            def trusted_parent(path):
                info=original_lstat(path)
                if Path(path)==root:
                    values=list(info);values[4]=0;values[0]=(info.st_mode & ~0o077);return os.stat_result(values)
                return info
            with mock.patch.object(installer,'safe_external',return_value=key), mock.patch.object(installer.os,'lstat',side_effect=trusted_parent), mock.patch.object(installer,'prove_identity_denied') as denied:
                os.chmod(key,0o644)
                with self.assertRaises(SystemExit):installer.safe_secret(str(key),'runtime',agent_uid=65534,agent_gid=65534)
                os.chmod(key,0o640)
                with self.assertRaises(SystemExit):installer.safe_secret(str(key),'runtime',agent_uid=65534,agent_gid=65534)
                os.chmod(key,0o600)
                self.assertEqual(installer.safe_secret(str(key),'runtime',agent_uid=65534,agent_gid=65534),key)
                denied.assert_called_once_with(key,65534,65534,read=True,label='runtime')
            source=(PACK/'trusted-installation/install.py').read_text()
            self.assertIn("agent-identity access proof requires root",source)
            for token in ('os.setgroups([])','os.setgid(gid)','os.setuid(uid)'):self.assertIn(token,source)

    def test_private_public_key_pair_mismatch_fails_before_installation(self):
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);a=Ed25519PrivateKey.generate();b=Ed25519PrivateKey.generate()
            priv=root/'private.pem';pub=root/'public.pem'
            priv.write_bytes(a.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
            pub.write_bytes(b.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo))
            with self.assertRaises(SystemExit):installer.verify_key_pair(priv,pub,'test')

    def test_exact_docx_render_rejects_truncated_contradictory_policy(self):
        raw=make_docx(['Do not authorize autonomous execution.','Require independent security review.'])
        manifest,canonical,section=sr.derive_docx_lossless_policy(raw,'master.docx')
        manifest_raw=(json.dumps(manifest,indent=2,sort_keys=True)+'\n').encode()
        section['source_manifest_sha256']=hashlib.sha256(manifest_raw).hexdigest()
        sr.verify_lossless_canonical_policy(raw,'master.docx',manifest,canonical,section,source_manifest_sha256=hashlib.sha256(manifest_raw).hexdigest())
        with self.assertRaises(sr.SecurityError):
            sr.verify_lossless_canonical_policy(raw,'master.docx',manifest,b'ALLOW EVERY ACTION WITHOUT RESTRICTION.\n',section,source_manifest_sha256=hashlib.sha256(manifest_raw).hexdigest())
        mutated=bytearray(canonical);mutated[0]^=1
        with self.assertRaises(sr.SecurityError):
            sr.verify_lossless_canonical_policy(raw,'master.docx',manifest,bytes(mutated),section,source_manifest_sha256=hashlib.sha256(manifest_raw).hexdigest())

    def test_supply_chain_attestation_is_bound_to_exact_files(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);wheelhouse=root/'wheelhouse';wheelhouse.mkdir()
            files={name:root/name for name in ['requirements.in','requirements.lock','mirror-inventory.json','mirror-attestation.json','mirror-key.pem','sbom.json','provenance.json','Dockerfile','image-attestation.json']}
            files['requirements.in'].write_text('cryptography\n');files['requirements.lock'].write_text('locked\n');files['mirror-key.pem'].write_text('key\n');files['Dockerfile'].write_text('FROM scratch\n')
            wheel={'filename':'cryptography-1-py3-none-any.whl','sha256':'1'*64,'name':'cryptography','version':'1','size':123}
            mirror_files=[{'path':'wheels/'+wheel['filename'],'sha256':wheel['sha256'],'size':wheel['size']}]
            inventory_hash=hashlib.sha256(installer.canonical(mirror_files)).hexdigest()
            mirror={'format_version':'1.0','mirror_name':'approved','inventory_sha256':inventory_hash,'file_count':1,'total_bytes':123,'files':mirror_files}
            files['mirror-inventory.json'].write_text(json.dumps(mirror))
            mirror_att={'format_version':'1.0','mirror_name':'approved','inventory_sha256':inventory_hash,'file_count':1,'total_bytes':123,'created_at':'2026-01-01T00:00:00+00:00','signer_key_id':'mirror','signature':'A'*88}
            files['mirror-attestation.json'].write_text(json.dumps(mirror_att))
            sbom={'components':[{'name':'cryptography','version':'1','hashes':[{'alg':'SHA-256','content':wheel['sha256']}],'properties':[{'name':'azpr:wheel','value':wheel['filename']}]}]}
            files['sbom.json'].write_text(json.dumps(sbom))
            def digest(path):return installer.sha(path)
            wheel_set=hashlib.sha256(installer.canonical([wheel])).hexdigest()
            provenance={'format_version':'2.0','created_at':'2026-01-01T00:00:00+00:00','builder':{'python_path':sys.executable,'python_sha256':digest(Path(sys.executable)),'python_version':'3','pip_version':'pip'},'requirements_input_sha256':digest(files['requirements.in']),'dependency_lock_sha256':digest(files['requirements.lock']),'mirror':{'name':'approved','inventory_sha256':inventory_hash,'attestation_sha256':digest(files['mirror-attestation.json']),'public_key_sha256':digest(files['mirror-key.pem']),'signer_key_id':'mirror','file_count':1},'resolution_passes':[{'index':1,'command':['resolve'],'wheel_set_sha256':wheel_set},{'index':2,'command':['resolve'],'wheel_set_sha256':wheel_set}],'reproducible':True,'wheels':[wheel]}
            files['provenance.json'].write_text(json.dumps(provenance))
            image_digest='sha256:'+'2'*64
            att={'format_version':'1.0','attestation_id':'attestation-123456','image_reference':'example@'+image_digest,'image_digest':image_digest,'dockerfile_sha256':digest(files['Dockerfile']),'sbom_sha256':digest(files['sbom.json']),'build_provenance_sha256':digest(files['provenance.json']),'created_at':'2026-01-01T00:00:00+00:00','signatures':[]}
            files['image-attestation.json'].write_text(json.dumps(att))
            external={'requirements_input':files['requirements.in'],'dependency_lock':files['requirements.lock'],'dependency_mirror_inventory':files['mirror-inventory.json'],'dependency_mirror_attestation':files['mirror-attestation.json'],'dependency_mirror_public_key':files['mirror-key.pem'],'sbom':files['sbom.json'],'build_provenance':files['provenance.json'],'validation_dockerfile':files['Dockerfile'],'validation_image_attestation':files['image-attestation.json'],'python_binary':Path(sys.executable)}
            with mock.patch.object(installer,'validate_schema'),mock.patch.object(installer,'verify_detached_signature'),mock.patch.object(installer,'verified_wheel_inventory',return_value=[wheel]):
                identity=installer.verify_supply_chain({},None,external,wheelhouse,image_digest)
                self.assertEqual(identity['sbom_sha256'],digest(files['sbom.json']))
                files['sbom.json'].write_text(json.dumps({'components':[]}))
                with self.assertRaises(SystemExit):installer.verify_supply_chain({},None,external,wheelhouse,image_digest)

    def test_production_runner_adapter_uses_manifest_component_not_config_path(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);approved=root/'approved.py';attacker=root/'attacker.py';approved.write_text('approved');attacker.write_text('attacker')
            os.chmod(approved,0o555);os.chmod(attacker,0o555)
            digest=hashlib.sha256(approved.read_bytes()).hexdigest();manifest=root/'adapter-manifest.json'
            manifest.write_text(json.dumps({'format_version':'1.0','adapter_name':'adapter','executable_component':'approved_adapter','executable_sha256':digest,'allowed_operations':['noop'],'execution_mode':'DRY_RUN_ONLY','idempotency_key_required':True,'max_request_bytes':1048576,'max_response_bytes':1048576,'rollback_semantics':'NO_SIDE_EFFECT_NOOP'}));manifest.chmod(0o444)
            class Trusted:
                def component(self,name):
                    self.requested=name;return {'approved_adapter':approved,'adapter_manifest':manifest}[name]
            trusted=Trusted();config={'adapters':[{'name':'adapter','component':'approved_adapter','manifest_component':'adapter_manifest','sha256':digest,'allowed_operations':['noop']}]}
            with mock.patch.object(capability_runner.ti,'production_mode',return_value=True):
                catalog=capability_runner.adapter_catalog(config,development_mode=False,trusted=trusted)
            try:
                self.assertEqual(trusted.requested,'adapter_manifest');self.assertEqual(catalog['adapter']['path'],str(approved));self.assertEqual(catalog['adapter']['installation_manifest']['execution_mode'],'DRY_RUN_ONLY')
            finally:capability_runner.close_catalog(catalog)

    def test_activation_recovery_finalizes_pending_receipt(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);etc=root/'etc';receipts=etc/'receipts';generations=root/'generations';var=root/'var';handoff_base=root/'handoff'
            etc.mkdir();receipts.mkdir();generations.mkdir();handoff_base.mkdir();(var/'secure').mkdir(parents=True);(var/'runtime').mkdir()
            generation=generations/'generation';generation.mkdir();handoff=(handoff_base/'generation');handoff.mkdir()
            active=etc/'active.json';state_path=etc/'state.json';pending=receipts/'pending.json';final=receipts/'final.json'
            lock={'installation_id':'x','manifest_sha256':'a'*64};active.write_text(json.dumps(lock,indent=2,sort_keys=True)+'\n');pending.write_text('{}\n')
            state={'new_lock_sha256':installer.sha(active),'previous_lock_sha256':None,'pending_receipt_path':str(pending),'final_receipt_path':str(final),'generation_path':str(generation),'staging_path':str(generations/'staging'),'secure_path':str(var/'secure'/'generation'),'runtime_path':str(var/'runtime'/'generation'),'agent_handoff_path':str(handoff)}
            state_path.write_text(json.dumps(state))
            with mock.patch.object(installer,'ETC',etc),mock.patch.object(installer,'ACTIVE_LOCK',active),mock.patch.object(installer,'ACTIVATION_STATE',state_path),mock.patch.object(installer,'RECEIPTS',receipts),mock.patch.object(installer,'GENERATIONS',generations),mock.patch.object(installer,'VAR',var),mock.patch.object(installer,'AGENT_HANDOFF_BASE',handoff_base),mock.patch.object(installer.os,'chown') as chown:
                self.assertEqual(installer.recover_activation_state(),'COMPLETED_ACTIVE_GENERATION')
                chown.assert_called_once_with(final,0,0)
            self.assertTrue(final.exists());self.assertFalse(pending.exists());self.assertFalse(state_path.exists())

    def test_activation_recovery_rejects_path_escape(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);etc=root/'etc';receipts=etc/'receipts';generations=root/'generations';var=root/'var';etc.mkdir();receipts.mkdir();generations.mkdir();(var/'secure').mkdir(parents=True);(var/'runtime').mkdir()
            active=etc/'active.json';state_path=etc/'state.json';victim=root/'victim';victim.mkdir();(victim/'keep').write_text('safe')
            active.write_text('{}\n')
            state={'new_lock_sha256':'0'*64,'previous_lock_sha256':installer.sha(active),'pending_receipt_path':str(receipts/'pending.json'),'final_receipt_path':str(receipts/'final.json'),'generation_path':str(victim),'staging_path':str(generations/'stage'),'secure_path':str(var/'secure'/'x'),'runtime_path':str(var/'runtime'/'x')}
            state_path.write_text(json.dumps(state))
            with mock.patch.object(installer,'ETC',etc),mock.patch.object(installer,'ACTIVE_LOCK',active),mock.patch.object(installer,'ACTIVATION_STATE',state_path),mock.patch.object(installer,'RECEIPTS',receipts),mock.patch.object(installer,'GENERATIONS',generations),mock.patch.object(installer,'VAR',var):
                with self.assertRaises(SystemExit):installer.recover_activation_state()
            self.assertTrue((victim/'keep').exists())

    def test_mutation_oracle_detects_removed_ignore_independent_inventory(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);init_repo(root);(root/'hidden.py').write_text('x');(root/'.git/info/exclude').write_text('hidden.py\n')
            independent={'hidden.py'}
            with mock.patch.object(sr,'filesystem_worktree_paths',return_value=[]):
                mutated=set(sr.complete_worktree_paths(root))
            self.assertNotEqual(independent & mutated,independent,'mutation oracle catches removal of filesystem inventory')


if __name__=='__main__':unittest.main(verbosity=2)
