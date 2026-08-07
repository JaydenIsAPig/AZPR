# AZPR v8 Promotion Gates

```json
{"safe_for_unattended_execution_now": false, "trusted_pre_autonomous_installation_ready": false}
```

## Gate 1 — Independent source reassessment

Freeze exact v8 hashes. An independent security consultant must reproduce P0/P1 tests and report zero open Critical/High implementation findings.

## Gate 2 — Dedicated-host qualification

Produce real signed supply-chain, host, isolation, cgroup/namespace, quota, LSM, key-custody, remote-anchor, installer-fault and isolated-target evidence. The v8 semantic verifier must reproduce the conclusions and issue a still-blocked receipt.

## Gate 3 — One-use installation authorization

Independent installation-authorization roles must bind the exact candidate, host, tools, profiles, reports, policy status and nonce. Install only a `QUALIFICATION_ONLY` generation first.

## Gate 4 — Policy and architecture decisions

Independently approve and activate the exact canonical policy. Execute Prompt 004 manually. Generate the roadmap once and independently review it against all 41 prompts.

## Gate 5 — Isolated dry runs and project qualification

Only after prior gates may non-production autonomous dry runs begin. Test the actual AZPR repository for authentication, customer isolation, migrations, backups, consent/suppression, PII, source terms, idempotency and provider behavior.

No gate is completed by this development bundle.
