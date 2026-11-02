"""
AIDNEXUS ONE — Phase VI versioned keyring (topic 38).

Distinguishes two things that are often conflated:
  * APPLICATION SECRETS (API credentials) — read from environment / platform secret store
    by name; never logged. `require_secret` fails closed with a name-only error.
  * ENCRYPTION KEYS — versioned here. Data is encrypted under the newest ACTIVE key;
    older keys stay DECRYPT-ONLY until revoked; revoked keys can never decrypt.
    Ciphertext carries its key version, so rotation needs no big-bang re-encrypt:
    `rewrap()` migrates records lazily or in a backfill.

STATUS: IMPLEMENTED + TESTED as a library. NOT yet protecting a production data column and
NOT backed by a KMS (a KMS would hold the key-encryption key and unwrap these data keys).
Keys are supplied by the caller (tests generate throwaway keys at runtime).
"""
from __future__ import annotations

import os
from typing import Dict, Optional

from cryptography.fernet import Fernet, InvalidToken


class SecretMissing(Exception):
    pass


class KeyRevoked(Exception):
    pass


def require_secret(name: str, environ=None) -> str:
    """Returns the secret value or raises SecretMissing naming ONLY the variable."""
    v = (environ if environ is not None else os.environ).get(name)
    if not v:
        raise SecretMissing(f"required secret {name!r} is not configured")
    return v


class Keyring:
    def __init__(self):
        self._keys: Dict[int, bytes] = {}
        self._state: Dict[int, str] = {}      # ACTIVE | DECRYPT_ONLY | REVOKED
        self.current: Optional[int] = None

    def add_key(self, version: int, key: Optional[bytes] = None) -> int:
        self._keys[version] = key or Fernet.generate_key()
        self._state[version] = "ACTIVE"
        for v in self._state:
            if v != version and self._state[v] == "ACTIVE":
                self._state[v] = "DECRYPT_ONLY"
        self.current = version
        return version

    def revoke(self, version: int) -> None:
        self._state[version] = "REVOKED"
        self._keys.pop(version, None)
        if self.current == version:
            self.current = None

    def status(self) -> Dict[int, str]:
        return dict(self._state)           # states only — never key material

    def encrypt(self, plaintext: bytes) -> bytes:
        if self.current is None:
            raise KeyRevoked("no active key")
        return f"v{self.current}:".encode() + Fernet(self._keys[self.current]).encrypt(plaintext)

    def decrypt(self, blob: bytes) -> bytes:
        head, _, body = blob.partition(b":")
        try:
            ver = int(head[1:])
        except ValueError as e:
            raise InvalidToken("malformed ciphertext header") from e
        if self._state.get(ver) == "REVOKED" or ver not in self._keys:
            raise KeyRevoked(f"key version {ver} is revoked or unknown")
        return Fernet(self._keys[ver]).decrypt(body)

    def rewrap(self, blob: bytes) -> bytes:
        return self.encrypt(self.decrypt(blob))
