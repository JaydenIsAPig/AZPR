from __future__ import annotations

import base64
import hashlib
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "operator-tools"))
sys.path.insert(0, str(ROOT / "trusted-installation"))
from v10_1_host_trust import HOST_AUTHORITY_KEY_NAME, HOST_MANIFEST_NAME, ROOT_FILENAMES, _load_host_qualification_context, canonical as host_canonical
from v10_probe_boundary import TARGETS, REQUIRED_OBSERVATION_NAMES, canonical, load_approved_probe_authority, sha_bytes


def write_bytes(path: Path, data: bytes, mode: int = 0o444) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not path.is_symlink():
        path.chmod(0o600)
    path.write_bytes(data)
    path.chmod(mode)


def write_json(path: Path, value: dict, mode: int = 0o444) -> None:
    write_bytes(path, (json.dumps(value, indent=2, sort_keys=True) + "\n").encode(), mode)


def keypair(directory: Path, name: str, public_mode: int = 0o444):
    private = Ed25519PrivateKey.generate()
    private_path = directory / f"{name}.private.pem"
    public_path = directory / f"{name}.public.pem"
    write_bytes(private_path, private.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()), 0o400)
    write_bytes(public_path, private.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo), public_mode)
    return private, private_path, public_path


def _signer_source(root: Path, private_path: Path) -> bytes:
    template = r'''#!__PYTHON__
import base64, hashlib, json, sys
from pathlib import Path
sys.path.insert(0, __TOOLS__)
from cryptography.hazmat.primitives import serialization
from v10_1_host_trust import _load_host_qualification_context
from v10_probe_boundary import canonical, load_approved_probe_authority
ROOT=Path(__HOST_ROOT__); OWNER=__OWNER__; PRIVATE=Path(__PRIVATE__)
if len(sys.argv)!=2 or sys.argv[1]!='sign-receipt': raise SystemExit('unsupported')
r=json.load(sys.stdin); u=r['unsigned_receipt']
c=_load_host_qualification_context(ROOT,owner_uid=OWNER,expected_host_id=u['host_id'],expected_candidate_archive_sha256=u['candidate_archive_sha256'],expected_challenge_sha256=u['challenge_sha256'])
a=load_approved_probe_authority(host_context=c,expected_host_id=u['host_id'],expected_candidate_archive_sha256=u['candidate_archive_sha256'],expected_challenge_sha256=u['challenge_sha256'])
if r.get('host_qualification_roots_manifest_sha256')!=c.manifest_sha256: raise SystemExit('host root mismatch')
if r.get('qualification_trust_binding')!=a.trust_binding or r.get('qualification_trust_binding_sha256')!=a.trust_binding_sha256: raise SystemExit('binding mismatch')
if r.get('signer_id')!=c.external_signer_id or r.get('signer_identity_sha256')!=c.external_signer_identity_sha256: raise SystemExit('signer mismatch')
if hashlib.sha256(canonical(u)).hexdigest()!=r.get('unsigned_receipt_sha256'): raise SystemExit('receipt hash mismatch')
k=serialization.load_pem_private_key(PRIVATE.read_bytes(),password=None)
s=dict(u); s['signature']=base64.b64encode(k.sign(canonical(u))).decode()
print(json.dumps({'format_version':'1.1','response_kind':'AZPR_V10_1_EXTERNAL_RECEIPT_SIGNING_RESPONSE','request_nonce':r['request_nonce'],'signer_id':c.external_signer_id,'signer_identity_sha256':c.external_signer_identity_sha256,'host_qualification_roots_manifest_sha256':c.manifest_sha256,'qualification_trust_binding_sha256':a.trust_binding_sha256,'unsigned_receipt_sha256':r['unsigned_receipt_sha256'],'signed_receipt':s},sort_keys=True))
'''
    text = (template
        .replace('__PYTHON__', str(Path(sys.executable).resolve()))
        .replace('__TOOLS__', repr(str(ROOT / 'operator-tools')))
        .replace('__HOST_ROOT__', repr(str(root)))
        .replace('__OWNER__', str(os.geteuid()))
        .replace('__PRIVATE__', repr(str(private_path))))
    return text.encode()



