from __future__ import annotations

import base64
import hashlib
import inspect
import json
import os
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "operator-tools"))
sys.path.insert(0, str(ROOT / "trusted-installation"))

import verify_v10_cleanroom_prerequisites as cleanroom
from v10_1_host_trust import (
    HOST_AUTHORITY_KEY_NAME,
    HOST_MANIFEST_NAME,
    ROOT_FILENAMES,
    _load_host_qualification_context,
    load_host_qualification_context,
)
from v10_binding import (
    QUALIFICATION_ARTIFACT_SET_VERSION,
    REQUIRED_QUALIFIED_ARTIFACTS,
    canonical as binding_canonical,
    verify_bootstrap_roots,
    verify_phase_transition,
    verify_versioned_artifact_bindings,
)
from v10_external_signer_client import request_external_signature
from v10_probe_boundary import (
    TARGETS,
    canonical,
    load_approved_probe_authority,
    sha_bytes,
    verify_probe_manifest,
)
from v10_1_test_support import build_host_fixture, build_probe_manifest, signed_envelope, write_json


def _reload_authority(fixture: dict):
    fixture["context"] = _load_host_qualification_context(
        fixture["root"],
        owner_uid=os.geteuid(),
        expected_host_id=fixture["host_id"],
        expected_candidate_archive_sha256=fixture["candidate"],
        expected_challenge_sha256=fixture["challenge"],
    )
    fixture["authority"] = load_approved_probe_authority(
        host_context=fixture["context"],
        expected_host_id=fixture["host_id"],
        expected_candidate_archive_sha256=fixture["candidate"],
        expected_challenge_sha256=fixture["challenge"],
    )
    return fixture["authority"]


def _rewrite_host_manifest_root_hash(fixture: dict, artifact_name: str) -> None:
    """Only used for adversarial fixtures to preserve outer consistency after mutation."""
    root = fixture["root"]
    root.chmod(0o700)
    host_manifest_path = root / HOST_MANIFEST_NAME
    host_manifest_path.chmod(0o600)
    host = json.loads(host_manifest_path.read_text())
    host["roots"][artifact_name]["sha256"] = hashlib.sha256(fixture["paths"][artifact_name].read_bytes()).hexdigest()
    # The private host key is deliberately outside the trusted root in the fixture.
    private = serialization.load_pem_private_key(
        (root.parent / "signer-private" / "host-authority.private.pem").read_bytes(), password=None
    )
    unsigned = dict(host)
    unsigned.pop("signature")
    from v10_1_host_trust import canonical as host_canonical
    host["signature"] = base64.b64encode(private.sign(host_canonical(unsigned))).decode()
    write_json(host_manifest_path, host)
    root.chmod(0o500)


def _rewrite_trust_manifest_hash(fixture: dict, artifact_name: str, trust_field: str) -> None:
    root = fixture["root"]
    root.chmod(0o700)
    trust_path = fixture["paths"]["qualification_trust_manifest"]
    trust_path.chmod(0o600)
    trust = json.loads(trust_path.read_text())
    trust[trust_field] = hashlib.sha256(fixture["paths"][artifact_name].read_bytes()).hexdigest()
    private = serialization.load_pem_private_key(
        (root.parent / "signer-private" / "trust-authority.private.pem").read_bytes(), password=None
    )
    unsigned = dict(trust)
    unsigned.pop("signature")
    trust["signature"] = base64.b64encode(private.sign(canonical(unsigned))).decode()
    write_json(trust_path, trust)
    _rewrite_host_manifest_root_hash(fixture, "qualification_trust_manifest")


def test_v10_1_approved_independent_authority_and_all_envelopes_pass(tmp_path: Path):
    fixture = build_host_fixture(tmp_path)
    manifest, targets = build_probe_manifest(fixture, tmp_path / "envelopes")
    result = verify_probe_manifest(manifest, target_hashes=targets, approved_authority=fixture["authority"])
    assert set(result["envelope_hashes"]) == set(TARGETS)
    assert result["qualification_trust_binding_sha256"] == fixture["authority"].trust_binding_sha256


def test_v10_1_public_host_loader_has_no_caller_selectable_root_parameters():
    assert set(inspect.signature(load_host_qualification_context).parameters) == {
        "expected_host_id", "expected_candidate_archive_sha256", "expected_challenge_sha256", "now"
    }
    source = inspect.getsource(load_host_qualification_context)
    assert "HOST_ROOT" in source
    assert "root" not in inspect.signature(load_host_qualification_context).parameters


