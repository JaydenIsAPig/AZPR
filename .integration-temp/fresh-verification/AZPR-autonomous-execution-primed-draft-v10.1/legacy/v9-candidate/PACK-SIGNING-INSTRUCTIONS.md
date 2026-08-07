# V8 Pack Signing Instructions

This development delivery is intentionally **not organization-signed** because no authorized release private key was supplied.

An authorized release host should:

1. verify the implementation ZIP, reports ZIP, sidecars, scoped internal manifests, fresh-extraction verification records, and delivery manifest;
2. sign the canonical delivery-manifest bytes with the established organization release authority;
3. publish the signature, signer certificate/key ID, expiry/revocation policy, and verification procedure separately;
4. never place the release private key in the candidate, repository, controller, Codex environment, or qualification host.

SHA-256 sidecars provide identity only; they do not establish organizational authorization.
