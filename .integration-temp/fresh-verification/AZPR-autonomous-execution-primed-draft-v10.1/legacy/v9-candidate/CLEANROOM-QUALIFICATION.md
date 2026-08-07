# V8 Clean-Room Qualification

The v8 verifier requires an exact 39-artifact manifest. Presence, ownership, mode, and hash are necessary but not sufficient. It validates strict schemas, signatures, signer-role separation, revocation, freshness, raw evidence, executable identity probes, and cross-artifact semantics.

A successful receipt has the status:

`SEMANTIC_QUALIFICATION_EVIDENCE_VERIFIED_INSTALLATION_STILL_BLOCKED`

It does not authorize installation. A separate independently dual-signed one-use installation authorization is required and is verified by the root installer before recovery or any write.

The fixture builder exists only to test the verifier. Its outputs are synthetic and forbidden as trusted qualification evidence.
