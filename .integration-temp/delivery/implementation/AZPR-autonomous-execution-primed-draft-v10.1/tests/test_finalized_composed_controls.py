from __future__ import annotations
import base64, hashlib, importlib.util, json, os, sqlite3, subprocess, sys, tempfile, unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

PACK=Path(__file__).resolve().parents[1]; TRUSTED=PACK/'trusted-controller'; sys.path.insert(0,str(TRUSTED))
import secure_runtime as sr
import evidence_registry as er
import trusted_installation as ti
from security_fixtures import keypair, write_external_fixture

def load_controller():
    spec=importlib.util.spec_from_file_location('azpr_controller_composed',TRUSTED/'controller.py'); assert spec and spec.loader
    module=importlib.util.module_from_spec(spec); sys.modules[spec.name]=module; spec.loader.exec_module(module); return module

def canonical(value): return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()

class FinalizedComposedControlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.controller=load_controller()

    def test_anchor_failure_never_releases_nonce_and_recovery_succeeds(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); private,public,_=keypair(root,'durable'); fail=root/'fail'; fail.write_text('1'); anchor=root/'anchor.py'; anchor_state=root/'anchor-state.json'
            anchor.write_text('#!/usr/bin/env python3\nimport json,os,sys\nfrom pathlib import Path\np=json.load(sys.stdin); fail=Path(os.environ["AZPR_TEST_FAIL_FILE"]); state=Path(os.environ["AZPR_TEST_ANCHOR_STATE"])\nif sys.argv[1]=="publish" and fail.exists(): sys.exit(3)\nif sys.argv[1]=="publish": state.write_text(json.dumps(p))\nif sys.argv[1]=="verify" and state.exists() and json.loads(state.read_text())!=p: sys.exit(4)\n')
            os.chmod(anchor,0o755)
            env={'AZPR_JOURNAL_ANCHOR_COMMAND':str(anchor),'AZPR_REQUIRE_JOURNAL_ANCHOR':'1','AZPR_TEST_FAIL_FILE':str(fail),'AZPR_TEST_ANCHOR_STATE':str(anchor_state)}
            # Anchor helper receives a minimal environment, so wrap fixed test paths into a launcher.
            wrapper=root/'anchor-wrapper.py'; wrapper.write_text(anchor.read_text().replace('os.environ["AZPR_TEST_FAIL_FILE"]',repr(str(fail))).replace('os.environ["AZPR_TEST_ANCHOR_STATE"]',repr(str(anchor_state)))); os.chmod(wrapper,0o755)
            with mock.patch.dict(os.environ,{'AZPR_JOURNAL_ANCHOR_COMMAND':str(wrapper),'AZPR_REQUIRE_JOURNAL_ANCHOR':'1'},clear=False):
                ledger=sr.NonceLedger(root/'runtime',private_key=private,public_key=public,key_id='durable')
                with self.assertRaises(sr.SecurityError): ledger.consume('q'*24,document_id='doc',purpose='apply',run_id='run-anchor-fail')
                with self.assertRaisesRegex(sr.SecurityError,'already consumed'):
                    ledger.consume('q'*24,document_id='other',purpose='apply',run_id='run-replay')
                fail.unlink(); self.assertEqual(ledger.consumed(),{'q'*24})
                conn=sqlite3.connect(ledger.store.path); self.assertEqual(conn.execute("SELECT COUNT(*) FROM event WHERE anchor_status='PENDING'").fetchone()[0],0); conn.close()

    def test_production_trust_root_ignores_caller_selected_git(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); attacker=root/'attacker-git'; attacker.write_text('#!/bin/sh\ntouch '+str(root/'owned')+'\n'); os.chmod(attacker,0o755)
            class Installed:
                production=True
                def component(self,name):
                    self.requested=name
                    return Path('/usr/bin/git')
            installed=Installed()
            with mock.patch.object(sr._ti,'load_installation',return_value=installed),mock.patch.dict(os.environ,{'AZPR_PRODUCTION_MODE':'1','AZPR_TRUSTED_GIT':str(attacker)},clear=False):
                self.assertEqual(sr.trusted_git_binary(),'/usr/bin/git'); self.assertEqual(installed.requested,'git_binary'); self.assertFalse((root/'owned').exists())

    def test_controller_output_is_bounded(self):
        with tempfile.TemporaryDirectory() as td, mock.patch.dict(os.environ,{'AZPR_DEV_CONTROLLER_STDOUT_LIMIT':'1024'},clear=False):
            with self.assertRaises(self.controller.ControllerError):
                self.controller.run_process([sys.executable,'-c','import sys;sys.stdout.write("x"*100000)'],cwd=Path(td),timeout_seconds=10)

    def test_operator_keygen_rejects_public_symlink(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); victim=root/'victim'; victim.write_text('unchanged'); public=root/'public.pem'; public.symlink_to(victim)
            tool=PACK/'operator-tools/generate_ed25519_keypair.py'; private=root/'private.pem'
            result=subprocess.run([sys.executable,str(tool),'--private-key',str(private),'--public-key',str(public)],capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0); self.assertEqual(victim.read_text(),'unchanged')

    def test_true_diff_budget_counts_deletion_and_binary_patch(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); subprocess.run(['/usr/bin/git','init','-q'],cwd=root,check=True); subprocess.run(['/usr/bin/git','config','user.email','t@azpr.local'],cwd=root,check=True); subprocess.run(['/usr/bin/git','config','user.name','T'],cwd=root,check=True)
            (root/'large.bin').write_bytes(os.urandom(65536)); subprocess.run(['/usr/bin/git','add','large.bin'],cwd=root,check=True); subprocess.run(['/usr/bin/git','commit','-qm','base'],cwd=root,check=True)
            (root/'large.bin').unlink()
            with self.assertRaises(sr.SecurityError): sr.git_diff_metrics(root,byte_limit=2048)
            metrics=sr.git_diff_metrics(root,byte_limit=200000); self.assertGreater(metrics['patch_bytes'],2048)

    def test_operation_evidence_exact_binding_matrix(self):
        fields=['stage_id','evidence_for_stage_id','environment','repository_id','source_commit','source_tree','plan_sha256','capability_manifest_sha256','target_attestation_sha256','target_sha256','operations_sha256','capability_nonce','controller_policy_identity_sha256']
        for field in fields:
            with self.subTest(field=field), tempfile.TemporaryDirectory() as td:
                root=Path(td); fixture=write_external_fixture(sr,PACK,root); journal_priv,journal_pub,_=keypair(root,'journal'); ev_priv,ev_pub,_=keypair(root,'ev')
                keyring=root/'evidence-keyring.json'; keyring.write_text(json.dumps({'format_version':'1.0','keys':[{'key_id':'ev','signer_id':'runner','roles':['external-evidence'],'public_key_pem':ev_pub.read_text()}]}))
                opreg=er.OperationRegistry(root/'operations',schema_path=PACK/'repository-overlay/automation/schemas/operation-registration.schema.json',journal_private_key=journal_priv,journal_public_key=journal_pub,journal_key_id='journal'); opreg.register(fixture['ticket'],run_id='register-12345678')
                t=fixture['ticket']; now=datetime.now(timezone.utc)
                payload={'format_version':'1.0','evidence_id':'evidence-matrix','operation_registration_id':t['registration_id'],'stage_id':t['stage_id'],'evidence_for_stage_id':t['evidence_for_stage_id'],'environment':t['environment'],'repository_id':t['repository_id'],'source_commit':t['source_commit'],'source_tree':t['source_tree'],'plan_sha256':t['plan_sha256'],'capability_manifest_sha256':t['capability_manifest_sha256'],'target_attestation_sha256':t['target_attestation_sha256'],'target_sha256':t['target_sha256'],'operations_sha256':t['operations_sha256'],'capability_nonce':t['capability_nonce'],'controller_policy_identity_sha256':t['controller_policy_identity_sha256'],'overall_status':'APPLY_COMPLETE','started_at':now.isoformat(),'completed_at':now.isoformat(),'target':fixture['target'],'adapter_results':[{'adapter':'mock','operation':'noop','status':'APPLIED','preflight_sha256':'4'*64,'result_sha256':'5'*64}],'rollback_ready':True,'output_hashes':{}}
                if field in {'stage_id','evidence_for_stage_id'}: payload[field]='036'
                elif field=='environment': payload[field]='production'
                elif field in {'source_commit','source_tree'}: payload[field]='f'*40
                elif field=='capability_nonce': payload[field]='x'*24
                elif field in {'repository_id'}: payload[field]='different-repository'
                else: payload[field]='f'*64
                signed=sr.sign_manifest(payload,private_key_path=ev_priv,key_id='ev'); path=root/'evidence.json'; path.write_text(json.dumps(signed))
                registry=er.EvidenceRegistry(root/'evidence-registry',schema_path=PACK/'repository-overlay/automation/schemas/evidence.schema.json',keyring_path=keyring,journal_private_key=journal_priv,journal_public_key=journal_pub,journal_key_id='journal',operation_registry=opreg)
                with self.assertRaises(sr.SecurityError): registry.ingest(path,required_roles=['external-evidence'],run_id='ingest-12345678',registration_id=t['registration_id'])

    def test_policy_identity_source_includes_evidence_roots(self):
        source=(TRUSTED/'controller.py').read_text()
        for token in ('evidence_keyring_sha256','schema_set_sha256','canonical_policy_record_sha256','governing_policy_source'):
            self.assertIn(token,source)

    def test_bundle_has_no_stale_placeholder_controller_config(self):
        self.assertFalse((PACK/'repository-overlay/automation/controller.config.refined.example.json').exists())
        source='\n'.join(p.read_text(errors='ignore') for p in [PACK/'operator-tools/generate_controller_config.py',PACK/'trusted-installation/install.py'])
        self.assertNotIn('/ABSOLUTE/TRUSTED/PATH',source)

if __name__=='__main__': unittest.main(verbosity=2)
