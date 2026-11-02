# Storage Architecture (Topic 30)

Current attachments: none exist in the app. `app/object_store.py` (local filesystem adapter) implements: server-generated tenant-prefixed keys; 5 MB cap; magic-byte allow-list (PDF/PNG/JPEG) and claimed-type match; client sha256 upload verification; same-org dedupe; sha256 re-verify on every read; HMAC-SHA256 signed GET (org, key, expiry), TTL capped 900 s; cross-tenant ≡ not-found error; delete + tombstone; legal-hold flag blocks delete.
Lab (9 attempts): authorised ✓; cross-tenant ✗; bad signature ✗; expired ✗; exe-as-PDF ✗; oversize ✗; corrupted upload ✗; bit-rot ✗; after delete ✗. Duplicate upload reused existing object.
NOT implemented: route wiring + metadata table (PLANNED), S3/GCS, SSE-KMS, malware scanning, multipart, lifecycle rules, versioning, audit events for access (add when wired), retention scheduler. Never a permanent public URL: no unsigned read path exists.
