"""
Milestone 5I.5 — Live Supabase Storage Integration Verification Suite

This suite executes against the real Supabase Storage remote endpoint
when SUPABASE_URL, SUPABASE_SERVICE_KEY, and STORAGE_BACKEND=supabase
are configured in the environment.

When live credentials or bucket are missing, tests cleanly skip and document
the exact blocking prerequisite.
"""

import os
import io
import time
import uuid
import shutil
import hashlib
import pytest
import httpx
from PIL import Image
from fastapi import UploadFile, HTTPException

from app.config import settings
from app.services.storage import (
    StorageService,
    SupabaseStorageBackend,
    sanitize_filename,
    build_object_key,
    is_key_owned_by_org
)
from app.models.content import ContentVersion
from app.services.pdf_service import pdf_service

LIVE_CREDENTIALS_AVAILABLE = bool(
    settings.SUPABASE_URL and settings.SUPABASE_SERVICE_KEY
)


@pytest.mark.skipif(
    not LIVE_CREDENTIALS_AVAILABLE,
    reason="PREREQUISITE MISSING: SUPABASE_URL and SUPABASE_SERVICE_KEY must be configured for live storage verification."
)
def test_live_bucket_exists_and_is_private():
    """Verifies that the target bucket 'inkloom-private-assets' exists and is private."""
    supabase_url = settings.SUPABASE_URL.rstrip("/")
    service_key = settings.SUPABASE_SERVICE_KEY
    bucket_name = settings.SUPABASE_STORAGE_BUCKET or "inkloom-private-assets"

    headers = {
        "Authorization": f"Bearer {service_key}",
        "apikey": service_key,
    }

    with httpx.Client(timeout=15.0) as client:
        # Check bucket metadata via Supabase Storage REST API
        resp = client.get(f"{supabase_url}/storage/v1/bucket/{bucket_name}", headers=headers)
        if resp.status_code == 404:
            pytest.fail(
                f"PREREQUISITE MISSING: Remote bucket '{bucket_name}' does not exist in Supabase project."
            )

        assert resp.status_code == 200, f"Failed to query bucket: {resp.status_code} {resp.text}"
        data = resp.json()
        assert data.get("public") is False, f"SECURITY VIOLATION: Bucket '{bucket_name}' must be private."


@pytest.mark.skipif(
    not LIVE_CREDENTIALS_AVAILABLE,
    reason="PREREQUISITE MISSING: SUPABASE_URL and SUPABASE_SERVICE_KEY must be configured for live storage verification."
)
def test_live_synthetic_asset_roundtrip_and_cleanup(tmp_path):
    """
    Executes live upload, download, checksum verification, and cleanup
    against the real remote bucket using a synthetic test payload only.
    Confirms test uploads use a unique test prefix and cleanup only deletes test objects.
    """
    backend = SupabaseStorageBackend(
        supabase_url=settings.SUPABASE_URL,
        supabase_service_key=settings.SUPABASE_SERVICE_KEY,
        bucket_name=settings.SUPABASE_STORAGE_BUCKET or "inkloom-private-assets",
        cache_dir=str(tmp_path / "live_cache")
    )

    test_org_id = f"test-org-{uuid.uuid4().hex[:8]}"
    synthetic_payload = b"LIVE_STORAGE_VERIFICATION_SYNTHETIC_DATA_" + uuid.uuid4().bytes
    expected_checksum = hashlib.sha256(synthetic_payload).hexdigest()

    file = UploadFile(
        filename="live_verification_asset.png",
        file=io.BytesIO(synthetic_payload),
        headers={"content-type": "image/png"}
    )

    import asyncio
    obj_key, size = asyncio.run(
        backend.save_file(file, org_id=test_org_id, subfolder="verification", filename_prefix="v1")
    )

    # Ensure key uses unique test prefix
    assert obj_key.startswith(f"{test_org_id}/verification/v1_")
    assert size == len(synthetic_payload)

    try:
        # 1. Download and verify byte-for-byte equality
        downloaded = backend.get_file_bytes(obj_key)
        assert downloaded == synthetic_payload

        # 2. Verify SHA-256 checksum consistency
        downloaded_checksum = hashlib.sha256(downloaded).hexdigest()
        assert downloaded_checksum == expected_checksum

        # 3. Verify materialization for local processing
        local_path = backend.get_file_path_for_processing(obj_key)
        assert os.path.exists(local_path)
        with open(local_path, "rb") as f:
            assert f.read() == synthetic_payload

        # 4. Verify check_exists returns True for live remote object
        assert backend.check_exists(obj_key) is True

    finally:
        # 5. Mandatory cleanup: delete only the specific test object created by this run
        deleted = backend.delete_file(obj_key)
        assert deleted is True


