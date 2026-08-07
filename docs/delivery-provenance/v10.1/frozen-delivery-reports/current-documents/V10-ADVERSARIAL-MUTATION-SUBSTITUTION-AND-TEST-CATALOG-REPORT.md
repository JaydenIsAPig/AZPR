# AZPR v10.1 Adversarial, Mutation, Substitution, and Test Catalog Report

## Catalog policy

The catalog contains all `120` tests collected from the candidate. There is no smaller selected release subset. The verifier re-collects tests and requires exact set equality before execution.

Each test runs in a separate process group with a clean reviewer home, disabled user site and pytest plugin autoload, bytecode disabled, bounded output, a hard timeout, and descendant-leak rejection.

## New attack regressions

- complete caller-created higher authority and signer chain;
- signed `DENY_ALL` policy paired with controlled-network evidence;
- one-second policy paired with one-hour-old evidence;
- forged/unsigned attestation;
- declared service digest differing from descriptor-opened executable;
- future trust and revocation issuance;
- stale/forked host-root sequence rejected by independent anchor;
- wrong-role and revoked keys;
- field-by-field trust-binding mutation;
- external signer binding substitution;
- exact 57-artifact membership and inode aliasing;
- bootstrap symlink and hard-link substitution.

The inherited schema-bounds oracle and all prior v5-v9, controller, validation-runner, transaction, rollback, evidence-derivation, key-lifecycle, and phase-separation tests are release blocking.
