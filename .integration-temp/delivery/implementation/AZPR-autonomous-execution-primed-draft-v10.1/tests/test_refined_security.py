from __future__ import annotations

import base64
import importlib.util
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

PACK = Path(__file__).resolve().parents[1]
TRUSTED = PACK / 'trusted-controller'
sys.path.insert(0, str(TRUSTED))
import secure_runtime as sr  # noqa: E402
from security_fixtures import write_external_fixture


def load_controller():
    spec = importlib.util.spec_from_file_location("azpr_controller_refined", TRUSTED / 'controller.py')
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
    os.chmod(public_path, 0o644)
    return private_path, public_path, private


def signed(payload: dict, key_id: str, private) -> dict:
    value = dict(payload)
    value.setdefault("signatures", [])
    unsigned = sr.unsigned_document(value)
    sig = private.sign(sr.canonical_json_bytes(unsigned))
    value["signatures"].append({"key_id": key_id, "ed25519": base64.b64encode(sig).decode("ascii")})
    return value


class SecureRuntimeTests(unittest.TestCase):
    def test_minimal_child_environment_drops_parent_secrets(self):
        os.environ["AZPR_APPROVAL_KEYS_JSON"] = "secret"
        os.environ["AWS_SECRET_ACCESS_KEY"] = "secret"
        with tempfile.TemporaryDirectory() as td:
            env = sr.minimal_child_env(runtime_dir=Path(td) / "runtime", executable_path="/usr/bin:/bin")
        self.assertNotIn("AZPR_APPROVAL_KEYS_JSON", env)
        self.assertNotIn("AWS_SECRET_ACCESS_KEY", env)
        self.assertNotEqual(env.get("HOME"), os.environ.get("HOME"))

    def test_sensitive_extra_environment_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(sr.SecurityError):
                sr.minimal_child_env(runtime_dir=Path(td) / "runtime", executable_path="/bin", extra={"SIGNING_KEY": "x"})

    def test_runtime_root_must_be_outside_repository(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "repo"
            repo.mkdir()
            with self.assertRaises(sr.SecurityError):
                sr.runtime_root_for(repo, str(repo / "runtime"))

    def test_signed_journal_detects_tampering_and_nonce_replay(self):
        import sqlite3
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            private_path, public_path, _ = keypair(root, "journal")
            ledger = sr.NonceLedger(root / "runtime", private_key=private_path, public_key=public_path, key_id="journal-key")
            ledger.consume("n" * 24, document_id="approval-1", purpose="test", run_id="run-12345678")
            with self.assertRaises(sr.SecurityError):
                ledger.consume("n" * 24, document_id="approval-1", purpose="test", run_id="run-87654321")
            conn=sqlite3.connect(ledger.store.path)
            raw=conn.execute("SELECT record_json FROM event WHERE seq=1").fetchone()[0]
            conn.execute("UPDATE event SET record_json=? WHERE seq=1",(raw.replace("approval-1","approval-X"),)); conn.commit(); conn.close()
            with self.assertRaises(sr.SecurityError):
                ledger.consumed()

    def test_distinct_signer_quorum_and_roles(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            op_priv, op_pub, op_key = keypair(root, "op")
            sec_priv, sec_pub, sec_key = keypair(root, "sec")
            del op_priv, sec_priv
            keyring_path = root / "keyring.json"
            keyring_path.write_text(json.dumps({"format_version":"1.0","keys":[
                {"key_id":"op-key","signer_id":"alice","roles":["operator"],"public_key_pem":op_pub.read_text()},
                {"key_id":"sec-key","signer_id":"bob","roles":["security-approver"],"public_key_pem":sec_pub.read_text()}
            ]}))
            payload = {"document_id":"doc-1","signatures":[]}
            payload = signed(payload, "op-key", op_key)
            with self.assertRaises(sr.SecurityError):
                sr.verify_signatures(payload, keyring=sr.load_public_keyring(keyring_path), required_key_ids=[], required_signer_ids=[], required_roles=["operator","security-approver"], min_signers=2)
            payload = signed(payload, "sec-key", sec_key)
            signers = sr.verify_signatures(payload, keyring=sr.load_public_keyring(keyring_path), required_key_ids=[], required_signer_ids=[], required_roles=["operator","security-approver"], min_signers=2)
            self.assertEqual(signers, {"alice", "bob"})

    def test_nul_path_parsing_and_control_character_rejection(self):
        self.assertEqual(sr.split_nul_paths(b"src/a.py\0tests/t.py\0", label="git"), ["src/a.py", "tests/t.py"])
        with self.assertRaises(sr.SecurityError):
            sr.split_nul_paths(b"allowed\ncontroller.py\0", label="git")
        with self.assertRaises(sr.SecurityError):
            sr.split_nul_paths(b"missing-terminator", label="git")

    def test_segment_aware_globs(self):
        self.assertTrue(sr.path_matches("src/a.py", ["src/*"]))
        self.assertFalse(sr.path_matches("src/pkg/a.py", ["src/*"]))
        self.assertTrue(sr.path_matches("src/pkg/a.py", ["src/**"]))

    def test_redaction_and_size_cap(self):
        redacted = sr.redact_text("Authorization: Bearer abcdef token=secret 520-555-1212", max_chars=100)
        self.assertNotIn("abcdef", redacted)
        self.assertNotIn("secret", redacted)
        self.assertNotIn("520-555-1212", redacted)

    def test_topology_rejects_writable_symlink_and_hardlink(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            subprocess.run(["git","init","-q"],cwd=root,check=True)
            (root / "src").mkdir()
            target = root / "outside.txt"
            target.write_text("x")
            os.symlink(target, root / "src" / "link.txt")
            with self.assertRaises(sr.SecurityError):
                sr.repository_topology_preflight(root, ["src/**"])
            (root / "src" / "link.txt").unlink()
            original = root / "src" / "a.txt"; original.write_text("a")
            os.link(original, root / "src" / "b.txt")
            with self.assertRaises(sr.SecurityError):
                sr.repository_topology_preflight(root, ["src/**"])


class ControllerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.controller = load_controller()

    def test_required_approval_empty_or_zero_fails(self):
        stage = {"human_approval":{"required_before_run":True,"approval_files":[],"required_actions":[],"min_approvals":0,"required_signer_ids":[],"required_key_ids":[],"environment":"staging"}}
        errors = self.controller._strict_approval_policy_errors(stage, "stage")
        self.assertGreaterEqual(len(errors), 4)

    def test_audit_semantic_consistency(self):
        stage = {"id":"002","kind":"audit"}
        base = {"stage_id":"002","audit":{"is_audit":True,"verdict":"PASS","audited_commit":"a"*40,"findings":[],"report_markdown":"report"},"corrections":[]}
        self.controller.validate_result_for_stage({**base,"outcome":"PASS"}, stage, "numbered")
        bad = json.loads(json.dumps(base)); bad["outcome"]="PASS_WITH_REQUIRED_CORRECTIONS"; bad["audit"]["verdict"]="PASS_WITH_REQUIRED_CORRECTIONS"
        with self.assertRaises(self.controller.ControllerError):
            self.controller.validate_result_for_stage(bad, stage, "numbered")
        blocked = json.loads(json.dumps(base)); blocked["outcome"]="BLOCKED"; blocked["audit"]["verdict"]="BLOCKED"
        with self.assertRaises(self.controller.ControllerError):
            self.controller.validate_result_for_stage(blocked, stage, "numbered")

    def test_security_sensitive_correction_requires_human_authorization(self):
        stage = {"id":"002","kind":"audit"}
        correction = {"correction_id":"c1","finding_id":"f1","severity":"HIGH","evidence":"e","required_action":"fix","owner":"security","acceptance_criteria":"pass","progression_effect":"blocks","blocking":True,"authorized_handler":"APPENDIX_A","audited_commit":"a"*40,"allowed_change_paths":["src/auth.py"],"path_budget":1,"security_sensitive":True}
        result={"stage_id":"002","outcome":"PASS_WITH_REQUIRED_CORRECTIONS","audit":{"is_audit":True,"verdict":"PASS_WITH_REQUIRED_CORRECTIONS","audited_commit":"a"*40,"findings":[{"finding_id":"f1","blocking":True}],"report_markdown":"r"},"corrections":[correction]}
        with self.assertRaises(self.controller.ControllerError):
            self.controller.validate_result_for_stage(result,stage,"numbered")
        correction["human_authorization_id"]="approval-123"
        self.controller.validate_result_for_stage(result,stage,"numbered")

    def test_refined_source_does_not_contain_retired_trust_models(self):
        source=(TRUSTED / 'controller.py').read_text()
        for forbidden in ("AZPR_APPROVAL_KEYS_JSON", "HMAC secret", "runtime = root / \".codex-loop\""):
            self.assertNotIn(forbidden, source)


class ExternalRunnerDryRunTests(unittest.TestCase):
    def test_signed_plan_attestation_and_live_probe_dry_run(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); fixture=write_external_fixture(sr,PACK,root)
            evidence_dir=root/'evidence'; evidence_dir.mkdir()
            command=[sys.executable,str(fixture['runner']),'--installation-manifest',str(fixture['installation_path']),'--development-mode',
              '--plan',str(root/'plan.json'),'--manifest',str(root/'manifest.json'),'--target-attestation',str(root/'attestation.json'),
              '--operation-ticket',str(root/'ticket.json'),'--evidence-dir',str(evidence_dir),'--confirm','APPLY SIGNED AZPR CAPABILITY','--dry-run']
            completed=subprocess.run(command,capture_output=True,text=True,env={**os.environ,'AZPR_EXPLICIT_TEST_MODE':'1','AZPR_PRODUCTION_MODE':'0'})
            self.assertEqual(completed.returncode,0,completed.stderr+completed.stdout); self.assertIn('DRY_RUN_PASS',completed.stdout)
            self.assertEqual(list(evidence_dir.iterdir()),[])
            apply_command=[value for value in command if value!='--dry-run']
            applied=subprocess.run(apply_command,capture_output=True,text=True,env={**os.environ,'AZPR_EXPLICIT_TEST_MODE':'1','AZPR_PRODUCTION_MODE':'0'})
            self.assertEqual(applied.returncode,0,applied.stderr+applied.stdout)
            files=list(evidence_dir.glob('*.json')); self.assertEqual(len(files),1)
            evidence=json.loads(files[0].read_text()); sr.verify_manifest(evidence,public_key_path=fixture['evidence_public'],key_id='evidence')
            self.assertEqual(evidence['operation_registration_id'],fixture['ticket']['registration_id'])
            self.assertEqual(evidence['capability_nonce'],fixture['ticket']['capability_nonce'])
            replay=subprocess.run(apply_command,capture_output=True,text=True,env={**os.environ,'AZPR_EXPLICIT_TEST_MODE':'1','AZPR_PRODUCTION_MODE':'0'})
            self.assertNotEqual(replay.returncode,0); self.assertIn('already consumed',replay.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
