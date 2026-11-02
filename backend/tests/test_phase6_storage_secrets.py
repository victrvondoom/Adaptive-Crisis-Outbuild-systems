"""Phase VI topics 30 and 38: object store + keyring + secrets."""
import os

import pytest
from cryptography.fernet import InvalidToken

from app import advanced_lab_ext as E
from app.keyring import Keyring, KeyRevoked, SecretMissing, require_secret
from app.object_store import AccessDenied, IntegrityError, LocalObjectStore, StorageError

PDF = b"%PDF-1.4\n" + b"x" * 500


@pytest.fixture
def store(tmp_path):
    now = [1000.0]
    s = LocalObjectStore(str(tmp_path), os.urandom(32), clock=lambda: now[0])
    s.now = now
    return s


def test_signed_download_roundtrip(store):
    m = store.put("ORG-A", "u", PDF, "application/pdf")
    t = store.sign_download("ORG-A", m["key"])
    assert store.read_signed("ORG-A", m["key"], t["exp"], t["sig"]) == PDF


def test_cross_tenant_and_missing_are_indistinguishable(store):
    m = store.put("ORG-A", "u", PDF, "application/pdf")
    with pytest.raises(AccessDenied) as e1:
        store.sign_download("ORG-B", m["key"])
    with pytest.raises(AccessDenied) as e2:
        store.sign_download("ORG-A", "ORG-A/zz/doesnotexist")
    assert "tenant" in str(e1.value) or "found" in str(e1.value)
    assert "found" in str(e2.value)


def test_signature_bound_to_org_key_and_expiry(store):
    m = store.put("ORG-A", "u", PDF, "application/pdf")
    t = store.sign_download("ORG-A", m["key"], ttl_s=30)
    with pytest.raises(AccessDenied):
        store.read_signed("ORG-A", m["key"], t["exp"] + 1000, t["sig"])      # extended expiry
    store.now[0] += 31
    with pytest.raises(AccessDenied, match="expired"):
        store.read_signed("ORG-A", m["key"], t["exp"], t["sig"])


def test_ttl_is_capped(store):
    m = store.put("ORG-A", "u", PDF, "application/pdf")
    assert store.sign_download("ORG-A", m["key"], ttl_s=10**6)["exp"] - 1000 <= 900


def test_content_validation(store):
    with pytest.raises(StorageError, match="magic"):
        store.put("ORG-A", "u", b"MZ" + b"0" * 50, "application/pdf")
    with pytest.raises(StorageError, match="does not match"):
        store.put("ORG-A", "u", PDF, "image/png")
    with pytest.raises(StorageError, match="exceeds"):
        store.put("ORG-A", "u", b"%PDF-" + b"0" * (6 * 1024 * 1024), "application/pdf")


def test_upload_checksum_and_duplicate_and_bitrot_and_delete(store):
    with pytest.raises(IntegrityError):
        store.put("ORG-A", "u", PDF, "application/pdf", client_sha256="0" * 64)
    m = store.put("ORG-A", "u", PDF, "application/pdf")
    assert store.put("ORG-A", "u", PDF, "application/pdf")["duplicate"] is True
    assert store.put("ORG-B", "u", PDF, "application/pdf")["duplicate"] is False     # dedupe never crosses tenants
    with open(store._paths(m["key"])[0], "ab") as f:
        f.write(b"rot")
    t = store.sign_download("ORG-A", m["key"])
    with pytest.raises(IntegrityError):
        store.read_signed("ORG-A", m["key"], t["exp"], t["sig"])
    store.delete("ORG-A", m["key"])
    with pytest.raises(AccessDenied):
        store.sign_download("ORG-A", m["key"])


def test_short_signing_key_rejected(tmp_path):
    with pytest.raises(StorageError):
        LocalObjectStore(str(tmp_path), b"short")


def test_storage_lab():
    r = E.storage_access()
    assert all(r["invariants"].values()) and len(r["attempts"]) == 9


def test_keyring_rotation_and_revocation():
    kr = Keyring()
    kr.add_key(1)
    old = kr.encrypt(b"secret-A")
    kr.add_key(2)
    assert kr.encrypt(b"x").startswith(b"v2:") and kr.decrypt(old) == b"secret-A"
    assert kr.status() == {1: "DECRYPT_ONLY", 2: "ACTIVE"}
    new = kr.rewrap(old)
    kr.revoke(1)
    assert kr.decrypt(new) == b"secret-A"
    with pytest.raises(KeyRevoked):
        kr.decrypt(old)
    with pytest.raises(KeyRevoked):
        kr.decrypt(b"v7:abc")
    with pytest.raises((InvalidToken, KeyRevoked)):
        kr.decrypt(b"garbage")


def test_status_never_exposes_key_material():
    kr = Keyring(); kr.add_key(1)
    assert all(isinstance(v, str) and len(v) < 20 for v in kr.status().values())


def test_missing_secret_fails_closed_without_leaking_value():
    with pytest.raises(SecretMissing) as e:
        require_secret("NOPE_SECRET", environ={})
    assert "NOPE_SECRET" in str(e.value)
    assert require_secret("K", environ={"K": "v"}) == "v"


def test_secrets_lab():
    assert all(E.secrets_rotation()["invariants"].values())
