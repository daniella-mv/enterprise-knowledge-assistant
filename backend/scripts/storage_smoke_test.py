"""Object storage smoke test.

Verifies the storage adapter is wired up correctly by performing a full
round-trip against the configured backend (MinIO locally, real S3 in
production):

  1. ensure_bucket
  2. put_object
  3. object_exists
  4. get_object (and check bytes match)
  5. generate_presigned_url
  6. delete_object
  7. confirm absence

Run via:
  make storage-smoke
or:
  docker compose exec api uv run python scripts/storage_smoke_test.py
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

# Allow running as a script without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.adapters import storage  # noqa: E402
from app.config import settings  # noqa: E402


def main() -> int:
    print(f"endpoint:  {settings.s3_endpoint_url or 'aws-default'}")
    print(f"bucket:    {settings.s3_bucket}")
    print(f"region:    {settings.s3_region}")
    print()

    key = f"smoke/{uuid.uuid4()}.txt"
    payload = b"hello from the storage smoke test"

    try:
        storage.ensure_bucket()
        print(f"[OK] bucket ready: {settings.s3_bucket}")

        storage.put_object(key, payload, content_type="text/plain")
        print(f"[OK] put_object: {key} ({len(payload)} bytes)")

        assert storage.object_exists(key), "object should exist after put"
        print("[OK] object_exists -> True")

        got = storage.get_object(key)
        assert got == payload, f"bytes mismatch: expected {payload!r}, got {got!r}"
        print(f"[OK] get_object returned {len(got)} bytes (matches)")

        url = storage.generate_presigned_url(key, expires_in=120)
        print(f"[OK] presigned URL: {url[:70]}{'...' if len(url) > 70 else ''}")

        storage.delete_object(key)
        print("[OK] delete_object")

        assert not storage.object_exists(key), "object should be gone after delete"
        print("[OK] object_exists -> False (deleted)")

        print("\nRESULT: PASS")
        return 0
    except Exception as e:
        print(f"\nFAIL: {type(e).__name__}: {e}")
        # Best-effort cleanup so we don't leave stray test objects.
        try:
            storage.delete_object(key)
        except Exception:
            pass
        return 1


if __name__ == "__main__":
    sys.exit(main())
