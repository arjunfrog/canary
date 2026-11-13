"""Hash chains: each record's hash covers its content and the hash before it.

Used by the audit log and the custody log, so any edit to an old record is detectable.
"""
import hashlib
import json

GENESIS = "0" * 64


def canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def link_hash(prev_hash: str, body: dict) -> str:
    return hashlib.sha256(prev_hash.encode() + b"\n" + canonical(body)).hexdigest()
