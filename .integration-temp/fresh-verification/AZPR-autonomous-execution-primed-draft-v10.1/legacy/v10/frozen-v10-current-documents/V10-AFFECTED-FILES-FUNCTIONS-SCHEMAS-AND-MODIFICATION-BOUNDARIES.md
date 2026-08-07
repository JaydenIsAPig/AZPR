# V10 Affected Files, Functions, Schemas, and Modification Boundaries

## Approved and actually changed security source

- `operator-tools/v10_trusted_io.py`
- `operator-tools/v10_probe_boundary.py`
- `operator-tools/v10_external_signer_client.py`
- `operator-tools/v10_external_signer_reference.py`
- `operator-tools/verify_v10_cleanroom_prerequisites.py`
- `trusted-installation/v10_binding.py`
- `trusted-installation/install.py`
- 15 v10 schemas under `repository-overlay/automation/schemas/`
- `tests/test_v10_security_closures.py`
- `VERIFY-V10-CANDIDATE.py`
- `V10-RELEASE-TEST-CATALOG.json`
- current v10 reports, index, manifests, packaging, and verification records

## Principal functions and boundaries

- trusted file resolution: `read_trusted_regular`, `load_trusted_json`;
- probe authority: `load_approved_probe_authority`, `verify_probe_envelope`, `verify_probe_manifest`;
- external signer client/reference: `request_external_signature`, signer `main`;
- artifact binding/bootstrap/phase: `verify_versioned_artifact_bindings`, `verify_bootstrap_roots`, `verify_phase_transition`;
- verifier: `verify_inputs_and_build`, release `run_catalog`, schema/prompt/document/manifest checks;
- installer: `_qualification_preflight`, `_reserve_authorization`, `_complete_authorization`, `main`.

## Prohibited and unchanged

- all 38 numbered prompt files;
- Appendices A–C;
- embedded prompt archive bytes;
- supplied Master Operating Prompt bytes;
- independent v9 reports;
- active canonical policy and promoted roadmap (both absent).

## Codex boundary

No autonomous Codex execution was used to approve trust roots, threat model, acceptance oracles, closure status, or release promotion. Any future Codex assistance must remain restricted to an approved path list and human-reviewed diffs.