def _anchor_client_source(private_path: Path, *, expected_sequence: int = 11) -> bytes:
    template = r'''#!__PYTHON__
import base64, json, sys
from datetime import datetime, timezone
from pathlib import Path
from cryptography.hazmat.primitives import serialization
PRIVATE=Path(__PRIVATE__); EXPECTED_SEQUENCE=__SEQUENCE__
def canonical(value): return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
if len(sys.argv)!=2 or sys.argv[1]!='verify-host-root-head': raise SystemExit('unsupported')
r=json.load(sys.stdin)
if r.get('format_version')!='1.0' or r.get('request_kind')!='AZPR_V10_1_VERIFY_HOST_ROOT_HEAD': raise SystemExit('request identity')
if r.get('host_qualification_roots_manifest_sequence')!=EXPECTED_SEQUENCE: raise SystemExit('stale or forked head')
u={'format_version':'1.0','response_kind':'AZPR_V10_1_HOST_ROOT_HEAD_RESPONSE','request_nonce':r['request_nonce'],'anchor_id':r['anchor_id'],'host_id':r['host_id'],'candidate_archive_sha256':r['candidate_archive_sha256'],'challenge_sha256':r['challenge_sha256'],'host_qualification_roots_manifest_sha256':r['host_qualification_roots_manifest_sha256'],'host_qualification_roots_manifest_sequence':r['host_qualification_roots_manifest_sequence'],'observed_at':datetime.now(timezone.utc).isoformat(),'previous_anchor_head_sha256':'e'*64}
k=serialization.load_pem_private_key(PRIVATE.read_bytes(),password=None)
print(json.dumps({**u,'signature':base64.b64encode(k.sign(canonical(u))).decode()},sort_keys=True))
'''
    return (template.replace('__PYTHON__', str(Path(sys.executable).resolve()))
        .replace('__PRIVATE__', repr(str(private_path)))
        .replace('__SEQUENCE__', str(expected_sequence))).encode()

