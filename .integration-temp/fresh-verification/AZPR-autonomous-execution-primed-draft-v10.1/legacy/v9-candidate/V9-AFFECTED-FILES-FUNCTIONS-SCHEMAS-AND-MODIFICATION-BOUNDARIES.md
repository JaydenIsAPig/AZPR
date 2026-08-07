# AZPR v9 Affected Files, Functions, Schemas, and Modification Boundaries

```json
{
  "safe_for_unattended_execution_now": false,
  "trusted_pre_autonomous_installation_ready": false
}
```

## Approved implementation surface

The handoff permitted bounded edits in `trusted-installation/`, qualification/probe/anchor/signing/evidence/key-lifecycle operator tools, installation/qualification schemas, narrowly required production loader checks, tests, verifiers, and v9 reports. The prompt archive, 41 prompt sources, governing DOCX source, independent consultation files, active-policy paths, and roadmap paths were prohibited.

## Security-critical changed paths

- `external-capability-runner/trusted_installation.py`
- `trusted-controller/trusted_installation.py`
- `trusted-validation-runner/trusted_installation.py`
- `trusted-installation/install.py`
- `trusted-installation/v9_binding.py`
- `trusted-installation/v9_transaction.py`
- `operator-tools/apply_key_lifecycle_transition_v9.py`
- `operator-tools/v9_evidence_derivation.py`
- `operator-tools/v9_external_signer_client.py`
- `operator-tools/v9_external_signer_reference.py`
- `operator-tools/v9_file_anchor_reference.py`
- `operator-tools/v9_probe_boundary.py`
- `operator-tools/verify_v9_cleanroom_prerequisites.py`
- `repository-overlay/automation/schemas/cleanroom-qualification-receipt-v9.schema.json`
- `repository-overlay/automation/schemas/external-receipt-signing-request-v9.schema.json`
- `repository-overlay/automation/schemas/external-receipt-signing-response-v9.schema.json`
- `repository-overlay/automation/schemas/host-bootstrap-roots-v9.schema.json`
- `repository-overlay/automation/schemas/installation-receipt.schema.json`
- `repository-overlay/automation/schemas/key-lifecycle-transition-v9.schema.json`
- `repository-overlay/automation/schemas/qualification-installation-authorization-v9.schema.json`
- `repository-overlay/automation/schemas/qualification-phase-transition-authorization-v9.schema.json`
- `repository-overlay/automation/schemas/qualification-probe-envelopes-manifest-v9.schema.json`
- `repository-overlay/automation/schemas/qualification-probe-result-envelope-v9.schema.json`
- `repository-overlay/automation/schemas/qualification-raw-evidence-v9.schema.json`
- `repository-overlay/automation/schemas/qualified-artifact-inputs-v9.schema.json`
- `repository-overlay/automation/schemas/trust-store-epoch-v9.schema.json`
- `repository-overlay/automation/schemas/trusted-installation.schema.json`
- `tests/test_v9_security_closures.py`

## Primary functions/classes

- `InstallerGlobalLock`, `AnchorClient`, and `AuthorizationTransactionStore`: serialization, compare-and-publish, signed records, recovery.
- `_qualification_preflight`, `_reserve_authorization`, `_complete_authorization`: enforcing call path in the privileged installer.
- `verify_complete_artifact_bindings`, `verify_bootstrap_roots`, `verify_phase_transition`: exact binding and phase invariants.
- `verify_probe_manifest`/`verify_probe_envelope`: signed no-secret envelope import without target execution.
- `request_external_signature`: authenticated external signing request/response with public-key verification.
- `derive_measurements`/`verify_report_derivation`: deterministic raw-evidence recomputation.
- `TrustEpochStore.apply`, `recover`, and `resolve_active_store`: atomic ten-store epoch transition.

## Prohibited surfaces confirmed unchanged

- All `repository-overlay/automation/numbered/*.md` and `appendices/*.md` prompt bytes.
- Embedded prompt archive identity.
- No `roadmap.json`, `roadmap.proposed.json`, active canonical-policy Markdown, or active policy section map.
- Consultation source files remain outside the implementation tree and unmodified.

No privileged installer or real signing/anchor/provider operation was executed.
