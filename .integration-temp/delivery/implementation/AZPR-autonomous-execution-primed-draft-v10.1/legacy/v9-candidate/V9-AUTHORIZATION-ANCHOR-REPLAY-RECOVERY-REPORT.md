# AZPR v9 Authorization Anchor, Replay, and Recovery Report

```json
{
  "safe_for_unattended_execution_now": false,
  "trusted_pre_autonomous_installation_ready": false
}
```

## State machine

Every reservation/completion is an Ed25519-signed record with journal ID, ledger sequence, authorization sequence, previous-head hash, ID, nonce, authorization hash, status, and timestamp. Record hashes form the anchor head. Reservation requires the exact next authorization sequence and scans the full authenticated journal for ID, nonce, and sequence reuse.

Before publication, a durable `PENDING.json` contains previous head, new head, and exact signed record. The anchor performs compare-and-publish. The signed record, transport receipt, local head, and pending removal are then persisted in that order. Installation receipts/manifests bind the reservation and completion heads.

## Independent v8 reproduction

The exact v8 authorization replay was accepted after ledger deletion. Reproduction result SHA-256: `7bef4bd295f661607a2c988fecd9e91ff565fcd8f759621035c033cf41802c77`.

## V9 observations

- A stale pre-completion backup restored after anchored completion is rejected.
- Exact replay after local deletion cannot reconcile with the non-genesis remote head.
- Local truncation or record-count mismatch fails signature/hash-chain audit.
- Anchor outage fails closed; an unanchored pending intent can only roll back.
- Remote-new/local-previous can only complete the exact pending signed record.
- Forked or unexpected local/remote heads have no recovery branch and fail closed.

A real qualified remote monotonic service remains required; the shipped file anchor is a deterministic test oracle only.