@pytest.mark.skipif(
    not LIVE_CREDENTIALS_AVAILABLE,
    reason="PREREQUISITE MISSING: SUPABASE_URL and SUPABASE_SERVICE_KEY must be configured for live storage verification."
)
def test_live_pdf_preview_rebuilding_from_stored_original(tmp_path):
    """
    Uploads a synthetic multi-page PDF to Supabase Storage, renders a page preview,
    wipes local caches, and confirms the preview can be successfully rebuilt
    from the durable remote original.
    """
    backend = SupabaseStorageBackend(
        supabase_url=settings.SUPABASE_URL,
        supabase_service_key=settings.SUPABASE_SERVICE_KEY,
        bucket_name=settings.SUPABASE_STORAGE_BUCKET or "inkloom-private-assets",
        cache_dir=str(tmp_path / "live_cache")
    )

    test_org_id = f"test-org-{uuid.uuid4().hex[:8]}"

    # Generate synthetic 1-page PDF using PIL
    pil_img = Image.new("RGB", (300, 300), color=(34, 139, 34))
    pdf_buffer = io.BytesIO()
    pil_img.save(pdf_buffer, format="PDF")
    pdf_bytes = pdf_buffer.getvalue()

    file = UploadFile(
        filename="live_test_deck.pdf",
        file=io.BytesIO(pdf_bytes),
        headers={"content-type": "application/pdf"}
    )

    import asyncio
    obj_key, size = asyncio.run(
        backend.save_file(file, org_id=test_org_id, subfolder="posters", filename_prefix="v1")
    )

    preview_cache_dir = tmp_path / "preview_cache"

    try:
        # 1. Materialize initial local file
        local_pdf_path = backend.get_file_path_for_processing(obj_key)
        assert os.path.exists(local_pdf_path)

        # 2. Render initial preview PNG
        rendered_png_1 = pdf_service.get_or_render_page_cache(
            file_path=local_pdf_path,
            page_number=1,
            cache_base_dir=str(preview_cache_dir)
        )
        assert os.path.exists(rendered_png_1)

        # 3. Wipe all local caches (simulating container restart / ephemeral disk wipe)
        shutil.rmtree(str(tmp_path / "live_cache"), ignore_errors=True)
        shutil.rmtree(str(preview_cache_dir), ignore_errors=True)
        assert not os.path.exists(local_pdf_path)
        assert not os.path.exists(rendered_png_1)

        # 4. Resolve local path again — must re-download from Supabase Storage
        reconstituted_pdf_path = backend.get_file_path_for_processing(obj_key)
        assert os.path.exists(reconstituted_pdf_path)
        with open(reconstituted_pdf_path, "rb") as f:
            assert f.read() == pdf_bytes

        # 5. Rebuild the missing preview PNG from the retrieved original
        rendered_png_2 = pdf_service.get_or_render_page_cache(
            file_path=reconstituted_pdf_path,
            page_number=1,
            cache_base_dir=str(preview_cache_dir)
        )
        assert os.path.exists(rendered_png_2)
        assert os.path.getsize(rendered_png_2) > 0

    finally:
        backend.delete_file(obj_key)


@pytest.mark.skipif(
    not LIVE_CREDENTIALS_AVAILABLE,
    reason="PREREQUISITE MISSING: SUPABASE_URL and SUPABASE_SERVICE_KEY must be configured for live storage verification."
)
def test_live_tenant_isolation_and_missing_object_error():
    """Verifies that non-existent objects return 404 and cross-tenant access is rejected."""
    backend = SupabaseStorageBackend(
        supabase_url=settings.SUPABASE_URL,
        supabase_service_key=settings.SUPABASE_SERVICE_KEY,
        bucket_name=settings.SUPABASE_STORAGE_BUCKET or "inkloom-private-assets"
    )

    # 1. Missing object handling
    non_existent_key = f"org-none/posters/missing_{uuid.uuid4().hex[:8]}.pdf"
    with pytest.raises(HTTPException) as exc_info:
        backend.get_file_bytes(non_existent_key)
    assert exc_info.value.status_code == 404

    # 2. Check tenant key isolation
    my_org = "org-authorized-1"
    other_org = "org-unauthorized-2"
    assert is_key_owned_by_org(f"{my_org}/posters/doc.pdf", my_org) is True
    assert is_key_owned_by_org(f"{other_org}/posters/doc.pdf", my_org) is False
    assert is_key_owned_by_org(f"{other_org}/../{my_org}/doc.pdf", my_org) is False


def test_preflight_credential_validation():
    """
    Deterministic test confirming that backend fails fast when Supabase
    backend is requested without credentials.
    """
    with pytest.raises(ValueError, match="Supabase Storage backend requires SUPABASE_URL and SUPABASE_SERVICE_KEY"):
        SupabaseStorageBackend(
            supabase_url="",
            supabase_service_key=""
        )
