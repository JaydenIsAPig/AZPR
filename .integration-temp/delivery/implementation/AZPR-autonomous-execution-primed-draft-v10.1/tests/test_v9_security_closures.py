from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import textwrap
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "trusted-installation"))
sys.path.insert(0, str(ROOT / "operator-tools"))

from v9_binding import REQUIRED_QUALIFIED_ARTIFACTS, verify_bootstrap_roots, verify_complete_artifact_bindings, verify_phase_transition
from v9_evidence_derivation import OUTPUT_FIELDS, REQUIRED_TRUE, derive_measurements, verify_report_derivation
from v9_external_signer_client import request_external_signature
from v9_probe_boundary import TARGETS, canonical as probe_canonical, sha_bytes as probe_sha, verify_probe_manifest
from v9_transaction import AuthorizationTransactionStore, InstallerGlobalLock, canonical as tx_canonical, sha_bytes
from apply_key_lifecycle_transition_v9 import TRUST_STORES, TrustEpochStore, canonical as lifecycle_canonical, resolve_active_store


def keypair(tmp: Path, name: str = "key"):
    private = Ed25519PrivateKey.generate()
    priv = tmp / f"{name}.private.pem"
    pub = tmp / f"{name}.public.pem"
    priv.write_bytes(private.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    pub.write_bytes(private.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo))
    priv.chmod(0o400); pub.chmod(0o444)
    return private, priv, pub


def write_json(path: Path, value: dict, mode: int = 0o444):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    path.chmod(mode)


def copy_anchor(tmp: Path) -> Path:
    anchor = tmp / "anchor"
    shutil.copy2(ROOT / "operator-tools" / "v9_file_anchor_reference.py", anchor)
    anchor.chmod(0o555)
    return anchor


def signed_probe(private, key_id: str, role: str, target_sha: str, policy_sha: str):
    now = datetime.now(timezone.utc)
    unsigned = {
        "format_version": "1.0", "envelope_kind": "AZPR_V9_NO_SECRET_PROBE_RESULT",
        "target_role": role, "target_sha256": target_sha, "probe_policy_sha256": policy_sha,
        "boundary": {"rootless": True, "no_secrets": True, "host_mounts": False, "daemon_sockets": False,
                     "pid_namespace": True, "mount_namespace": True, "cgroup_v2": True, "disposable": True,
                     "run_as_uid": 65534, "run_as_gid": 65534, "network_mode": "DENY_ALL"},
        "observations": {"secret_read_denied": True, "host_read_denied": True, "network_denied": True,
                         "mount_denied": True, "daemon_access_denied": True, "escape_denied": True,
                         "resource_exhaustion_contained": True, "evidence_mutation_denied": True},
        "exit_code": 0, "started_at": (now - timedelta(seconds=1)).isoformat(), "completed_at": now.isoformat(),
        "signer_key_id": key_id,
    }
    return {**unsigned, "signature": base64.b64encode(private.sign(probe_canonical(unsigned))).decode()}


def test_f01_no_secret_probe_envelopes_never_execute_targets(tmp_path: Path):
    marker = tmp_path / "EXECUTED"
    signer, _, signer_pub = keypair(tmp_path, "probe")
    pub_pem = signer_pub.read_text()
    keyring = {"format_version": "1.0", "keys": [{"key_id": "probe-key-0001", "signer_id": "probe-service-0001", "roles": ["qualification-probe-service"], "public_key_pem": pub_pem}]}
    policy_sha = "a" * 64
    target_hashes = {}; rows = {}
    for role in TARGETS:
        target = tmp_path / f"malicious-{role}"
        target.write_text(f"#!/bin/sh\necho pwned >> {marker}\nexit 0\n"); target.chmod(0o555)
        target_hashes[role] = hashlib.sha256(target.read_bytes()).hexdigest()
        envelope_path = tmp_path / f"{role}.json"
        write_json(envelope_path, signed_probe(signer, "probe-key-0001", role, target_hashes[role], policy_sha))
        rows[role] = {"path": str(envelope_path), "sha256": hashlib.sha256(envelope_path.read_bytes()).hexdigest()}
    aggregate = probe_sha(probe_canonical({role: rows[role]["sha256"] for role in TARGETS}))
    manifest = tmp_path / "manifest.json"
    write_json(manifest, {"format_version": "1.0", "manifest_kind": "AZPR_V9_PROBE_ENVELOPES_MANIFEST", "probe_policy_sha256": policy_sha, "envelopes": rows, "aggregate_sha256": aggregate})
    verify_probe_manifest(manifest, target_hashes=target_hashes, probe_keyring=keyring)
    assert not marker.exists(), "qualified target was executed by the verifier"