def test_v10_1_qualification_contract_rejects_complete_caller_trust_chain(monkeypatch, tmp_path: Path):
    fixture = build_host_fixture(tmp_path)
    monkeypatch.setattr(cleanroom, "load_host_qualification_context", lambda **_: fixture["context"])
    attacker_input = {
        "format_version": "2.1",
        "safe_for_unattended_execution_now": False,
        "trusted_pre_autonomous_installation_ready": False,
        "candidate_archive_sha256": fixture["candidate"],
        "bundle_manifest_sha256": "c" * 64,
        "challenge_sha256": fixture["challenge"],
        "host_id": fixture["host_id"],
        "agent_uid": 10001,
        "agent_gid": 10001,
        "validation_image_digest": "sha256:" + "d" * 64,
        "raw_evidence": {},
        "probe_targets": {},
        "artifacts": {},
        # Complete caller-selected hierarchy from the independently reproduced v10 attack.
        "trusted_ancestor": str(fixture["root"]),
        "expected_trust_owner_uid": os.geteuid(),
        "minimum_trust_sequence": 1,
        "external_signer_client": str(fixture["paths"]["external_signer_client"]),
        "qualification_receipt_signing_public_key": str(fixture["paths"]["qualification_receipt_signing_public_key"]),
    }
    with pytest.raises(SystemExit, match="shape/version mismatch|select a security trust root"):
        cleanroom.verify_inputs_and_build(attacker_input)


def test_v10_1_input_schema_excludes_caller_trust_selection():
    schema = json.loads((ROOT / "repository-overlay/automation/schemas/cleanroom-qualification-input.schema.json").read_text())
    props = set(schema["properties"])
    forbidden = {
        "trusted_ancestor", "expected_trust_owner_uid", "minimum_trust_sequence",
        "external_signer_client", "external_signer_identity_sha256",
        "qualification_receipt_signing_public_key", "receipt_signing_key_id",
    }
    assert not (props & forbidden)
    assert schema["additionalProperties"] is False


def test_v10_1_signed_policy_network_mode_is_enforced_exactly(tmp_path: Path):
    fixture = build_host_fixture(tmp_path, network_mode="DENY_ALL")
    weaker = dict(fixture["policy_boundary"])
    weaker["network_mode"] = "ISOLATED_CONTROLLED_ENDPOINT_ONLY"
    manifest, targets = build_probe_manifest(fixture, tmp_path / "envelopes", boundary=weaker)
    with pytest.raises(SystemExit, match="exact signed policy boundary"):
        verify_probe_manifest(manifest, target_hashes=targets, approved_authority=fixture["authority"])


def test_v10_1_signed_policy_maximum_age_is_enforced_exactly(tmp_path: Path):
    fixture = build_host_fixture(tmp_path, maximum_age_seconds=1)
    manifest, targets = build_probe_manifest(fixture, tmp_path / "envelopes", completed_offset_seconds=-3600)
    with pytest.raises(SystemExit, match="signed policy"):
        verify_probe_manifest(manifest, target_hashes=targets, approved_authority=fixture["authority"])


def test_v10_1_unsigned_or_forged_service_attestation_fails(tmp_path: Path):
    with pytest.raises(SystemExit, match="attestation signature failed"):
        build_host_fixture(tmp_path, attestation_signed=False)


def test_v10_1_service_identity_must_match_actual_descriptor_opened_executable(tmp_path: Path):
    with pytest.raises(SystemExit, match="actual executable bytes"):
        build_host_fixture(tmp_path, executable_digest_override="f" * 64)


def test_v10_1_future_trust_issued_at_fails(tmp_path: Path):
    with pytest.raises(SystemExit, match="issuance chronology invalid"):
        build_host_fixture(tmp_path, trust_issued_offset=timedelta(days=30), revocation_issued_offset=timedelta(days=30, minutes=1))


def test_v10_1_future_revocation_issued_at_fails(tmp_path: Path):
    with pytest.raises(SystemExit, match="issuance chronology invalid"):
        build_host_fixture(tmp_path, revocation_issued_offset=timedelta(days=30))