def build_host_fixture(
    tmp_path: Path,
    *,
    network_mode: str = "DENY_ALL",
    maximum_age_seconds: int = 60,
    trust_issued_offset: timedelta = timedelta(minutes=-10),
    revocation_issued_offset: timedelta = timedelta(minutes=-5),
    attestation_signed: bool = True,
    executable_digest_override: str | None = None,
    probe_key_role: str = "qualification-probe-service",
    revoked_probe_keys: list[str] | None = None,
) -> dict:
    root = tmp_path / "host-root"
    root.mkdir(parents=True, mode=0o700)
    signer_private_dir = tmp_path / "signer-private"
    signer_private_dir.mkdir(mode=0o700)
    now = datetime.now(timezone.utc)
    host_id = "host-v10-1-test-0001"
    candidate = "a" * 64
    challenge = "b" * 64
    service_id = "probe-service-v10-1-0001"
    attestor_id = "probe-attestor-v10-1-0001"
    signer_id = "receipt-signer-v10-1-0001"

    host_authority, _, host_authority_pub = keypair(signer_private_dir, "host-authority")
    trust_authority, _, trust_authority_pub = keypair(signer_private_dir, "trust-authority")
    probe_private, _, probe_public = keypair(signer_private_dir, "probe")
    attestor_private, _, attestor_public = keypair(signer_private_dir, "attestor")
    receipt_private, receipt_private_path, receipt_public = keypair(signer_private_dir, "receipt")
    anchor_private, anchor_private_path, anchor_public = keypair(signer_private_dir, "host-root-anchor")

    paths = {name: root / filename for name, filename in ROOT_FILENAMES.items()}
    write_bytes(root / HOST_AUTHORITY_KEY_NAME, host_authority_pub.read_bytes(), 0o444)
    write_bytes(paths["qualification_trust_authority_public_key"], trust_authority_pub.read_bytes(), 0o444)
    write_bytes(paths["qualification_receipt_signing_public_key"], receipt_public.read_bytes(), 0o444)
    anchor_client = _anchor_client_source(anchor_private_path, expected_sequence=11)
    write_bytes(paths["host_root_anchor_client"], anchor_client, 0o555)
    write_json(paths["host_root_anchor_identity"], {
        "format_version": "1.0", "identity_kind": "AZPR_V10_1_HOST_ROOT_ANCHOR_IDENTITY",
        "anchor_id": "host-root-anchor-v10-1-0001",
        "anchor_client_sha256": hashlib.sha256(anchor_client).hexdigest(),
        "anchor_public_key_pem": anchor_public.read_text(), "host_id": host_id,
        "candidate_archive_sha256": candidate, "not_before": (now - timedelta(days=1)).isoformat(),
        "not_after": (now + timedelta(days=7)).isoformat(),
    })

    service_executable = b"#!/bin/sh\nexit 0\n"
    write_bytes(paths["probe_service_executable"], service_executable, 0o555)
    service_digest = hashlib.sha256(service_executable).hexdigest()
    launcher_digest = "c" * 64
    runtime_digest = "d" * 64

    write_json(paths["probe_keyring"], {
        "format_version": "1.0", "keyring_kind": "AZPR_V10_1_APPROVED_PROBE_KEYRING",
        "keyring_id": "probe-keyring-v10-1-0001", "sequence": 5, "service_id": service_id,
        "keys": [{"key_id": "probe-key-v10-1-0001", "signer_id": service_id, "roles": [probe_key_role],
                  "public_key_pem": probe_public.read_text(), "not_before": (now - timedelta(days=1)).isoformat(),
                  "not_after": (now + timedelta(days=7)).isoformat()}],
    })
    write_json(paths["probe_attestor_keyring"], {
        "format_version": "1.0", "keyring_kind": "AZPR_V10_1_PROBE_ATTESTOR_KEYRING",
        "keyring_id": "attestor-keyring-v10-1-0001", "sequence": 7, "service_id": attestor_id,
        "keys": [{"key_id": "attestor-key-v10-1-0001", "signer_id": attestor_id, "roles": ["probe-service-attestor"],
                  "public_key_pem": attestor_public.read_text(), "not_before": (now - timedelta(days=1)).isoformat(),
                  "not_after": (now + timedelta(days=7)).isoformat()}],
    })
    boundary = {
        "rootless": True, "no_secrets": True, "host_mounts": False, "daemon_sockets": False,
        "pid_namespace": True, "mount_namespace": True, "cgroup_v2": True, "disposable": True,
        "run_as_uid": 10001, "run_as_gid": 10001, "network_mode": network_mode,
    }
    write_json(paths["probe_policy"], {
        "format_version": "1.1", "policy_kind": "AZPR_V10_1_PROBE_POLICY", "policy_version": "10.1.1",
        "host_id": host_id, "candidate_archive_sha256": candidate, "challenge_sha256": challenge,
        "probe_service_id": service_id, "required_targets": list(TARGETS), "required_boundary": boundary,
        "required_observations": list(REQUIRED_OBSERVATION_NAMES), "maximum_envelope_age_seconds": maximum_age_seconds,
    })
    write_json(paths["probe_service_identity"], {
        "format_version": "1.1", "identity_kind": "AZPR_V10_1_PROBE_SERVICE_IDENTITY", "service_id": service_id,
        "service_binary_sha256": executable_digest_override or service_digest,
        "deployment_identity": "dedicated-no-secret-probe-boundary-v10.1",
        "launcher_identity_sha256": launcher_digest, "runtime_configuration_sha256": runtime_digest,
    })
    write_json(paths["probe_revocation_state"], {
        "format_version": "1.0", "revocation_kind": "AZPR_V10_1_PROBE_KEY_REVOCATIONS", "sequence": 5,
        "service_id": service_id, "issued_at": (now + revocation_issued_offset).isoformat(),
        "revoked_key_ids": revoked_probe_keys or [],
    })
    write_json(paths["probe_attestor_revocation_state"], {
        "format_version": "1.0", "revocation_kind": "AZPR_V10_1_PROBE_ATTESTOR_REVOCATIONS", "sequence": 7,
        "service_id": attestor_id, "issued_at": (now + revocation_issued_offset).isoformat(), "revoked_key_ids": [],
    })

    identity_sha = hashlib.sha256(paths["probe_service_identity"].read_bytes()).hexdigest()
    att_unsigned = {
        "format_version": "1.1", "attestation_kind": "AZPR_V10_1_PROBE_SERVICE_ATTESTATION",
        "attestation_id": "probe-attestation-v10-1-0001", "service_id": service_id,
        "service_identity_sha256": identity_sha, "service_executable_sha256": service_digest,
        "launcher_identity_sha256": launcher_digest, "runtime_configuration_sha256": runtime_digest,
        "host_id": host_id, "candidate_archive_sha256": candidate, "challenge_sha256": challenge,
        "issued_at": (now - timedelta(minutes=2)).isoformat(), "expires_at": (now + timedelta(days=2)).isoformat(),
        "attestor_id": attestor_id, "attestor_key_id": "attestor-key-v10-1-0001", "attestor_role": "probe-service-attestor",
    }
    att_signature = base64.b64encode(attestor_private.sign(canonical(att_unsigned))).decode() if attestation_signed else base64.b64encode(b"x" * 64).decode()
    write_json(paths["probe_service_attestation"], {**att_unsigned, "signature": att_signature})

    signer_source = _signer_source(root, receipt_private_path)
    write_bytes(paths["external_signer_client"], signer_source, 0o555)
    write_json(paths["external_signer_identity"], {
        "format_version": "1.0", "identity_kind": "AZPR_V10_1_EXTERNAL_RECEIPT_SIGNER_IDENTITY",
        "signer_id": signer_id, "signer_client_sha256": hashlib.sha256(signer_source).hexdigest(),
        "receipt_signing_public_key_sha256": hashlib.sha256(receipt_public.read_bytes()).hexdigest(),
        "host_id": host_id, "candidate_archive_sha256": candidate,
        "not_before": (now - timedelta(days=1)).isoformat(), "not_after": (now + timedelta(days=7)).isoformat(),
    })

    trust_issued = now + trust_issued_offset
    trust_unsigned = {
        "format_version": "1.1", "trust_manifest_kind": "AZPR_V10_1_QUALIFICATION_TRUST_ROOTS",
        "trust_manifest_id": "qualification-trust-v10-1-0001", "sequence": 9,
        "issued_at": trust_issued.isoformat(), "not_before": (now - timedelta(days=1)).isoformat(),
        "not_after": (now + timedelta(days=8)).isoformat(), "host_id": host_id,
        "candidate_archive_sha256": candidate, "challenge_sha256": challenge,
        "probe_service_id": service_id, "probe_attestor_id": attestor_id,
        "probe_keyring_sha256": hashlib.sha256(paths["probe_keyring"].read_bytes()).hexdigest(),
        "probe_policy_sha256": hashlib.sha256(paths["probe_policy"].read_bytes()).hexdigest(),
        "probe_service_identity_sha256": hashlib.sha256(paths["probe_service_identity"].read_bytes()).hexdigest(),
        "probe_service_attestation_sha256": hashlib.sha256(paths["probe_service_attestation"].read_bytes()).hexdigest(),
        "probe_revocation_state_sha256": hashlib.sha256(paths["probe_revocation_state"].read_bytes()).hexdigest(),
        "probe_attestor_keyring_sha256": hashlib.sha256(paths["probe_attestor_keyring"].read_bytes()).hexdigest(),
        "probe_attestor_revocation_state_sha256": hashlib.sha256(paths["probe_attestor_revocation_state"].read_bytes()).hexdigest(),
        "probe_service_executable_sha256": service_digest,
        "external_signer_identity_sha256": hashlib.sha256(paths["external_signer_identity"].read_bytes()).hexdigest(),
        "qualification_receipt_signing_public_key_sha256": hashlib.sha256(receipt_public.read_bytes()).hexdigest(),
        "signer_key_id": "qualification-trust-authority-v10-1",
    }
    write_json(paths["qualification_trust_manifest"], {**trust_unsigned, "signature": base64.b64encode(trust_authority.sign(canonical(trust_unsigned))).decode()})

    roots = {name: {"filename": ROOT_FILENAMES[name], "sha256": hashlib.sha256(paths[name].read_bytes()).hexdigest()} for name in ROOT_FILENAMES}
    host_unsigned = {
        "format_version": "1.0", "manifest_kind": "AZPR_V10_1_HOST_QUALIFICATION_ROOTS",
        "manifest_id": "host-qualification-roots-v10-1-0001", "sequence": 11,
        "issued_at": (now - timedelta(minutes=1)).isoformat(), "not_before": (now - timedelta(days=1)).isoformat(),
        "not_after": (now + timedelta(days=8)).isoformat(), "host_id": host_id,
        "candidate_archive_sha256": candidate, "challenge_sha256": challenge,
        "minimum_trust_sequence": 9, "minimum_probe_revocation_sequence": 5,
        "minimum_attestor_revocation_sequence": 7, "external_signer_id": signer_id,
        "external_signer_identity_sha256": hashlib.sha256(paths["external_signer_identity"].read_bytes()).hexdigest(),
        "receipt_signing_key_id": "receipt-key-v10-1", "roots": roots,
        "signer_key_id": "host-qualification-authority-v10-1",
    }
    write_json(root / HOST_MANIFEST_NAME, {**host_unsigned, "signature": base64.b64encode(host_authority.sign(host_canonical(host_unsigned))).decode()})

    root.chmod(0o500)
    context = _load_host_qualification_context(root, owner_uid=os.geteuid(), expected_host_id=host_id,
        expected_candidate_archive_sha256=candidate, expected_challenge_sha256=challenge)
    authority = load_approved_probe_authority(host_context=context, expected_host_id=host_id,
        expected_candidate_archive_sha256=candidate, expected_challenge_sha256=challenge)
    return {
        "root": root, "paths": paths, "context": context, "authority": authority, "host_id": host_id,
        "candidate": candidate, "challenge": challenge, "service_id": service_id, "attestor_id": attestor_id,
        "probe_private": probe_private, "receipt_private": receipt_private, "policy_boundary": boundary,
        "maximum_age_seconds": maximum_age_seconds,
    }


