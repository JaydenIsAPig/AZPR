# AZPR v9 Qualification Probe Isolation and External Signing Report

```json
{
  "safe_for_unattended_execution_now": false,
  "trusted_pre_autonomous_installation_ready": false
}
```

## V8 reproduction

A malicious v8 Codex probe executed as UID 0, read the qualification receipt private key, and the v8 verifier still emitted a signed receipt. Reproduction artifacts include `codex-probe-uid.txt` SHA-256 `9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa`, key-hash evidence SHA-256 `76dcff4c61029de2adb8b94e1278d269d95d3abaf8e9b6922a4eb7f2b28fd777`, and verifier output SHA-256 `ca3432c165b7388fbe1bdfa77e3234f4fb79eb6d1261921b3459ce622be7694e`.

## V9 boundary

The v9 verifier refuses EUID 0, has no qualification receipt private-key input, and never invokes a target binary. The nine exact target identities are accepted only through signed envelopes issued by an independently authorized `qualification-probe-service` signer. Each envelope requires rootless/no-secret/disposable isolation and affirmative denial observations for secret access, host reads, network, mounts, daemon sockets, escape, resource exhaustion, and evidence mutation.

Receipt signing is delegated through a scrubbed-environment client whose executable hash is bound by the qualification input and signed receipt. The response must echo the request nonce and unsigned receipt hash, identify the expected public key, and carry a valid Ed25519 signature over the receipt.

## Qualification dependency

`v9_external_signer_reference.py` and `v9_file_anchor_reference.py` are TEST ONLY. The package does not include or claim a production probe service, disposable VM image, HSM/remote signer, independent evidence reviewer, or real isolation attestation.
