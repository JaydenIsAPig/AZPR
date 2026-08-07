# AZPR v10.1 Non-Root Release Verifier Report

`VERIFY-V10-CANDIDATE.py` refuses UID 0. It uses a reviewer-owned mode-0700 temporary root, sanitized configuration paths, no inherited credentials, no network requirement, disabled bytecode and plugin autoload, and process-isolated tests.

The verifier validates readiness flags, absence of active policy/roadmap authority, Python syntax, every JSON Schema and global resource bounds, prompt bytes, current-document hashes, exact complete test-catalog coverage, all isolated results, internal manifest identity, cache/platform metadata absence, and source-tree immutability.

Source and fresh-extraction executions must both pass under an unprivileged account. Any catalog omission, timeout, output overflow, descendant leak, unexpected result, source mutation, or inventory/hash difference fails the release.