def test_f01_root_or_secret_boundary_claim_fails(tmp_path: Path):
    signer, _, signer_pub = keypair(tmp_path, "probe")
    env = signed_probe(signer, "probe-key-0001", "codex_binary", "b" * 64, "c" * 64)
    env["boundary"]["run_as_uid"] = 0
    unsigned = dict(env); unsigned.pop("signature")
    env["signature"] = base64.b64encode(signer.sign(probe_canonical(unsigned))).decode()
    from v9_probe_boundary import load_probe_keyring, verify_probe_envelope
    keys = load_probe_keyring({"format_version": "1.0", "keys": [{"key_id": "probe-key-0001", "signer_id": "probe-service-0001", "roles": ["qualification-probe-service"], "public_key_pem": signer_pub.read_text()}]})
    with pytest.raises(SystemExit, match="ran as root"):
        verify_probe_envelope(env, expected_role="codex_binary", expected_target_sha256="b" * 64, expected_probe_policy_sha256="c" * 64, keys=keys)


def test_f01_external_signing_protocol_has_no_receipt_private_key_in_verifier(tmp_path: Path):
    signer, priv, pub = keypair(tmp_path, "receipt")
    reference = ROOT / "operator-tools" / "v9_external_signer_reference.py"
    trusted_base = Path("/root") if os.geteuid() == 0 else Path("/home/oai")
    trusted_dir = trusted_base / ("azpr-v9-signer-test-" + tmp_path.name)
    trusted_dir.mkdir(mode=0o700)
    wrapper = trusted_dir / "signer-client"
    wrapper.write_text(f"#!/bin/sh\nexport AZPR_V9_TEST_REFERENCE_SIGNER=1\nexport AZPR_V9_TEST_REFERENCE_SIGNER_PRIVATE_KEY='{priv}'\nexec '{sys.executable}' '{reference}' \"$@\"\n")
    wrapper.chmod(0o555)
    identity = hashlib.sha256(wrapper.read_bytes()).hexdigest()
    unsigned = {"format_version": "3.0", "receipt_kind": "test", "signer_key_id": "receipt-key-0001"}
    receipt = request_external_signature(unsigned_receipt=unsigned, signer_client=wrapper, signer_identity_sha256=identity, receipt_public_key=pub, request_nonce="nonce-00000001")
    assert "signature" in receipt
    verifier_source = (ROOT / "operator-tools" / "verify_v9_cleanroom_prerequisites.py").read_text()
    assert "qualification_receipt_signing_private_key" not in verifier_source
    assert "receipt-private-key" not in verifier_source
    shutil.rmtree(trusted_dir)


def test_f06_contradictory_machine_evidence_fails(tmp_path: Path):
    kind = "REMOTE_ANCHOR_QUALIFICATION"
    checks = {name: True for name in REQUIRED_TRUE[kind]}
    checks.update({"anchor_endpoint_id": "anchor-0001", "challenge_response_sha256": "d" * 64})
    raw = {"format_version": "1.0", "evidence_kind": "AZPR_V9_MACHINE_DERIVABLE_QUALIFICATION_EVIDENCE", "report_kind": kind,
           "challenge_nonce": "challenge-0001", "host_id": "host-00000001", "candidate_archive_sha256": "e" * 64,
           "commands": [{"command_id": "cmd-0001", "exit_code": 0, "argv_sha256": "1" * 64, "tool_sha256": "2" * 64, "stdout_sha256": "3" * 64, "stderr_sha256": "4" * 64}],
           "checks": checks, "transcript_sha256": "5" * 64}
    raw_path = tmp_path / "raw.json"; write_json(raw_path, raw)
    derived = derive_measurements(raw, kind)
    report = {"report_kind": kind, "host_id": raw["host_id"], "candidate_archive_sha256": raw["candidate_archive_sha256"], "status": "PASS", "measurements": derived}
    verify_report_derivation(report, raw_path)
    # The verifier intentionally consumes immutable raw evidence. Make the
    # test mutation explicit by replacing the fixture through a writable test
    # inode, then restore the delivery-mode permissions before verification.
    raw["checks"]["rollback_test_passed"] = False
    raw_path.chmod(0o600)
    write_json(raw_path, raw)
    with pytest.raises(SystemExit, match="decisive check failed"):
        verify_report_derivation(report, raw_path)


