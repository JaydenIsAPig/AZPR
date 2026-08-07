#!/usr/bin/env python3
"""TEST-ONLY local implementation of the v9 external signer protocol.

It intentionally refuses execution unless AZPR_V9_TEST_REFERENCE_SIGNER=1. A
production receipt signer must be remote/HSM-backed and separately qualified.
"""
from __future__ import annotations
import base64, hashlib, json, os, sys
from pathlib import Path
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

def canonical(v): return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
def main():
    if os.environ.get("AZPR_V9_TEST_REFERENCE_SIGNER") != "1":
        raise SystemExit("reference signer is test-only")
    if len(sys.argv)!=2 or sys.argv[1]!="sign-receipt": raise SystemExit("unsupported operation")
    req=json.load(sys.stdin)
    expected={"format_version","request_kind","request_nonce","signer_identity_sha256","unsigned_receipt_sha256","unsigned_receipt"}
    if set(req)!=expected or req["request_kind"]!="AZPR_V9_EXTERNAL_RECEIPT_SIGNING_REQUEST": raise SystemExit("request invalid")
    unsigned=req["unsigned_receipt"]
    if hashlib.sha256(canonical(unsigned)).hexdigest()!=req["unsigned_receipt_sha256"]: raise SystemExit("request hash mismatch")
    key_path=os.environ.get("AZPR_V9_TEST_REFERENCE_SIGNER_PRIVATE_KEY")
    if not key_path: raise SystemExit("test signer key missing")
    key=serialization.load_pem_private_key(Path(key_path).read_bytes(),password=None)
    if not isinstance(key,Ed25519PrivateKey): raise SystemExit("test signer key is not Ed25519")
    signed=dict(unsigned); signed["signature"]=base64.b64encode(key.sign(canonical(unsigned))).decode()
    print(json.dumps({"format_version":"1.0","response_kind":"AZPR_V9_EXTERNAL_RECEIPT_SIGNING_RESPONSE","request_nonce":req["request_nonce"],"signer_identity_sha256":req["signer_identity_sha256"],"unsigned_receipt_sha256":req["unsigned_receipt_sha256"],"signed_receipt":signed},sort_keys=True))
if __name__=="__main__": main()