def test_v10_1_remote_anchor_rejects_rolled_back_host_root_sequence(tmp_path: Path):
    fixture = build_host_fixture(tmp_path)
    root = fixture["root"]
    root.chmod(0o700)
    manifest_path = root / HOST_MANIFEST_NAME
    manifest_path.chmod(0o600)
    value = json.loads(manifest_path.read_text())
    value["sequence"] = 10
    private = serialization.load_pem_private_key(
        (root.parent / "signer-private" / "host-authority.private.pem").read_bytes(), password=None
    )
    from v10_1_host_trust import canonical as host_canonical
    unsigned = dict(value); unsigned.pop("signature")
    value["signature"] = base64.b64encode(private.sign(host_canonical(unsigned))).decode()
    write_json(manifest_path, value)
    root.chmod(0o500)
    with pytest.raises(SystemExit, match="remote anchor query failed closed"):
        _load_host_qualification_context(
            root, owner_uid=os.geteuid(), expected_host_id=fixture["host_id"],
            expected_candidate_archive_sha256=fixture["candidate"], expected_challenge_sha256=fixture["challenge"],
        )

def test_v10_1_revoked_and_wrong_role_probe_keys_fail(tmp_path: Path):
    with pytest.raises(SystemExit, match="role or service mismatch"):
        build_host_fixture(tmp_path / "wrong-role", probe_key_role="untrusted-role")
    fixture = build_host_fixture(tmp_path / "revoked", revoked_probe_keys=["probe-key-v10-1-0001"])
    manifest, targets = build_probe_manifest(fixture, tmp_path / "revoked-envelopes")
    with pytest.raises(SystemExit, match="unapproved or revoked"):
        verify_probe_manifest(manifest, target_hashes=targets, approved_authority=fixture["authority"])


def test_v10_1_mutating_each_envelope_trust_binding_field_fails(tmp_path: Path):
    fixture = build_host_fixture(tmp_path)
    fields = [
        "host_id", "candidate_archive_sha256", "challenge_sha256",
        "qualification_trust_manifest_sha256", "probe_keyring_sha256", "probe_policy_sha256",
        "probe_service_identity_sha256", "probe_service_attestation_sha256", "probe_revocation_state_sha256",
        "probe_attestor_keyring_sha256", "probe_attestor_revocation_state_sha256",
        "probe_service_executable_sha256", "signer_service_id",
    ]
    for field in fields:
        case_dir = tmp_path / ("case-" + field)
        manifest, targets = build_probe_manifest(fixture, case_dir)
        value = json.loads(manifest.read_text())
        role = TARGETS[0]
        envelope_path = Path(value["envelopes"][role]["path"])
        envelope_path.chmod(0o600)
        envelope = json.loads(envelope_path.read_text())
        envelope[field] = "wrong-service" if field in {"host_id", "signer_service_id"} else "f" * 64
        unsigned = dict(envelope)
        unsigned.pop("signature")
        envelope["signature"] = base64.b64encode(fixture["probe_private"].sign(canonical(unsigned))).decode()
        write_json(envelope_path, envelope)
        value["envelopes"][role]["sha256"] = hashlib.sha256(envelope_path.read_bytes()).hexdigest()
        value["aggregate_sha256"] = sha_bytes(canonical({x: value["envelopes"][x]["sha256"] for x in TARGETS}))
        manifest.chmod(0o600)
        write_json(manifest, value)
        with pytest.raises(SystemExit, match="trust binding mismatch"):
            verify_probe_manifest(manifest, target_hashes=targets, approved_authority=fixture["authority"])


def test_v10_1_external_signer_independently_reloads_fixed_authority(tmp_path: Path):
    fixture = build_host_fixture(tmp_path)
    binding = fixture["authority"].trust_binding
    unsigned = {
        "format_version": "4.1",
        "receipt_kind": "AZPR_V10_1_SEMANTIC_CLEANROOM_QUALIFICATION_RECEIPT",
        "host_id": fixture["host_id"],
        "candidate_archive_sha256": fixture["candidate"],
        "challenge_sha256": fixture["challenge"],
        "qualification_trust_binding": binding,
        "qualification_trust_binding_sha256": fixture["authority"].trust_binding_sha256,
        "external_signer_identity_sha256": fixture["context"].external_signer_identity_sha256,
        "signer_key_id": fixture["context"].receipt_signing_key_id,
    }
    signed = request_external_signature(
        unsigned_receipt=unsigned,
        qualification_trust_binding=binding,
        host_context=fixture["context"],
        request_nonce="nonce-v10-1-0001",
    )
    assert "signature" in signed
    attacker = dict(binding)
    attacker["probe_policy_sha256"] = "f" * 64
    attacker_unsigned = dict(unsigned)
    attacker_unsigned["qualification_trust_binding"] = attacker
    attacker_unsigned["qualification_trust_binding_sha256"] = sha_bytes(canonical(attacker))
    with pytest.raises(SystemExit, match="failed closed"):
        request_external_signature(
            unsigned_receipt=attacker_unsigned,
            qualification_trust_binding=attacker,
            host_context=fixture["context"],
            request_nonce="nonce-v10-1-0002",
        )