def signed_envelope(fixture: dict, role: str, target_sha: str, *, completed_offset_seconds: int = -1, boundary: dict | None = None) -> dict:
    now = datetime.now(timezone.utc)
    completed = now + timedelta(seconds=completed_offset_seconds)
    binding = fixture["authority"].trust_binding
    unsigned = {
        "format_version": "1.1", "envelope_kind": "AZPR_V10_1_NO_SECRET_PROBE_RESULT",
        "target_role": role, "target_sha256": target_sha, "host_id": binding["host_id"],
        "candidate_archive_sha256": binding["candidate_archive_sha256"], "challenge_sha256": binding["challenge_sha256"],
        "qualification_trust_manifest_sha256": binding["qualification_trust_manifest_sha256"],
        "probe_keyring_sha256": binding["probe_keyring_sha256"], "probe_policy_sha256": binding["probe_policy_sha256"],
        "probe_service_identity_sha256": binding["probe_service_identity_sha256"],
        "probe_service_attestation_sha256": binding["probe_service_attestation_sha256"],
        "probe_revocation_state_sha256": binding["probe_revocation_state_sha256"],
        "probe_attestor_keyring_sha256": binding["probe_attestor_keyring_sha256"],
        "probe_attestor_revocation_state_sha256": binding["probe_attestor_revocation_state_sha256"],
        "probe_service_executable_sha256": binding["probe_service_executable_sha256"],
        "boundary": boundary or fixture["policy_boundary"],
        "observations": {x: True for x in REQUIRED_OBSERVATION_NAMES}, "exit_code": 0,
        "started_at": (completed - timedelta(seconds=1)).isoformat(), "completed_at": completed.isoformat(),
        "signer_key_id": "probe-key-v10-1-0001", "signer_service_id": fixture["service_id"],
    }
    return {**unsigned, "signature": base64.b64encode(fixture["probe_private"].sign(canonical(unsigned))).decode()}


