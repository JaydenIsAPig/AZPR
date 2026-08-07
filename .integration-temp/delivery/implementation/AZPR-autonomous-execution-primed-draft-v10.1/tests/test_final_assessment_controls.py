from __future__ import annotations

import base64
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

PACK = Path(__file__).resolve().parents[1]
TRUSTED = PACK / "trusted-controller"
sys.path.insert(0, str(TRUSTED))
import secure_runtime as sr  # noqa: E402
import evidence_registry as er  # noqa: E402
from security_fixtures import write_external_fixture


def load_controller():
    spec = importlib.util.spec_from_file_location("azpr_controller_final_draft", TRUSTED / "controller.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def keypair(directory: Path, name: str):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    private = Ed25519PrivateKey.generate()
    private_path = directory / f"{name}.private.pem"
    public_path = directory / f"{name}.public.pem"
    private_path.write_bytes(private.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    public_path.write_bytes(private.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo))
    os.chmod(private_path, 0o600)
    return private_path, public_path, private


def add_signature(payload: dict, key_id: str, private) -> dict:
    value = json.loads(json.dumps(payload))
    value.setdefault("signatures", [])
    unsigned = sr.unsigned_document(value)
    value["signatures"].append({
        "key_id": key_id,
        "ed25519": base64.b64encode(private.sign(sr.canonical_json_bytes(unsigned))).decode("ascii"),
    })
    return value


class FinalAssessmentControlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.controller = load_controller()

    def test_atomic_nonce_exactly_one_of_many_threads(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            private, public, _ = keypair(root, "journal")
            ledger = sr.NonceLedger(root / "runtime", private_key=private, public_key=public, key_id="journal")
            barrier = threading.Barrier(40)
            def consume(index: int) -> bool:
                barrier.wait()
                try:
                    ledger.consume("x" * 24, document_id=f"doc-{index}", purpose="race", run_id=f"run-{index:08d}")
                    return True
                except sr.SecurityError:
                    return False
            with ThreadPoolExecutor(max_workers=40) as pool:
                results = list(pool.map(consume, range(40)))
            self.assertEqual(sum(results), 1)
            self.assertEqual(ledger.consumed(), {"x" * 24})


    def test_atomic_nonce_exactly_one_of_many_processes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            private, public, _ = keypair(root, "journal-process")
            runtime = root / "runtime"
            # Initialize the database and journal before independent processes race.
            sr.NonceLedger(runtime, private_key=private, public_key=public, key_id="journal")
            start = root / "start"
            worker = root / "worker.py"
            worker.write_text(
                "import sys,time\n"
                "from pathlib import Path\n"
                f"sys.path.insert(0, {str(TRUSTED)!r})\n"
                "import secure_runtime as sr\n"
                "runtime,private,public,start,idx=map(Path,sys.argv[1:5])+[sys.argv[5]] if False else (Path(sys.argv[1]),Path(sys.argv[2]),Path(sys.argv[3]),Path(sys.argv[4]),sys.argv[5])\n"
                "while not start.exists(): time.sleep(0.002)\n"
                "ledger=sr.NonceLedger(runtime,private_key=private,public_key=public,key_id='journal')\n"
                "try:\n"
                " ledger.consume('p'*24,document_id='doc-'+idx,purpose='process-race',run_id='run-'+idx.zfill(8))\n"
                " print('OK')\n"
                "except sr.SecurityError:\n"
                " print('BLOCKED')\n"
            )
            processes = [subprocess.Popen([sys.executable, str(worker), str(runtime), str(private), str(public), str(start), str(i)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for i in range(20)]
            start.write_text("go")
            outputs = []
            for process in processes:
                stdout, stderr = process.communicate(timeout=30)
                self.assertEqual(process.returncode, 0, stderr)
                outputs.append(stdout.strip())
            self.assertEqual(outputs.count("OK"), 1)
            self.assertEqual(outputs.count("BLOCKED"), 19)

    def test_external_anchor_detects_signed_journal_rollback(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            private, public, _ = keypair(root, "anchor-journal")
            journal_path = root / "runtime" / "journal.jsonl"
            anchor_root = root / "anchors"
            helper = PACK / "operator-tools" / "file_anchor_reference.py"
            with mock.patch.dict(os.environ, {
                "AZPR_JOURNAL_ANCHOR_COMMAND": str(helper),
                "AZPR_REFERENCE_ANCHOR_ROOT": str(anchor_root),
                "AZPR_REQUIRE_JOURNAL_ANCHOR": "1",
            }, clear=False):
                journal = sr.SignedJournal(journal_path, signing_private_key_path=private, verification_public_key_path=public, signer_key_id="anchor")
                journal.append("ONE", {"value": 1}, run_id="run-anchor-0001")
                first = journal_path.read_text()
                journal.append("TWO", {"value": 2}, run_id="run-anchor-0002")
                self.assertEqual(len(journal.read_all()), 2)
                journal_path.write_text(first)
                with self.assertRaises(sr.SecurityError):
                    journal.read_all()

    def test_distinct_role_assignment_rejects_dual_role_shortcut(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _, dual_pub, dual_key = keypair(root, "dual")
            _, other_pub, other_key = keypair(root, "other")
            keyring_path = root / "keyring.json"
            keyring_path.write_text(json.dumps({"format_version":"1.0","keys":[
                {"key_id":"dual","signer_id":"alice","roles":["operator","security-approver"],"public_key_pem":dual_pub.read_text()},
                {"key_id":"other","signer_id":"bob","roles":["reviewer"],"public_key_pem":other_pub.read_text()}
            ]}))
            payload = add_signature({"document":"x","signatures":[]}, "dual", dual_key)
            payload = add_signature(payload, "other", other_key)
            with self.assertRaises(sr.SecurityError):
                sr.verify_signatures(payload, keyring=sr.load_public_keyring(keyring_path), required_key_ids=[], required_signer_ids=[], required_roles=["operator","security-approver"], min_signers=2)

    def test_approval_binding_has_no_self_hash_and_detects_policy_change(self):
        c = self.controller
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "automation/schemas").mkdir(parents=True)
            schema_src = PACK / "repository-overlay/automation/schemas/approval.schema.json"
            (root / "automation/schemas/approval.schema.json").write_bytes(schema_src.read_bytes())
            _, public, private = keypair(root, "approver")
            keyring = root / "keyring.json"
            keyring.write_text(json.dumps({"format_version":"1.0","keys":[{"key_id":"k1","signer_id":"alice","roles":["security-approver"],"public_key_pem":public.read_text()}]}))
            hashes = {f"policy-{i}": f"{i:064x}" for i in range(1, 9)}
            now = datetime.now(timezone.utc)
            decision={"account_id":None,"project_id":None,"region":None,"resources":[],"database_targets":[],"network_destinations":[],"recipient_cohort":{"cohort_id":None,"recipient_count":0,"recipient_hash":None},"limits":{"cost_ceiling_usd":0,"rate_per_minute":0,"max_operations":0},"activation_window":{"starts_at":None,"ends_at":None},"backup_rollback":{"backup_id":None,"rollback_plan_sha256":None,"kill_switch":None},"evidence_outputs":["run.json"]}
            approval={"format_version":"2.0","approval_id":"approval-123","approved":True,"stage_id":"005","target_commit":"a"*40,"controller_version":c.CONTROLLER_VERSION,"environment":"staging","approved_actions":["bootstrap"],"issued_at":(now-timedelta(minutes=1)).isoformat(),"expires_at":(now+timedelta(minutes=5)).isoformat(),"nonce":"n"*24,"bindings":{"policy_hashes":hashes,"plan_sha256":None,"capability_manifest_sha256":None,"target_attestation_sha256":None},"decision":decision,"signatures":[]}
            approval=add_signature(approval,"k1",private)
            approval_path=root/"approval.json"; approval_path.write_text(json.dumps(approval))
            stage={"id":"005","human_approval":{"required_before_run":True,"environment":"staging","required_actions":["bootstrap"],"required_key_ids":["k1"],"required_signer_ids":[],"required_signer_roles":["security-approver"],"min_approvals":1,"required_bindings":{},"decision_requirements":{}}}
            config={"approval_schema_path":"automation/schemas/approval.schema.json","approval_public_keyring_path":str(keyring)}
            verified,error=c.verify_approval_file(root,"approval.json",stage=stage,target_commit="a"*40,hashes=hashes,consumed_nonces=set(),config=config)
            self.assertIsNone(error); self.assertIsNotNone(verified)
            changed=dict(hashes); changed["policy-1"]="f"*64
            verified,error=c.verify_approval_file(root,"approval.json",stage=stage,target_commit="a"*40,hashes=changed,consumed_nonces=set(),config=config)
            self.assertIsNone(verified); self.assertIn("policy hash", error)
            self.assertNotIn("approval:approval.json", hashes)

    def test_secure_controller_write_rejects_symlink_ancestor(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/"repo"; outside=Path(td)/"outside"; root.mkdir(); outside.mkdir()
            os.symlink(outside, root/"docs")
            with self.assertRaises(sr.SecurityError):
                sr.secure_repo_write_bytes(root,"docs/audit.md",b"no")
            self.assertFalse((outside/"audit.md").exists())

    def test_hardened_git_rejects_host_code_configuration(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            subprocess.run(["/usr/bin/git","init","-q"],cwd=root,check=True)
            subprocess.run(["/usr/bin/git","config","core.hooksPath","hooks"],cwd=root,check=True)
            with self.assertRaises(sr.SecurityError):
                sr.secure_git_run(root,["status","--porcelain"])

    def test_state_binding_rejects_head_rollback(self):
        c=self.controller
        state={"policy_identity":{"x":"y"},"last_reconciled_commit":"a"*40,"last_reconciled_tree":"b"*40,"roadmap_sha256":"c"*64}
        identity={"x":"y","roadmap_sha256":"c"*64}
        with mock.patch.object(c,"repository_policy_identity",return_value=identity), mock.patch.object(c,"current_commit",return_value="d"*40), mock.patch.object(c,"current_tree",return_value="b"*40):
            with self.assertRaises(c.ControllerError):
                c.assert_state_repository_binding(Path("/tmp"),state,{}, {})

    def test_evidence_registry_is_signed_bound_and_create_once(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); fixture=write_external_fixture(sr,PACK,root)
            journal_private,journal_public,_=keypair(root,'journal')
            evidence_private,evidence_public,_=keypair(root,'ingest-evidence')
            keyring=root/'evidence-keyring.json'; keyring.write_text(json.dumps({'format_version':'1.0','keys':[{'key_id':'evidence','signer_id':'runner','roles':['external-evidence'],'public_key_pem':evidence_public.read_text()}]}))
            opreg=er.OperationRegistry(root/'operations',schema_path=PACK/'repository-overlay/automation/schemas/operation-registration.schema.json',journal_private_key=journal_private,journal_public_key=journal_public,journal_key_id='journal')
            opreg.register(fixture['ticket'],run_id='run-operation-register-123456')
            now=datetime.now(timezone.utc)
            ticket=fixture['ticket']
            payload={'format_version':'1.0','evidence_id':'evidence-123','operation_registration_id':ticket['registration_id'],'stage_id':ticket['stage_id'],
              'evidence_for_stage_id':ticket['evidence_for_stage_id'],'environment':ticket['environment'],'repository_id':ticket['repository_id'],
              'source_commit':ticket['source_commit'],'source_tree':ticket['source_tree'],'controller_policy_identity_sha256':ticket['controller_policy_identity_sha256'],
              'overall_status':'APPLY_COMPLETE','plan_sha256':ticket['plan_sha256'],'capability_manifest_sha256':ticket['capability_manifest_sha256'],
              'target_attestation_sha256':ticket['target_attestation_sha256'],'target_sha256':ticket['target_sha256'],'operations_sha256':ticket['operations_sha256'],
              'capability_nonce':ticket['capability_nonce'],'started_at':now.isoformat(),'completed_at':now.isoformat(),'target':fixture['target'],
              'adapter_results':[{'adapter':'mock','operation':'noop','status':'APPLIED','preflight_sha256':'4'*64,'result_sha256':'5'*64}],
              'rollback_ready':True,'output_hashes':{}}
            signed_payload=sr.sign_manifest(payload,private_key_path=evidence_private,key_id='evidence')
            evidence_file=root/'evidence.json'; evidence_file.write_text(json.dumps(signed_payload))
            registry=er.EvidenceRegistry(root/'registry',schema_path=PACK/'repository-overlay/automation/schemas/evidence.schema.json',keyring_path=keyring,
              journal_private_key=journal_private,journal_public_key=journal_public,journal_key_id='journal',operation_registry=opreg)
            envelope=registry.ingest(evidence_file,required_roles=['external-evidence'],run_id='run-evidence-123456789',registration_id=ticket['registration_id'])
            self.assertEqual(envelope['evidence_id'],'evidence-123'); self.assertEqual(registry.envelopes(['evidence-123'])[0]['overall_status'],'APPLY_COMPLETE')
            replay=registry.ingest(evidence_file,required_roles=['external-evidence'],run_id='run-evidence-replay',registration_id=ticket['registration_id'])
            self.assertEqual(replay['evidence_id'],'evidence-123')
            tampered=dict(signed_payload); tampered['repository_id']='other-repository'; tampered=sr.sign_manifest({k:v for k,v in tampered.items() if k not in {'signer_key_id','signature'}},private_key_path=evidence_private,key_id='evidence')
            bad=root/'bad-evidence.json'; bad.write_text(json.dumps(tampered))
            with self.assertRaises(sr.SecurityError): registry.ingest(bad,required_roles=['external-evidence'],run_id='run-evidence-bad',registration_id=ticket['registration_id'])


    def test_aggregate_diff_budget_includes_untracked_files(self):
        c = self.controller
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            subprocess.run(['/usr/bin/git','init','-q'],cwd=root,check=True)
            subprocess.run(['/usr/bin/git','config','user.email','test@example.invalid'],cwd=root,check=True)
            subprocess.run(['/usr/bin/git','config','user.name','AZPR Test'],cwd=root,check=True)
            (root/'baseline.txt').write_text('base')
            subprocess.run(['/usr/bin/git','add','baseline.txt'],cwd=root,check=True)
            subprocess.run(['/usr/bin/git','-c','core.hooksPath=/dev/null','commit','--no-verify','-qm','base'],cwd=root,check=True)
            (root/'src').mkdir()
            for index in range(3):
                (root/'src'/f'new-{index}.py').write_text('x')
            stage={'allowed_change_paths':['src/**'],'forbidden_change_paths':[],'path_scope_budget':2,'max_changed_bytes':1024}
            config={'global_forbidden_change_paths':[],'default_path_scope_budget':2,'default_max_changed_bytes':1024}
            with self.assertRaises(c.ControllerError):
                c.enforce_change_paths(root,config,stage,'stage','a'*40)

    def test_external_runner_rolled_back_is_non_success_terminal(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); fixture=write_external_fixture(sr,PACK,root,apply_status='ROLLED_BACK')
            evidence_dir=root/'evidence'; evidence_dir.mkdir()
            command=[sys.executable,str(fixture['runner']),'--installation-manifest',str(fixture['installation_path']),'--development-mode',
              '--plan',str(root/'plan.json'),'--manifest',str(root/'manifest.json'),'--target-attestation',str(root/'attestation.json'),
              '--operation-ticket',str(root/'ticket.json'),'--evidence-dir',str(evidence_dir),'--confirm','APPLY SIGNED AZPR CAPABILITY']
            completed=subprocess.run(command,capture_output=True,text=True,env={**os.environ,'AZPR_EXPLICIT_TEST_MODE':'1','AZPR_PRODUCTION_MODE':'0'})
            self.assertNotEqual(completed.returncode,0,completed.stderr+completed.stdout)
            files=list(evidence_dir.glob('*.json')); self.assertEqual(len(files),1)
            evidence=json.loads(files[0].read_text()); sr.verify_manifest(evidence,public_key_path=fixture['evidence_public'],key_id='evidence')
            self.assertEqual(evidence['overall_status'],'APPLY_ROLLED_BACK')


    def test_appendix_a_invented_authorization_id_does_not_pass(self):
        c=self.controller
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); auth_dir=root/"auth"; auth_dir.mkdir()
            (root/"docs/audits").mkdir(parents=True); report=root/"docs/audits/report.md"; report.write_text("audit")
            state={"pending_correction":{"audit_stage_id":"031","audit_report_file":"docs/audits/report.md","audit_commit":"b"*40,"audited_commit":"a"*40,"corrections":[{"correction_id":"c1"}]}}
            stage={"allowed_change_paths":["src/auth.py"],"_appendix_authorization_id":"invented"}
            config={"appendix_a_authorization_dir":str(auth_dir)}
            with self.assertRaises(c.ControllerError):
                c.verify_appendix_a_authorization(root,state,stage,{f"p{i}":str(i)*64 for i in range(1,9)},config)


if __name__ == "__main__":
    unittest.main(verbosity=2)
