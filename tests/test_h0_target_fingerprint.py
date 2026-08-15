import contextlib
import hashlib
import importlib.util
import io
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts" / "h0_target_fingerprint.py"
SPEC = importlib.util.spec_from_file_location("h0_target_fingerprint", SCRIPT)
assert SPEC and SPEC.loader
fingerprint = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fingerprint)
PACK = ROOT / "automation" / "integration" / "v10.1" / "h0-ansible-live-stages"
VECTORS = PACK / "target-fingerprint-test-vectors.json"
SCHEMA = PACK / "operator-input.schema.json"
TEMPLATE = PACK / "operator-input.template.json"
CONTRACT = PACK / "target-fingerprint-contract.json"


class H0TargetFingerprintTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.vector = json.loads(VECTORS.read_text(encoding="utf-8"))["vectors"][0]

    def test_golden_vector_fixes_normalization_bytes_and_digest(self) -> None:
        normalized = fingerprint.normalize_identity(self.vector["input"])
        canonical = fingerprint.canonical_bytes(self.vector["input"])
        self.assertEqual(normalized, self.vector["normalized_identity"])
        self.assertEqual(canonical.decode("utf-8"), self.vector["canonical_json"])
        self.assertEqual(canonical.hex(), self.vector["canonical_utf8_hex"])
        self.assertEqual(hashlib.sha256(canonical).hexdigest(), self.vector["sha256"])
        self.assertEqual(fingerprint.fingerprint(self.vector["input"]), self.vector["sha256"])

    def test_member_order_is_fixed_and_bytes_have_no_newline_or_bom(self) -> None:
        canonical = fingerprint.canonical_bytes(self.vector["input"])
        decoded = json.loads(canonical)
        self.assertEqual(tuple(decoded), fingerprint.MEMBER_ORDER)
        self.assertFalse(canonical.endswith(b"\n"))
        self.assertFalse(canonical.startswith(b"\xef\xbb\xbf"))

    def test_missing_extra_invalid_and_unsupported_fields_fail_closed(self) -> None:
        cases = []
        missing = dict(self.vector["normalized_identity"])
        missing.pop("machine_id")
        cases.append(missing)
        extra = {**self.vector["normalized_identity"], "extra": "value"}
        cases.append(extra)
        invalid_machine = {**self.vector["normalized_identity"], "machine_id": "0" * 32}
        cases.append(invalid_machine)
        wrong_architecture = {**self.vector["normalized_identity"], "architecture": "arm64"}
        cases.append(wrong_architecture)
        boolean_uid = {**self.vector["normalized_identity"], "reviewer_uid": True}
        cases.append(boolean_uid)
        for identity in cases:
            with self.subTest(identity=identity):
                with self.assertRaises(fingerprint.TargetFingerprintError):
                    fingerprint.fingerprint(identity)

    def test_expected_digest_mismatch_blocks(self) -> None:
        observed, matches = fingerprint.compare_fingerprint(
            self.vector["normalized_identity"], "0" * 64
        )
        self.assertEqual(observed, self.vector["sha256"])
        self.assertFalse(matches)
        output = io.StringIO()
        with tempfile.TemporaryDirectory() as directory:
            identity_path = Path(directory) / "identity.json"
            identity_path.write_text(
                json.dumps(self.vector["normalized_identity"]), encoding="utf-8"
            )
            with contextlib.redirect_stdout(output):
                exit_code = fingerprint.main(
                    [
                        "calculate",
                        "--input",
                        str(identity_path),
                        "--expected-sha256",
                        "0" * 64,
                    ]
                )
        self.assertEqual(exit_code, 2)
        self.assertEqual(json.loads(output.getvalue())["status"], "BLOCKED")

    def test_independent_observation_uses_fixed_linux_sources(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            machine_id = root / "machine-id"
            hostname = root / "hostname"
            os_release = root / "os-release"
            machine_id.write_text("0123456789abcdef0123456789abcdef\n", encoding="ascii")
            hostname.write_text("AZPR-H0-Disposable-01\n", encoding="ascii")
            os_release.write_text('ID=ubuntu\nVERSION_ID="24.04"\n', encoding="utf-8")
            observed = fingerprint.observe_identity(
                machine_id_path=machine_id,
                hostname_path=hostname,
                os_release_path=os_release,
                uname=lambda: SimpleNamespace(machine="aarch64"),
                passwd_lookup=lambda name: SimpleNamespace(
                    pw_name=name,
                    pw_uid=1000,
                    pw_gid=1000,
                    pw_dir="/home/ubuntu",
                ),
            )
        self.assertEqual(observed, self.vector["normalized_identity"])

    def test_unavailable_observation_field_produces_no_digest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(fingerprint.TargetFingerprintError) as raised:
                fingerprint.observe_identity(
                    machine_id_path=root / "missing-machine-id",
                    hostname_path=root / "missing-hostname",
                    os_release_path=root / "missing-os-release",
                )
        self.assertEqual(raised.exception.code, "TARGET_IDENTITY_FIELD_UNAVAILABLE")

    def test_duplicate_os_release_identity_field_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "os-release"
            path.write_text(
                "ID=ubuntu\nID=ubuntu\nVERSION_ID=24.04\n", encoding="utf-8"
            )
            with self.assertRaises(fingerprint.TargetFingerprintError) as raised:
                fingerprint.parse_os_release(path)
        self.assertEqual(raised.exception.code, "INVALID_OS_RELEASE")

    def supplied_operator_input(self, now: datetime) -> dict:
        value = json.loads(TEMPLATE.read_text(encoding="utf-8"))
        identity = self.vector["normalized_identity"]
        value["status"] = "SUPPLIED_REFERENCE_NOT_APPROVAL"
        value["target"].update(identity)
        value["target"].update(
            target_fingerprint_sha256=self.vector["sha256"],
            disposable_target_confirmed=True,
            local_guest_session_confirmed=True,
        )
        value["authorization_reference"].update(
            authorized=True,
            reference="human-owned-reference",
            authorized_by="human-authorizer",
            authorized_at=(now - timedelta(minutes=1)).isoformat().replace("+00:00", "Z"),
            expires_at=(now + timedelta(minutes=30)).isoformat().replace("+00:00", "Z"),
            allowed_stage_ids=["H0-ALV-00"],
            target_fingerprint_sha256=self.vector["sha256"],
            target_fingerprint_contract_sha256=hashlib.sha256(CONTRACT.read_bytes()).hexdigest(),
            fingerprint_procedure_approved=True,
        )
        return value

    def test_operator_input_uses_draft_2020_12_format_checker_and_exact_bindings(self) -> None:
        now = datetime(2026, 8, 13, 18, 0, tzinfo=timezone.utc)
        value = self.supplied_operator_input(now)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "operator-input.json"
            path.write_text(json.dumps(value), encoding="utf-8")
            result = fingerprint.validate_operator_input(
                path,
                now=now,
                procedure_approval_check=lambda: SimpleNamespace(
                    approved=True,
                    approval_reference="human-owned-reference",
                    procedure_sha256=hashlib.sha256(CONTRACT.read_bytes()).hexdigest(),
                ),
            )
            self.assertTrue(result["authorization_reference_valid"])
            self.assertIs(result["authority_effect"], False)

            value["authorization_reference"]["authorized_at"] = "not-a-date-time"
            path.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaises(fingerprint.TargetFingerprintError) as raised:
                fingerprint.validate_operator_input(
                    path,
                    now=now,
                    procedure_approval_check=lambda: SimpleNamespace(
                        approved=True,
                        approval_reference="human-owned-reference",
                        procedure_sha256=hashlib.sha256(CONTRACT.read_bytes()).hexdigest(),
                    ),
                )
        self.assertEqual(raised.exception.code, "OPERATOR_INPUT_SCHEMA_MISMATCH")

    def test_operator_input_rejects_missing_procedure_approval_and_expiry(self) -> None:
        now = datetime(2026, 8, 13, 18, 0, tzinfo=timezone.utc)
        cases = []
        missing_approval = self.supplied_operator_input(now)
        missing_approval["authorization_reference"]["fingerprint_procedure_approved"] = False
        cases.append((missing_approval, "OPERATOR_INPUT_SCHEMA_MISMATCH"))
        expired = self.supplied_operator_input(now)
        expired["authorization_reference"]["expires_at"] = (
            now - timedelta(seconds=1)
        ).isoformat().replace("+00:00", "Z")
        cases.append((expired, "AUTHORIZATION_WINDOW_INVALID"))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "operator-input.json"
            for value, code in cases:
                with self.subTest(code=code):
                    path.write_text(json.dumps(value), encoding="utf-8")
                    with self.assertRaises(fingerprint.TargetFingerprintError) as raised:
                        fingerprint.validate_operator_input(
                            path,
                            now=now,
                            procedure_approval_check=lambda: SimpleNamespace(
                                approved=True,
                                approval_reference="human-owned-reference",
                                procedure_sha256=hashlib.sha256(CONTRACT.read_bytes()).hexdigest(),
                            ),
                        )
                    self.assertEqual(raised.exception.code, code)

    def test_operator_input_requires_the_repository_governed_procedure_reference(self) -> None:
        now = datetime(2026, 8, 13, 18, 0, tzinfo=timezone.utc)
        value = self.supplied_operator_input(now)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "operator-input.json"
            path.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaises(fingerprint.TargetFingerprintError) as raised:
                fingerprint.validate_operator_input(
                    path,
                    now=now,
                    procedure_approval_check=lambda: SimpleNamespace(
                        approved=False,
                        approval_reference=None,
                        procedure_sha256=hashlib.sha256(CONTRACT.read_bytes()).hexdigest(),
                    ),
                )
            self.assertEqual(raised.exception.code, "FINGERPRINT_PROCEDURE_APPROVAL_MISSING")

            with self.assertRaises(fingerprint.TargetFingerprintError) as raised:
                fingerprint.validate_operator_input(
                    path,
                    now=now,
                    procedure_approval_check=lambda: SimpleNamespace(
                        approved=True,
                        approval_reference="git:different:decision.json",
                        procedure_sha256=hashlib.sha256(CONTRACT.read_bytes()).hexdigest(),
                    ),
                )
            self.assertEqual(raised.exception.code, "PROCEDURE_APPROVAL_REFERENCE_MISMATCH")


if __name__ == "__main__":
    unittest.main()
