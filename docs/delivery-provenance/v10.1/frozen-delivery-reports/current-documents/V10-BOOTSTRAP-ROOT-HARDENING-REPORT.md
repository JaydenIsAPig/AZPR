# AZPR v10.1 Bootstrap and Host-Root Hardening Report

The installer bootstrap manifest now pins eight roots, including the host qualification manifest and authority key. The host qualification layer then pins 15 prior trust artifacts plus the fixed anchor client and signed anchor identity.

All local root reads are no-follow, owner/mode/link checked, bounded, and inode-stable. The host manifest is not accepted solely by local signature: the fixed anchor client must return an independently signed response for the exact hash and sequence. Leaf/ancestor symlinks, hard links, writable ancestors, wrong ownership, stale sequence, wrong context, bad signature, and remote-head rollback fail closed.