def make_binding_fixture(tmp: Path):
    entries = {}; receipt = {}; expected = {}
    for index, name in enumerate(REQUIRED_QUALIFIED_ARTIFACTS):
        path = tmp / f"{index:02d}-{name}.bin"
        path.write_bytes(f"artifact:{name}".encode())
        secret = name.endswith("private_key")
        path.chmod(0o400 if secret else 0o444)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        entries[name] = {"path": str(path), "sha256": digest, "secret": secret}
        receipt[name] = digest; expected[name] = path
    return {"format_version": "1.0", "artifacts": entries}, receipt, expected


def test_f03_exact_39_bindings_and_each_substitution_fails(tmp_path: Path):
    manifest, receipt, expected = make_binding_fixture(tmp_path)
    actual, aggregate = verify_complete_artifact_bindings(manifest, receipt, expected)
    assert len(actual) == 39 and aggregate == sha_bytes(json.dumps(actual, sort_keys=True, separators=(",", ":")).encode())
    for name in REQUIRED_QUALIFIED_ARTIFACTS:
        path = expected[name]; original = path.read_bytes(); mode = path.stat().st_mode & 0o777
        path.chmod(0o600); path.write_bytes(original + b"X"); path.chmod(mode)
        with pytest.raises(SystemExit): verify_complete_artifact_bindings(manifest, receipt, expected)
        path.chmod(0o600); path.write_bytes(original); path.chmod(mode)
    assert len(REQUIRED_QUALIFIED_ARTIFACTS) == 39


def test_f03_alias_symlink_and_path_substitution_fail(tmp_path: Path):
    manifest, receipt, expected = make_binding_fixture(tmp_path)
    names = list(REQUIRED_QUALIFIED_ARTIFACTS); a, b = names[0], names[1]
    hard = tmp_path / "hardlink"; os.link(expected[a], hard)
    row = dict(manifest["artifacts"][b]); row["path"] = str(hard); row["sha256"] = receipt[a]
    bad = json.loads(json.dumps(manifest)); bad["artifacts"][b] = row; bad_receipt = dict(receipt); bad_receipt[b] = receipt[a]; bad_expected = dict(expected); bad_expected[b] = hard
    with pytest.raises(SystemExit): verify_complete_artifact_bindings(bad, bad_receipt, bad_expected)
    hard.unlink()
    symlink = tmp_path / "alias"; symlink.symlink_to(expected[a])
    bad["artifacts"][b]["path"] = str(symlink); bad_expected[b] = symlink
    with pytest.raises(SystemExit): verify_complete_artifact_bindings(bad, bad_receipt, bad_expected)
    with pytest.raises(SystemExit, match="path differs"):
        verify_complete_artifact_bindings(manifest, receipt, {**expected, a: tmp_path / "wrong"})


def test_f03_pinned_bootstrap_root_substitution_fails(tmp_path: Path):
    authority, _, authority_pub = keypair(tmp_path, "authority")
    files = {}
    for name in ["q", "receipt", "phase", "anchor"]:
        p = tmp_path / name; p.write_bytes(name.encode()); p.chmod(0o444); files[name] = p
    roots = {"qualification_authorization_keyring_sha256": hashlib.sha256(files["q"].read_bytes()).hexdigest(),
             "qualification_receipt_signing_public_key_sha256": hashlib.sha256(files["receipt"].read_bytes()).hexdigest(),
             "phase_transition_keyring_sha256": hashlib.sha256(files["phase"].read_bytes()).hexdigest(),
             "authorization_anchor_identity_sha256": hashlib.sha256(files["anchor"].read_bytes()).hexdigest()}
    unsigned = {"format_version": "1.0", "bootstrap_kind": "AZPR_V9_HOST_BOOTSTRAP_ROOTS", "manifest_id": "bootstrap-0001", "sequence": 1, "issued_at": datetime.now(timezone.utc).isoformat(), "roots": roots, "signer_key_id": "bootstrap-authority-0001"}
    manifest = {**unsigned, "signature": base64.b64encode(authority.sign(json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode())).decode()}
    mp = tmp_path / "bootstrap.json"; write_json(mp, manifest)
    verify_bootstrap_roots(mp, authority_pub, qualification_authorization_keyring=files["q"], qualification_receipt_public_key=files["receipt"], phase_transition_keyring=files["phase"], authorization_anchor=files["anchor"])
    files["q"].chmod(0o600); files["q"].write_bytes(b"replacement"); files["q"].chmod(0o444)
    with pytest.raises(SystemExit, match="differs from pinned bootstrap"):
        verify_bootstrap_roots(mp, authority_pub, qualification_authorization_keyring=files["q"], qualification_receipt_public_key=files["receipt"], phase_transition_keyring=files["phase"], authorization_anchor=files["anchor"])