def _keypair(directory: Path, name: str):
    private = Ed25519PrivateKey.generate()
    private_path = directory / f"{name}.private.pem"
    public_path = directory / f"{name}.public.pem"
    private_path.write_bytes(private.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    public_path.write_bytes(private.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo))
    private_path.chmod(0o400)
    public_path.chmod(0o444)
    return private, public_path


def _bootstrap_fixture(tmp_path: Path):
    trusted = tmp_path / "bootstrap"
    trusted.mkdir(mode=0o700)
    private_dir = tmp_path / "private"
    private_dir.mkdir(mode=0o700)
    authority, authority_pub_private = _keypair(private_dir, "bootstrap")
    authority_pub = trusted / "bootstrap.public.pem"
    shutil.copy2(authority_pub_private, authority_pub)
    authority_pub.chmod(0o444)
    roots: dict[str, Path] = {}
    for name in (
        "qualification_authorization_keyring", "qualification_receipt_public_key", "phase_transition_keyring",
        "authorization_anchor", "qualification_trust_manifest", "qualification_trust_authority_public_key",
        "host_qualification_roots_manifest", "host_qualification_roots_authority_public_key",
    ):
        path = trusted / name
        path.write_bytes(name.encode())
        path.chmod(0o444)
        roots[name] = path
    hashes = {
        "qualification_authorization_keyring_sha256": hashlib.sha256(roots["qualification_authorization_keyring"].read_bytes()).hexdigest(),
        "qualification_receipt_signing_public_key_sha256": hashlib.sha256(roots["qualification_receipt_public_key"].read_bytes()).hexdigest(),
        "phase_transition_keyring_sha256": hashlib.sha256(roots["phase_transition_keyring"].read_bytes()).hexdigest(),
        "authorization_anchor_identity_sha256": hashlib.sha256(roots["authorization_anchor"].read_bytes()).hexdigest(),
        "qualification_trust_manifest_sha256": hashlib.sha256(roots["qualification_trust_manifest"].read_bytes()).hexdigest(),
        "qualification_trust_authority_public_key_sha256": hashlib.sha256(roots["qualification_trust_authority_public_key"].read_bytes()).hexdigest(),
        "host_qualification_roots_manifest_sha256": hashlib.sha256(roots["host_qualification_roots_manifest"].read_bytes()).hexdigest(),
        "host_qualification_roots_authority_public_key_sha256": hashlib.sha256(roots["host_qualification_roots_authority_public_key"].read_bytes()).hexdigest(),
    }
    now = datetime.now(timezone.utc)
    unsigned = {
        "format_version": "1.0", "bootstrap_kind": "AZPR_V10_HOST_BOOTSTRAP_ROOTS",
        "manifest_id": "bootstrap-v10-1-0001", "sequence": 6,
        "issued_at": now.isoformat(), "expires_at": (now + timedelta(days=3)).isoformat(),
        "roots": hashes, "signer_key_id": "bootstrap-authority-v10-1",
    }
    manifest = trusted / "manifest.json"
    write_json(manifest, {**unsigned, "signature": base64.b64encode(authority.sign(binding_canonical(unsigned))).decode()})
    return trusted, manifest, authority_pub, roots


