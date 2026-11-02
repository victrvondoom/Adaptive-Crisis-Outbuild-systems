"""
AIDNEXUS ONE — Phase VI secure object store (topic 30).

STATUS: IMPLEMENTED as a local-filesystem adapter + HMAC-signed, expiring URLs.
NOT wired to any HTTP route yet (PLANNED) and NOT S3/GCS: a production deployment
would swap `LocalObjectStore` for a managed bucket with SSE-KMS and native
pre-signed URLs, keeping this interface and its tests.

Rules enforced here (each covered in tests/test_phase6_storage.py):
  * object key is server-generated and tenant-prefixed: <org>/<sha256-prefix>/<uuid>; callers never choose paths
  * size limit and content-type allow-list validated by SNIFFING magic bytes, not the claimed type
  * sha256 recorded at upload and re-verified on every read (corruption => IntegrityError)
  * metadata (org, owner, type, size, sha256, created, retention) kept separately from bytes
  * signed URLs bind (org, key, expiry, method); tampering or expiry => rejected; cross-tenant => rejected
  * delete removes bytes and writes a tombstone so later reads fail closed
  * no permanent public URL exists: there is no unsigned read path
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import uuid
from typing import Any, Dict, Optional

MAX_BYTES = int(os.environ.get("OBJECT_MAX_BYTES", str(5 * 1024 * 1024)))
MAGIC = {b"%PDF-": "application/pdf", b"\x89PNG\r\n\x1a\n": "image/png", b"\xff\xd8\xff": "image/jpeg"}
ALLOWED = set(MAGIC.values())


class StorageError(Exception):
    pass


class AccessDenied(StorageError):
    pass


class IntegrityError(StorageError):
    pass


def sniff(data: bytes) -> Optional[str]:
    for sig, ctype in MAGIC.items():
        if data.startswith(sig):
            return ctype
    return None


class LocalObjectStore:
    def __init__(self, root: str, signing_key: bytes, clock=time.time):
        if not signing_key or len(signing_key) < 16:
            raise StorageError("signing key missing or too short")
        self.root, self._key, self._clock = root, signing_key, clock
        os.makedirs(root, exist_ok=True)

    # -- paths -------------------------------------------------------------
    def _paths(self, key: str):
        safe = key.replace("/", "__")
        return os.path.join(self.root, safe + ".bin"), os.path.join(self.root, safe + ".meta.json")

    def _meta(self, org_id: str, key: str) -> Dict[str, Any]:
        if not key.startswith(org_id + "/"):
            raise AccessDenied("object belongs to another tenant")
        _, mp = self._paths(key)
        if not os.path.exists(mp):
            raise AccessDenied("not found")        # same error as cross-tenant: no existence oracle
        meta = json.load(open(mp))
        if meta.get("deleted"):
            raise AccessDenied("not found")
        return meta

    # -- write -------------------------------------------------------------
    def put(self, org_id: str, owner_id: str, data: bytes, claimed_type: str,
            client_sha256: Optional[str] = None, retention_days: int = 365) -> Dict[str, Any]:
        if len(data) > MAX_BYTES:
            raise StorageError(f"object exceeds {MAX_BYTES} bytes")
        real = sniff(data)
        if real is None or real not in ALLOWED:
            raise StorageError("content type not allowed (magic-byte check)")
        if claimed_type != real:
            raise StorageError("claimed content type does not match content")
        sha = hashlib.sha256(data).hexdigest()
        if client_sha256 and client_sha256 != sha:
            raise IntegrityError("upload corrupted in transit (sha256 mismatch)")
        # duplicate upload by same org => same content reuses existing object (idempotent)
        for fn in os.listdir(self.root):
            if fn.endswith(".meta.json"):
                m = json.load(open(os.path.join(self.root, fn)))
                if m["org_id"] == org_id and m["sha256"] == sha and not m.get("deleted"):
                    return {**m, "duplicate": True}
        key = f"{org_id}/{sha[:2]}/{uuid.uuid4().hex}"
        bp, mp = self._paths(key)
        meta = {"key": key, "org_id": org_id, "owner_id": owner_id, "content_type": real, "size": len(data),
                "sha256": sha, "created_at": self._clock(), "retain_until": self._clock() + retention_days * 86400,
                "deleted": False}
        open(bp, "wb").write(data)
        json.dump(meta, open(mp, "w"))
        return {**meta, "duplicate": False}

    # -- signed URLs ---------------------------------------------------------
    def _sig(self, org_id: str, key: str, exp: int, method: str) -> str:
        return hmac.new(self._key, f"{method}|{org_id}|{key}|{exp}".encode(), hashlib.sha256).hexdigest()

    def sign_download(self, org_id: str, key: str, ttl_s: int = 120) -> Dict[str, Any]:
        self._meta(org_id, key)                      # caller must already be authorised for this org's object
        exp = int(self._clock()) + min(ttl_s, 900)   # hard cap 15 minutes
        return {"key": key, "exp": exp, "sig": self._sig(org_id, key, exp, "GET")}

    def read_signed(self, org_id: str, key: str, exp: int, sig: str) -> bytes:
        if not hmac.compare_digest(sig, self._sig(org_id, key, int(exp), "GET")):
            raise AccessDenied("bad signature")
        if self._clock() > int(exp):
            raise AccessDenied("signed URL expired")
        meta = self._meta(org_id, key)
        data = open(self._paths(key)[0], "rb").read()
        if hashlib.sha256(data).hexdigest() != meta["sha256"]:
            raise IntegrityError("stored object failed checksum verification")
        return data

    # -- delete --------------------------------------------------------------
    def delete(self, org_id: str, key: str, now: Optional[float] = None) -> None:
        meta = self._meta(org_id, key)
        if (now or self._clock()) < meta["retain_until"] and meta.get("legal_hold"):
            raise StorageError("retention/legal hold active")
        bp, mp = self._paths(key)
        if os.path.exists(bp):
            os.remove(bp)
        meta.update(deleted=True, deleted_at=self._clock())
        json.dump(meta, open(mp, "w"))