def test_f05_first_install_forced_qualification_only_and_exact_transition(tmp_path: Path):
    auth = {"canonical_policy_status": "APPROVED"}
    with pytest.raises(SystemExit, match="first installation may only"):
        verify_phase_transition(installation_phase="POLICY_ACTIVATED", active_lock_path=tmp_path / "missing", authorization=auth, phase_authorization={}, canonical_policy_record_path=None, prior_receipt_path=None, qualification_launcher_evidence_path=None, fault_matrix_evidence_path=None, load_json=lambda p, l: json.loads(p.read_text()))
    assert verify_phase_transition(installation_phase="QUALIFICATION_ONLY", active_lock_path=tmp_path / "missing", authorization={"canonical_policy_status": "NOT_YET_APPROVED"}, phase_authorization=None, canonical_policy_record_path=None, prior_receipt_path=None, qualification_launcher_evidence_path=None, fault_matrix_evidence_path=None, load_json=lambda p, l: json.loads(p.read_text())) is None
    prior = tmp_path / "prior.json"; write_json(prior, {"installation_id": "install-0001", "installation_phase": "QUALIFICATION_ONLY", "host_id": "host-00000001"})
    lock = tmp_path / "active.json"; write_json(lock, {"manifest_path": str(prior)})
    receipt = tmp_path / "receipt.json"; write_json(receipt, {"installation_id": "install-0001"})
    launcher = tmp_path / "launcher.json"; write_json(launcher, {"status": "PASS"})
    fault = tmp_path / "fault.json"; write_json(fault, {"status": "PASS"})
    policy = tmp_path / "policy.json"; write_json(policy, {"status": "APPROVED"})
    h = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
    phase = {"prior_installation_id": "install-0001", "prior_manifest_sha256": h(prior), "prior_lock_sha256": h(lock), "prior_installation_receipt_sha256": h(receipt), "host_id": "host-00000001", "qualification_launcher_evidence_sha256": h(launcher), "fault_matrix_evidence_sha256": h(fault), "canonical_policy_record_sha256": h(policy), "qualification_launcher_status": "PASS", "fault_matrix_status": "PASS"}
    assert verify_phase_transition(installation_phase="POLICY_ACTIVATED", active_lock_path=lock, authorization={"canonical_policy_status": "APPROVED"}, phase_authorization=phase, canonical_policy_record_path=policy, prior_receipt_path=receipt, qualification_launcher_evidence_path=launcher, fault_matrix_evidence_path=fault, load_json=lambda p, l: json.loads(p.read_text()))["installation_id"] == "install-0001"
    for field in ["prior_manifest_sha256", "prior_lock_sha256", "prior_installation_receipt_sha256", "host_id", "qualification_launcher_evidence_sha256", "fault_matrix_evidence_sha256", "canonical_policy_record_sha256"]:
        bad = dict(phase); bad[field] = "0" * 64 if field != "host_id" else "wrong-host"
        with pytest.raises(SystemExit): verify_phase_transition(installation_phase="POLICY_ACTIVATED", active_lock_path=lock, authorization={"canonical_policy_status": "APPROVED"}, phase_authorization=bad, canonical_policy_record_path=policy, prior_receipt_path=receipt, qualification_launcher_evidence_path=launcher, fault_matrix_evidence_path=fault, load_json=lambda p, l: json.loads(p.read_text()))