def _call_bootstrap(fixture, manifest=None, key=None):
    trusted, real_manifest, real_key, roots = fixture
    return verify_bootstrap_roots(
        manifest or real_manifest,
        key or real_key,
        qualification_authorization_keyring=roots["qualification_authorization_keyring"],
        qualification_receipt_public_key=roots["qualification_receipt_public_key"],
        phase_transition_keyring=roots["phase_transition_keyring"],
        authorization_anchor=roots["authorization_anchor"],
        qualification_trust_manifest=roots["qualification_trust_manifest"],
        qualification_trust_authority_public_key=roots["qualification_trust_authority_public_key"],
        host_qualification_roots_manifest=roots["host_qualification_roots_manifest"],
        host_qualification_roots_authority_public_key=roots["host_qualification_roots_authority_public_key"],
        trusted_ancestor=trusted,
        expected_owner_uid=os.geteuid(),
        minimum_sequence=6,
    )


def test_v10_1_bootstrap_pins_higher_host_authority_and_rejects_symlink_hardlink(tmp_path: Path):
    fixture = _bootstrap_fixture(tmp_path)
    result = _call_bootstrap(fixture)
    assert result["sequence"] == 6
    trusted, manifest, key, _ = fixture
    manifest_link = trusted / "manifest-link.json"
    manifest_link.symlink_to(manifest)
    with pytest.raises(SystemExit, match="no-follow|symlink"):
        _call_bootstrap(fixture, manifest=manifest_link)
    key_link = trusted / "key-link.pem"
    key_link.symlink_to(key)
    with pytest.raises(SystemExit, match="no-follow|symlink"):
        _call_bootstrap(fixture, key=key_link)
    hard = trusted / "manifest-hard.json"
    os.link(manifest, hard)
    with pytest.raises(SystemExit, match="multiple hard links|single-link"):
        _call_bootstrap(fixture, manifest=hard)


def test_v10_1_exact_versioned_57_artifacts_and_alias_substitution_fail(tmp_path: Path):
    assert QUALIFICATION_ARTIFACT_SET_VERSION == "2.1"
    assert len(REQUIRED_QUALIFIED_ARTIFACTS) == 57
    entries, receipt, expected = {}, {}, {}
    secrets = {"runtime_private_key", "evidence_private_key", "installation_signing_private_key"}
    for index, name in enumerate(REQUIRED_QUALIFIED_ARTIFACTS):
        path = tmp_path / f"{index:02d}-{name}"
        path.write_bytes(name.encode())
        path.chmod(0o400 if name in secrets else (0o555 if name.endswith("binary") or name in {"external_signer_client", "probe_service_executable", "container_engine", "anchor_helper", "git_binary", "python_binary", "codex_binary"} else 0o444))
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        entries[name] = {"path": str(path), "sha256": digest, "secret": name in secrets}
        receipt[name] = digest
        expected[name] = path
    manifest = {"format_version": "1.0", "artifact_set_version": "2.1", "artifacts": entries}
    actual, aggregate = verify_versioned_artifact_bindings(manifest, receipt, expected)
    assert len(actual) == 57 and aggregate == hashlib.sha256(binding_canonical(actual)).hexdigest()
    missing = json.loads(json.dumps(manifest))
    missing["artifacts"].pop(REQUIRED_QUALIFIED_ARTIFACTS[0])
    with pytest.raises(SystemExit, match="set mismatch"):
        verify_versioned_artifact_bindings(missing, receipt, expected)
    a, b = REQUIRED_QUALIFIED_ARTIFACTS[:2]
    entries[b]["path"] = entries[a]["path"]
    entries[b]["sha256"] = entries[a]["sha256"]
    receipt[b] = receipt[a]
    expected[b] = expected[a]
    with pytest.raises(SystemExit, match="alias"):
        verify_versioned_artifact_bindings(manifest, receipt, expected)


def test_v10_1_first_install_remains_qualification_only(tmp_path: Path):
    with pytest.raises(SystemExit, match="first installation may only"):
        verify_phase_transition(
            installation_phase="POLICY_ACTIVATED", active_lock_path=tmp_path / "missing",
            authorization={"canonical_policy_status": "APPROVED"}, phase_authorization={},
            canonical_policy_record_path=None, prior_receipt_path=None,
            qualification_launcher_evidence_path=None, fault_matrix_evidence_path=None,
            load_json=lambda p, label: json.loads(p.read_text()),
        )
    assert verify_phase_transition(
        installation_phase="QUALIFICATION_ONLY", active_lock_path=tmp_path / "missing",
        authorization={"canonical_policy_status": "NOT_YET_APPROVED"}, phase_authorization=None,
        canonical_policy_record_path=None, prior_receipt_path=None,
        qualification_launcher_evidence_path=None, fault_matrix_evidence_path=None,
        load_json=lambda p, label: json.loads(p.read_text()),
    ) is None


