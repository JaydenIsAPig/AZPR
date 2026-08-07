# V10 Bootstrap Root Hardening Report

## V9 reproduction

The v9 `verify_bootstrap_roots` path accepted both the signed bootstrap manifest and authority key through symlink paths.

## V10 design

`operator-tools/v10_trusted_io.py` performs a descriptor-relative component walk. It requires no-follow primitives, rejects symlinks and non-directories in ancestors, rejects group/world-writable trusted directories, enforces expected ownership, opens the leaf with `O_NOFOLLOW`, requires a single-link regular file, enforces restrictive mode and size, and compares device/inode/size/mode/owner/timestamps before and after reading.

`trusted-installation/v10_binding.py::verify_bootstrap_roots` verifies the signed manifest only after trusted reads of both the manifest and authority key, checks sequence and validity, and pins downstream roots including the qualification-trust authority and manifest.

## Release-blocking cases

- leaf symlink for manifest or key;
- ancestor symlink;
- hard-linked leaf;
- writable parent;
- wrong owner;
- stale sequence;
- paired substituted authority key and forged manifest;
- unsupported no-follow primitive.

All source-level cases fail before trust establishment or installation state changes.

## Remaining dependency

The exact production filesystem, mount, ownership, immutable provisioning, key rotation, and recovery ceremony must be exercised on the dedicated host.