def test_f02_f04_twenty_process_same_sequence_exactly_one_advances(tmp_path: Path):
    _, priv, _ = keypair(tmp_path, "ledger")
    anchor = copy_anchor(tmp_path)
    worker = tmp_path / "worker.py"
    worker.write_text(textwrap.dedent(f"""
        import sys
        from pathlib import Path
        sys.path.insert(0,{str(ROOT/'trusted-installation')!r})
        from v9_transaction import AuthorizationTransactionStore,InstallerGlobalLock
        i=sys.argv[1]; root=Path({str(tmp_path)!r})
        try:
            with InstallerGlobalLock(root/'global.lock'):
                s=AuthorizationTransactionStore(root/'ledger',str(root/'anchor'),root/'ledger.private.pem','ledger-key-0001','journal-concurrency')
                s.reserve({{'authorization_id':'auth-'+i.zfill(8),'nonce':'nonce-'+i.zfill(8),'sequence':1}},'a'*64)
            print('SUCCESS')
        except BaseException as e: print('FAIL:'+str(e))
    """)); worker.chmod(0o444)
    procs = [subprocess.Popen([sys.executable, str(worker), str(i)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for i in range(20)]
    outputs = [p.communicate(timeout=30)[0].strip() for p in procs]
    assert outputs.count("SUCCESS") == 1, outputs
    store = AuthorizationTransactionStore(tmp_path / "ledger", str(anchor), priv, "ledger-key-0001", "journal-concurrency")
    assert store._local_head().authorization_sequence == 1
    store.recover()


def test_f04_rollback_delete_restore_and_pending_recovery_fail_closed(tmp_path: Path, monkeypatch):
    _, priv, _ = keypair(tmp_path, "ledger")
    anchor = copy_anchor(tmp_path)
    store = AuthorizationTransactionStore(tmp_path / "ledger", str(anchor), priv, "ledger-key-0001", "journal-replay")
    r = store.reserve({"authorization_id": "auth-00000001", "nonce": "nonce-00000001", "sequence": 1}, "a" * 64)
    backup = tmp_path / "backup"; shutil.copytree(tmp_path / "ledger", backup)
    store.complete(r, "CONSUMED", "install-0001")
    shutil.rmtree(tmp_path / "ledger"); shutil.copytree(backup, tmp_path / "ledger")
    with pytest.raises(SystemExit, match="mismatch|rollback"):
        AuthorizationTransactionStore(tmp_path / "ledger", str(anchor), priv, "ledger-key-0001", "journal-replay").recover()

    tmp2 = tmp_path / "before-anchor"; tmp2.mkdir(); anchor2 = copy_anchor(tmp2); _, priv2, _ = keypair(tmp2, "ledger")
    s2 = AuthorizationTransactionStore(tmp2 / "ledger", str(anchor2), priv2, "ledger-key-0001", "journal-before")
    monkeypatch.setattr(s2.anchor, "compare_and_publish", lambda p, n: (_ for _ in ()).throw(SystemExit("injected-before-anchor")))
    with pytest.raises(SystemExit): s2.reserve({"authorization_id": "auth-00000002", "nonce": "nonce-00000002", "sequence": 1}, "b" * 64)
    assert AuthorizationTransactionStore(tmp2 / "ledger", str(anchor2), priv2, "ledger-key-0001", "journal-before").recover().startswith("ROLLED_BACK")

    tmp3 = tmp_path / "after-anchor"; tmp3.mkdir(); anchor3 = copy_anchor(tmp3); _, priv3, _ = keypair(tmp3, "ledger")
    import v9_transaction as module
    original = module.atomic_write
    def crash_record(path, data, mode=0o400):
        if Path(path).parent.name == "records": raise SystemExit("injected-after-anchor")
        return original(path, data, mode)
    monkeypatch.setattr(module, "atomic_write", crash_record)
    s3 = AuthorizationTransactionStore(tmp3 / "ledger", str(anchor3), priv3, "ledger-key-0001", "journal-after")
    with pytest.raises(SystemExit): s3.reserve({"authorization_id": "auth-00000003", "nonce": "nonce-00000003", "sequence": 1}, "c" * 64)
    monkeypatch.setattr(module, "atomic_write", original)
    recovered = AuthorizationTransactionStore(tmp3 / "ledger", str(anchor3), priv3, "ledger-key-0001", "journal-after").recover()
    assert recovered == "COMPLETED_ANCHORED_PENDING_TRANSACTION"


def lifecycle_transition(tmp: Path, sequence: int, previous, epoch: str, stores: dict, signers):
    now = datetime.now(timezone.utc)
    unsigned = {"format_version": "1.0", "transition_kind": "AZPR_V9_ATOMIC_TRUST_EPOCH_TRANSITION", "transition_id": f"transition-{sequence:08d}", "sequence": sequence, "nonce": f"nonce-{sequence:08d}", "issued_at": now.isoformat(), "expires_at": (now + timedelta(days=1)).isoformat(), "previous_epoch_id": previous, "new_epoch_id": epoch, "stores": stores}
    sigs = [{"key_id": kid, "signature": base64.b64encode(key.sign(lifecycle_canonical(unsigned))).decode()} for kid, key in signers]
    return {**unsigned, "signatures": sigs}


def test_f07_atomic_trust_epoch_and_interruption_recovery(tmp_path: Path):
    a, _, apub = keypair(tmp_path, "authorizer"); b, _, bpub = keypair(tmp_path, "security")
    keyring = tmp_path / "keyring.json"
    write_json(keyring, {"format_version": "1.0", "keys": [
        {"key_id": "lifecycle-authorizer-0001", "signer_id": "operator-0001", "roles": ["key-lifecycle-authorizer"], "public_key_pem": apub.read_text()},
        {"key_id": "lifecycle-security-0001", "signer_id": "security-0001", "roles": ["security-approver"], "public_key_pem": bpub.read_text()}]})
    stores = {}
    for name in TRUST_STORES:
        p = tmp_path / f"store-{name}"; p.write_bytes(name.encode()); p.chmod(0o444)
        stores[name] = {"path": str(p), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
    anchor = copy_anchor(tmp_path)
    t1 = lifecycle_transition(tmp_path, 1, None, "epoch-00000001", stores, [("lifecycle-authorizer-0001", a), ("lifecycle-security-0001", b)])
    pointer = TrustEpochStore(tmp_path / "epochs-state", str(anchor), "epoch-journal").apply(t1, keyring)
    assert pointer["epoch_id"] == "epoch-00000001"
    for name in TRUST_STORES: assert resolve_active_store(tmp_path / "epochs-state", name).read_bytes() == name.encode()

    before = tmp_path / "before"; before.mkdir(); anchor2 = copy_anchor(before)
    t_before = lifecycle_transition(before, 1, None, "epoch-before-0001", stores, [("lifecycle-authorizer-0001", a), ("lifecycle-security-0001", b)])
    def fail_before(point):
        if point == "after_pending": raise RuntimeError("fault")
    with pytest.raises(RuntimeError): TrustEpochStore(before / "state", str(anchor2), "before-journal", fail_before).apply(t_before, keyring)
    assert TrustEpochStore(before / "state", str(anchor2), "before-journal").recover() == "ROLLED_BACK_UNANCHORED_EPOCH"

    after = tmp_path / "after"; after.mkdir(); anchor3 = copy_anchor(after)
    t_after = lifecycle_transition(after, 1, None, "epoch-after-00001", stores, [("lifecycle-authorizer-0001", a), ("lifecycle-security-0001", b)])
    def fail_after(point):
        if point == "after_anchor": raise RuntimeError("fault")
    with pytest.raises(RuntimeError): TrustEpochStore(after / "state", str(anchor3), "after-journal", fail_after).apply(t_after, keyring)
    assert TrustEpochStore(after / "state", str(anchor3), "after-journal").recover() == "ACTIVATED_ANCHORED_EPOCH"
    active = after / "state" / "active-epoch.json"; saved = active.read_bytes(); active.unlink()
    with pytest.raises(SystemExit, match="pointer rollback"):
        TrustEpochStore(after / "state", str(anchor3), "after-journal").recover()
    active.write_bytes(saved); active.chmod(0o400)


def test_installer_exact_enforcing_order_and_phase_not_policy_derived():
    source = (ROOT / "trusted-installation" / "install.py").read_text()
    lock = source.index("InstallerGlobalLock(GLOBAL_INSTALLER_LOCK).acquire()")
    preflight = source.index("qualification=_qualification_preflight(args)")
    recovery = source.index("recovered=recover_activation_state()")
    reserve = source.index("\n _reserve_authorization(qualification)", recovery)
    complete = source.index("_complete_authorization(qualification,'CONSUMED'")
    assert lock < preflight < recovery < reserve < complete
    assert "installation_phase=qualification['authorization']['installation_phase']" in source
    assert "if qualification['authorization']['canonical_policy_status']=='APPROVED'" not in source
    assert "verify_complete_artifact_bindings" in source and "verify_bootstrap_roots" in source
    assert "receipt['probe_envelopes_manifest_sha256']!=sha" in source
    for bound_component in ("mount_binary", "umount_binary", "qualification_verifier", "key_lifecycle_state", "probe_envelopes_manifest"):
        assert f"'{bound_component}':" in source
    assert "AuthorizationTransactionStore" in source