def test_v10_1_installer_enforces_fixed_roots_before_reservation():
    source = (ROOT / "trusted-installation/install.py").read_text()
    ordered = [
        "bootstrap=verify_bootstrap_roots",
        "host_context=load_host_qualification_context",
        "authority=load_approved_probe_authority",
        "probe_verification=verify_probe_manifest",
        "actual_bindings,aggregate=verify_complete_artifact_bindings",
        "_reserve_authorization(qualification)",
    ]
    positions = [source.index(token) for token in ordered]
    assert positions == sorted(positions)
    for token in (
        "host-qualification-roots-v10.1.json",
        "external-receipt-signer-identity-v10.1.json",
        "probe-service-v10.1",
        "host-root-anchor-client-v10.1",
        "host-root-anchor-identity-v10.1.json",
        "QUALIFICATION_ONLY",
    ):
        assert token in source


def test_v10_1_reference_signer_removed_from_release_path():
    assert not (ROOT / "operator-tools/v10_external_signer_reference.py").exists()
    archived = ROOT / "legacy/v10/unsafe-reference-signer/v10_external_signer_reference.py.disabled"
    assert archived.exists()
    for current in (ROOT / "operator-tools/v10_external_signer_client.py", ROOT / "operator-tools/verify_v10_cleanroom_prerequisites.py"):
        text = current.read_text()
        assert "AZPR_V10_TEST_TRUST_CONFIG" not in text
        assert "TEST_REFERENCE_SIGNER_PRIVATE_KEY" not in text


def test_v10_1_host_trust_root_contains_no_private_key_material(tmp_path: Path):
    fixture = build_host_fixture(tmp_path)
    names = {p.name for p in fixture["root"].iterdir()}
    assert not any("private" in name.lower() for name in names)
    assert set(ROOT_FILENAMES.values()).issubset(names)
    assert HOST_MANIFEST_NAME in names and HOST_AUTHORITY_KEY_NAME in names


def test_v10_1_strict_schemas_are_bounded_and_no_generic_signer_objects():
    from test_autonomous_priming_controls import AutonomousPrimingControlTests
    AutonomousPrimingControlTests("test_every_json_schema_is_bounded_and_strict").test_every_json_schema_is_bounded_and_strict()
    schemas = ROOT / "repository-overlay/automation/schemas"
    for name in (
        "external-receipt-signing-response-v10.schema.json",
        "external-receipt-signing-request-v10.schema.json",
        "probe-policy-v10.schema.json",
        "probe-service-attestation-v10.schema.json",
    ):
        value = json.loads((schemas / name).read_text())
        assert value["additionalProperties"] is False
        assert value.get("required")
        assert value.get("properties")


def test_v10_1_prompt_archive_bytes_are_unchanged():
    prompt_zip = ROOT / "markdown-prompts-autonomous-priming-draft.zip"
    assert hashlib.sha256(prompt_zip.read_bytes()).hexdigest() == "3b235cb7e33ca409241ff26523f60f8fee89cec524b3f09e91a69927a0aa4880"


def test_v10_1_inherited_transaction_evidence_and_key_lifecycle_controls_remain():
    tx = (ROOT / "trusted-installation/v9_transaction.py").read_text()
    evidence = (ROOT / "operator-tools/v9_evidence_derivation.py").read_text()
    lifecycle = (ROOT / "operator-tools/apply_key_lifecycle_transition_v9.py").read_text()
    for token in ("fcntl.flock", "PENDING.json", "compare_and_publish", "authorization ID replay", "authorization nonce replay"):
        assert token in tx
    for token in ("raw evidence decisive check failed or missing", "signed qualification measurements do not match machine-derived raw evidence"):
        assert token in evidence
    for token in ("TRUST_STORES", "active trust epoch pointer rollback detected", "ROLLED_BACK_UNANCHORED_EPOCH"):
        assert token in lifecycle


def test_v10_1_release_verifier_is_nonroot_isolated_and_complete_catalog_aware():
    source = (ROOT / "VERIFY-V10-CANDIDATE.py").read_text()
    assert "dir='/root'" not in source and 'dir="/root"' not in source
    for token in ("start_new_session=True", "PYTHONDONTWRITEBYTECODE", "V10-RELEASE-TEST-CATALOG.json"):
        assert token in source