def build_probe_manifest(fixture: dict, directory: Path, *, completed_offset_seconds: int = -1, boundary: dict | None = None):
    directory.mkdir(parents=True, exist_ok=True)
    hashes = {name: hashlib.sha256(name.encode()).hexdigest() for name in TARGETS}
    rows = {}
    for name in TARGETS:
        path = directory / f"{name}.json"
        write_json(path, signed_envelope(fixture, name, hashes[name], completed_offset_seconds=completed_offset_seconds, boundary=boundary))
        rows[name] = {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    b = fixture["authority"].trust_binding
    manifest = {
        "format_version": "1.1", "manifest_kind": "AZPR_V10_1_PROBE_ENVELOPES_MANIFEST", "artifact_set_version": "2.1",
        "issued_at": datetime.now(timezone.utc).isoformat(), "host_id": b["host_id"], "candidate_archive_sha256": b["candidate_archive_sha256"],
        "challenge_sha256": b["challenge_sha256"], "qualification_trust_binding_sha256": fixture["authority"].trust_binding_sha256,
        "qualification_trust_manifest_sha256": b["qualification_trust_manifest_sha256"], "probe_keyring_sha256": b["probe_keyring_sha256"],
        "probe_policy_sha256": b["probe_policy_sha256"], "probe_service_identity_sha256": b["probe_service_identity_sha256"],
        "probe_service_attestation_sha256": b["probe_service_attestation_sha256"], "probe_revocation_state_sha256": b["probe_revocation_state_sha256"],
        "probe_attestor_keyring_sha256": b["probe_attestor_keyring_sha256"], "probe_attestor_revocation_state_sha256": b["probe_attestor_revocation_state_sha256"],
        "probe_service_executable_sha256": b["probe_service_executable_sha256"], "envelopes": rows,
        "aggregate_sha256": sha_bytes(canonical({name: rows[name]["sha256"] for name in TARGETS})),
    }
    path = directory / "manifest.json"
    write_json(path, manifest)
    return path, hashes
