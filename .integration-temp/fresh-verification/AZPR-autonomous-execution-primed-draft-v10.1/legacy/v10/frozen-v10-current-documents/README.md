# AZPR v10 Corrective Development Candidate

Status: **READY FOR INDEPENDENT V10 SOURCE REASSESSMENT ONLY**.

This unsigned development candidate corrects the source-level v9 trust-root, bootstrap-path, non-root-verifier, packaging, documentation, and regression-test findings. It does not authorize trusted installation, Prompt 004, canonical-policy activation, roadmap generation or promotion, numbered-prompt execution, provider access, credentials, or customer data.

## Required verification

Run from a fresh, read-only extraction as a dedicated unprivileged reviewer:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 VERIFY-V10-CANDIDATE.py --fresh-extraction
```

A PASS preserves these mandatory dispositions:

- `pre_autonomous_staging: FAIL`
- `semi_autonomous_codex_staging_ready: false`
- `trusted_pre_autonomous_installation_ready: false`
- `safe_for_unattended_execution_now: false`

The next permissible event is independent source reassessment. Real organization signing and dedicated-host qualification remain later gates.
