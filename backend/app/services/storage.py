import os
import re
import io
import time
import uuid
import shutil
import hashlib
import logging
import contextlib
from abc import ABC, abstractmethod
from typing import Tuple, Optional, Dict, Any, Generator

import httpx
from fastapi import UploadFile, HTTPException, status

from app.config import settings

logger = logging.getLogger(__name__)

ALLOWED_MIME_TYPES = {
    "application/pdf": ".pdf",
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/webp": ".webp",
    "image/svg+xml": ".svg",
    "text/plain": ".txt",
}

MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB


def sanitize_filename(filename: Optional[str], fallback_ext: str = ".dat") -> str:
    """
    Sanitizes arbitrary client-supplied filenames to prevent directory traversal
    and illegal filesystem characters across Windows and POSIX systems.
    """
    if not filename:
        return f"asset_{uuid.uuid4().hex[:8]}{fallback_ext}"

    # Remove null bytes and ASCII control characters
    clean = re.sub(r"[\x00-\x1f\x7f]", "", filename)

    # Strip directory paths (both POSIX and Windows delimiters)
    clean = clean.replace("\\", "/").split("/")[-1].strip()

    # Strip leading dots to prevent hidden files or traversal sequences (../)
    clean = clean.lstrip(".")

    # Replace unsupported characters with underscore, keeping alphanumeric, hyphen, underscore, dot
    clean = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", clean)

    # Collapse multiple consecutive dots
    clean = re.sub(r"\.{2,}", ".", clean)

    if not clean or clean.startswith("."):
        return f"asset_{uuid.uuid4().hex[:8]}{fallback_ext}"

    return clean


def build_object_key(
    org_id: str,
    subfolder: str,
    safe_filename: str,
    version_id: Optional[str] = None
) -> str:
    """
    Constructs a deterministic, tenant-isolated object key for cloud storage:
    {organization_id}/{subfolder}/{version_id}_{safe_filename}
    """
    clean_org = re.sub(r"[^a-zA-Z0-9_\-]", "", org_id)
    if not clean_org:
        raise ValueError("Invalid organization identifier for storage object path.")

    clean_subfolder = re.sub(r"[^a-zA-Z0-9_\-]", "", subfolder) or "documents"

    if version_id:
        clean_version = re.sub(r"[^a-zA-Z0-9_\-]", "", version_id)
        return f"{clean_org}/{clean_subfolder}/{clean_version}_{safe_filename}"

    return f"{clean_org}/{clean_subfolder}/{safe_filename}"


def is_key_owned_by_org(object_key_or_path: str, org_id: str) -> bool:
    """
    Verifies that the object key or path begins with or belongs to the organization identifier.
    Guarantees cross-tenant isolation and rejects path traversal attempts.
    """
    clean_org = re.sub(r"[^a-zA-Z0-9_\-]", "", org_id)
    normalized = object_key_or_path.replace("\\", "/").strip()

    if normalized.startswith("supabase://"):
        parts = normalized.split("/", 3)
        if len(parts) >= 4:
            normalized = parts[3]

    parts = [p for p in normalized.split("/") if p]
    # Reject any path containing path traversal components (..)
    if ".." in parts:
        return False

    parts = [p for p in parts if p != "."]
    if not parts:
        return False

    # Top-level bucket path must match the organization ID
    if parts[0] == clean_org:
        return True

    # If it's a full local filesystem path, verify clean_org is present as an exact directory component
    if clean_org in parts:
        idx = parts.index(clean_org)
        if idx < len(parts) - 1:
            return True

    return False


class StorageBackend(ABC):
    """Abstract interface defining the durable storage contract."""

    @abstractmethod
    def validate_file(self, file: UploadFile) -> Tuple[str, str]:
        """Validates MIME type and declared file size."""
        pass

    @abstractmethod
    async def save_file(
        self,
        file: UploadFile,
        org_id: str,
        subfolder: str = "documents",
        filename_prefix: Optional[str] = None
    ) -> Tuple[str, int]:
        """Stores a file durably and returns (storage_reference, bytes_written)."""
        pass

    @abstractmethod
    def get_file_bytes(self, file_key_or_path: str) -> bytes:
        """Retrieves complete file bytes for authenticated access."""
        pass

    @abstractmethod
    def get_file_path_for_processing(self, file_key_or_path: str) -> str:
        """Resolves or materializes a local filesystem path for OCR and PDF rendering."""
        pass

    @abstractmethod
    def check_exists(self, file_key_or_path: str) -> bool:
        """Checks if the object exists in durable storage or local disk."""
        pass

    @abstractmethod
    def delete_file(self, file_key_or_path: str) -> bool:
        """Deletes the object from storage."""
        pass

    @abstractmethod
    def cleanup_cache(self, max_age_seconds: int = 3600) -> int:
        """Purges disposable cached assets older than max_age_seconds."""
        pass


class LocalStorageBackend(StorageBackend):
    """
    Local filesystem storage backend preserving development and offline testing behavior.
    """
    def __init__(self, local_dir: Optional[str] = None):
        self.local_dir = local_dir or settings.LOCAL_STORAGE_DIR
        os.makedirs(self.local_dir, exist_ok=True)

    def validate_file(self, file: UploadFile) -> Tuple[str, str]:
        mime_type = file.content_type or "application/octet-stream"
        if mime_type not in ALLOWED_MIME_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file type '{mime_type}'. Supported: PDF, PNG, JPG, WEBP, SVG, TXT"
            )

        if hasattr(file, "size") and file.size and file.size > MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File exceeds maximum allowed size of 25MB."
            )

        ext = ALLOWED_MIME_TYPES[mime_type]
        return mime_type, ext

    async def save_file(
        self,
        file: UploadFile,
        org_id: str,
        subfolder: str = "documents",
        filename_prefix: Optional[str] = None
    ) -> Tuple[str, int]:
        mime_type, ext = self.validate_file(file)
        org_folder = os.path.join(self.local_dir, org_id, subfolder)
        os.makedirs(org_folder, exist_ok=True)

        safe_filename = sanitize_filename(file.filename, fallback_ext=ext)
        if filename_prefix:
            safe_filename = f"{filename_prefix}_{safe_filename}"
        dest_path = os.path.join(org_folder, safe_filename)

        bytes_written = 0
        hasher = hashlib.sha256()
        with open(dest_path, "wb") as buffer:
            while chunk := await file.read(1024 * 1024):
                bytes_written += len(chunk)
                if bytes_written > MAX_FILE_SIZE_BYTES:
                    buffer.close()
                    if os.path.exists(dest_path):
                        os.remove(dest_path)
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="File size limit of 25MB exceeded."
                    )
                hasher.update(chunk)
                buffer.write(chunk)

        return dest_path, bytes_written

    def get_file_bytes(self, file_key_or_path: str) -> bytes:
        if not file_key_or_path or not os.path.exists(file_key_or_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Asset not found on disk."
            )
        with open(file_key_or_path, "rb") as f:
            return f.read()

    def get_file_path_for_processing(self, file_key_or_path: str) -> str:
        return file_key_or_path

    def check_exists(self, file_key_or_path: str) -> bool:
        return bool(file_key_or_path and os.path.exists(file_key_or_path))

    def delete_file(self, file_key_or_path: str) -> bool:
        if file_key_or_path and os.path.exists(file_key_or_path):
            try:
                os.remove(file_key_or_path)
                return True
            except Exception:
                return False
        return False

    def cleanup_cache(self, max_age_seconds: int = 3600) -> int:
        return 0


class SupabaseStorageBackend(StorageBackend):
    """
    Durable private Supabase Storage backend.
    Interacts with the Supabase Storage REST API using backend-only service credentials.
    Confidential assets remain private in bucket 'inkloom-private-assets'.
    """
    def __init__(
        self,
        supabase_url: Optional[str] = None,
        supabase_service_key: Optional[str] = None,
        bucket_name: Optional[str] = None,
        cache_dir: Optional[str] = None,
        http_client: Optional[httpx.Client] = None,
        async_http_client: Optional[httpx.AsyncClient] = None
    ):
        url = supabase_url if supabase_url is not None else settings.SUPABASE_URL
        self.supabase_url = (url or "").rstrip("/")
        self.service_key = supabase_service_key if supabase_service_key is not None else settings.SUPABASE_SERVICE_KEY
        self.bucket = bucket_name or settings.SUPABASE_STORAGE_BUCKET or "inkloom-private-assets"

        if not self.supabase_url or not self.service_key:
            raise ValueError(
                "Supabase Storage backend requires SUPABASE_URL and SUPABASE_SERVICE_KEY to be configured."
            )

        self.cache_dir = cache_dir or os.path.join(settings.LOCAL_STORAGE_DIR, "supabase_cache")
        os.makedirs(self.cache_dir, exist_ok=True)

        self._injected_http_client = http_client
        self._injected_async_http_client = async_http_client

    def _get_headers(self, content_type: Optional[str] = None, upsert: bool = True) -> Dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.service_key}",
            "apikey": self.service_key,
        }
        if content_type:
            headers["Content-Type"] = content_type
        if upsert:
            headers["x-upsert"] = "true"
        return headers

    def _normalize_key(self, key_or_path: str) -> str:
        """Extracts the canonical object key from a full path or supabase:// URI."""
        k = key_or_path.replace("\\", "/").strip()
        if k.startswith("supabase://"):
            parts = k.split("/", 3)
            if len(parts) >= 4:
                return parts[3]
        return k.lstrip("./")

    def validate_file(self, file: UploadFile) -> Tuple[str, str]:
        mime_type = file.content_type or "application/octet-stream"
        if mime_type not in ALLOWED_MIME_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file type '{mime_type}'. Supported: PDF, PNG, JPG, WEBP, SVG, TXT"
            )

        if hasattr(file, "size") and file.size and file.size > MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File exceeds maximum allowed size of 25MB."
            )

        ext = ALLOWED_MIME_TYPES[mime_type]
        return mime_type, ext

    async def save_file(
        self,
        file: UploadFile,
        org_id: str,
        subfolder: str = "documents",
        filename_prefix: Optional[str] = None
    ) -> Tuple[str, int]:
        mime_type, ext = self.validate_file(file)
        safe_filename = sanitize_filename(file.filename, fallback_ext=ext)
        object_key = build_object_key(
            org_id=org_id,
            subfolder=subfolder,
            safe_filename=safe_filename,
            version_id=filename_prefix
        )

        # Stream chunks into memory with strict size enforcement
        chunks = []
        bytes_written = 0
        hasher = hashlib.sha256()

        while chunk := await file.read(1024 * 1024):
            bytes_written += len(chunk)
            if bytes_written > MAX_FILE_SIZE_BYTES:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="File size limit of 25MB exceeded."
                )
            hasher.update(chunk)
            chunks.append(chunk)

        file_bytes = b"".join(chunks)
        upload_url = f"{self.supabase_url}/storage/v1/object/{self.bucket}/{object_key}"
        headers = self._get_headers(content_type=mime_type, upsert=True)

        try:
            if self._injected_async_http_client:
                response = await self._injected_async_http_client.post(
                    upload_url, headers=headers, content=file_bytes, timeout=30.0
                )
            else:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(
                        upload_url, headers=headers, content=file_bytes
                    )

            if response.status_code not in (200, 201):
                logger.error(
                    f"Supabase Storage upload failed with status {response.status_code}: {response.text}"
                )
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Durable storage upload failed: Supabase Storage returned {response.status_code}"
                )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Supabase Storage network error during upload: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Durable storage unavailable: {str(e)}"
            )

        # Cache locally in controlled temporary cache for immediate OCR/validation
        cache_path = os.path.join(self.cache_dir, object_key)
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        tmp_cache = f"{cache_path}.tmp_{uuid.uuid4().hex[:6]}"
        with open(tmp_cache, "wb") as cf:
            cf.write(file_bytes)
        try:
            os.replace(tmp_cache, cache_path)
        except OSError:
            try:
                with open(cache_path, "wb") as cf:
                    cf.write(file_bytes)
                if os.path.exists(tmp_cache):
                    os.remove(tmp_cache)
            except Exception:
                pass

        return object_key, bytes_written

    def get_file_bytes(self, file_key_or_path: str) -> bytes:
        if os.path.exists(file_key_or_path):
            with open(file_key_or_path, "rb") as f:
                return f.read()

        object_key = self._normalize_key(file_key_or_path)
        cache_path = os.path.join(self.cache_dir, object_key)
        if os.path.exists(cache_path) and os.path.getsize(cache_path) > 0:
            with open(cache_path, "rb") as f:
                return f.read()

        # Download from private Supabase Storage authenticated endpoint
        download_url = f"{self.supabase_url}/storage/v1/object/authenticated/{self.bucket}/{object_key}"
        headers = self._get_headers(upsert=False)

        try:
            if self._injected_http_client:
                response = self._injected_http_client.get(download_url, headers=headers, timeout=30.0)
            else:
                with httpx.Client(timeout=30.0) as client:
                    response = client.get(download_url, headers=headers)

            def _is_not_found(res: httpx.Response) -> bool:
                if res.status_code == 404:
                    return True
                if res.status_code == 400:
                    try:
                        err = res.json()
                        if err.get("statusCode") in (404, "404") or err.get("error") in ("not_found", "NoSuchKey") or err.get("code") in ("NoSuchKey", "not_found"):
                            return True
                    except Exception:
                        pass
                return False

            if _is_not_found(response):
                # Fallback to standard object path with service-role token
                fallback_url = f"{self.supabase_url}/storage/v1/object/{self.bucket}/{object_key}"
                if self._injected_http_client:
                    response = self._injected_http_client.get(fallback_url, headers=headers, timeout=30.0)
                else:
                    with httpx.Client(timeout=30.0) as client:
                        response = client.get(fallback_url, headers=headers)

            if _is_not_found(response):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Object '{object_key}' not found in Supabase Storage."
                )

            if response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Failed to retrieve object from storage: Supabase returned status {response.status_code}."
                )

            data = response.content

            # Cache downloaded bytes safely
            os.makedirs(os.path.dirname(cache_path), exist_ok=True)
            tmp_cache = f"{cache_path}.tmp_{uuid.uuid4().hex[:6]}"
            with open(tmp_cache, "wb") as f:
                f.write(data)
            try:
                os.replace(tmp_cache, cache_path)
            except OSError:
                try:
                    with open(cache_path, "wb") as f:
                        f.write(data)
                    if os.path.exists(tmp_cache):
                        os.remove(tmp_cache)
                except Exception:
                    pass

            return data

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Supabase Storage download error for key '{object_key}': {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Durable storage unavailable: {str(e)}"
            )

    def get_file_path_for_processing(self, file_key_or_path: str) -> str:
        """
        Materializes the asset onto the local filesystem for processing by
        libraries requiring a local path (pypdfium2, RapidOCR, PIL).
        """
        if os.path.exists(file_key_or_path):
            return file_key_or_path

        object_key = self._normalize_key(file_key_or_path)
        cache_path = os.path.join(self.cache_dir, object_key)
        if os.path.exists(cache_path) and os.path.getsize(cache_path) > 0:
            return cache_path

        # Triggers download and atomic write to cache_path
        self.get_file_bytes(object_key)
        return cache_path

    def check_exists(self, file_key_or_path: str) -> bool:
        if os.path.exists(file_key_or_path):
            return True

        object_key = self._normalize_key(file_key_or_path)
        cache_path = os.path.join(self.cache_dir, object_key)
        if os.path.exists(cache_path) and os.path.getsize(cache_path) > 0:
            return True

        info_url = f"{self.supabase_url}/storage/v1/object/info/{self.bucket}/{object_key}"
        headers = self._get_headers(upsert=False)

        try:
            if self._injected_http_client:
                res = self._injected_http_client.get(info_url, headers=headers, timeout=10.0)
            else:
                with httpx.Client(timeout=10.0) as client:
                    res = client.get(info_url, headers=headers)

            if res.status_code == 200:
                return True

            # Also try HEAD request on object
            head_url = f"{self.supabase_url}/storage/v1/object/{self.bucket}/{object_key}"
            if self._injected_http_client:
                res_head = self._injected_http_client.head(head_url, headers=headers, timeout=10.0)
            else:
                with httpx.Client(timeout=10.0) as client:
                    res_head = client.head(head_url, headers=headers)

            return res_head.status_code == 200
        except Exception:
            return False

    def delete_file(self, file_key_or_path: str) -> bool:
        object_key = self._normalize_key(file_key_or_path)

        # 1. Remove from local cache
        cache_path = os.path.join(self.cache_dir, object_key)
        if os.path.exists(cache_path):
            try:
                os.remove(cache_path)
            except Exception:
                pass

        if os.path.exists(file_key_or_path):
            try:
                os.remove(file_key_or_path)
            except Exception:
                pass

        # 2. Delete from Supabase Storage
        delete_url = f"{self.supabase_url}/storage/v1/object/{self.bucket}/{object_key}"
        headers = self._get_headers(upsert=False)

        try:
            if self._injected_http_client:
                res = self._injected_http_client.delete(delete_url, headers=headers, timeout=10.0)
            else:
                with httpx.Client(timeout=10.0) as client:
                    res = client.delete(delete_url, headers=headers)

            return res.status_code in (200, 204, 404)
        except Exception as e:
            logger.warning(f"Failed to delete Supabase Storage object '{object_key}': {str(e)}")
            return False

    def cleanup_cache(self, max_age_seconds: int = 3600) -> int:
        now = time.time()
        purged = 0
        if not os.path.exists(self.cache_dir):
            return 0

        for root, _, files in os.walk(self.cache_dir):
            for fname in files:
                fpath = os.path.join(root, fname)
                try:
                    if (now - os.path.getmtime(fpath)) > max_age_seconds:
                        os.remove(fpath)
                        purged += 1
                except Exception:
                    pass
        return purged


class StorageService:
    """
    Unified Storage Service façade supporting 'local' and 'supabase' backends.
    """
    def __init__(
        self,
        backend: Optional[str] = None,
        supabase_url: Optional[str] = None,
        supabase_service_key: Optional[str] = None,
        bucket_name: Optional[str] = None,
        local_dir: Optional[str] = None,
        http_client: Optional[httpx.Client] = None,
        async_http_client: Optional[httpx.AsyncClient] = None
    ):
        self.backend_name = (backend or settings.STORAGE_BACKEND or "local").lower()
        self.local_dir = local_dir or settings.LOCAL_STORAGE_DIR

        if self.backend_name == "supabase":
            self.backend = SupabaseStorageBackend(
                supabase_url=supabase_url,
                supabase_service_key=supabase_service_key,
                bucket_name=bucket_name,
                cache_dir=os.path.join(self.local_dir, "supabase_cache"),
                http_client=http_client,
                async_http_client=async_http_client
            )
        else:
            self.backend = LocalStorageBackend(local_dir=self.local_dir)

    def validate_file(self, file: UploadFile) -> Tuple[str, str]:
        return self.backend.validate_file(file)

    async def save_file(
        self,
        file: UploadFile,
        org_id: str,
        subfolder: str = "documents",
        filename_prefix: Optional[str] = None
    ) -> Tuple[str, int]:
        return await self.backend.save_file(
            file=file,
            org_id=org_id,
            subfolder=subfolder,
            filename_prefix=filename_prefix
        )

    def get_file_bytes(self, file_key_or_path: str) -> bytes:
        return self.backend.get_file_bytes(file_key_or_path)

    def get_file_path_for_processing(self, file_key_or_path: str) -> str:
        return self.backend.get_file_path_for_processing(file_key_or_path)

    def check_exists(self, file_key_or_path: str) -> bool:
        return self.backend.check_exists(file_key_or_path)

    def delete_file(self, file_key_or_path: str) -> bool:
        return self.backend.delete_file(file_key_or_path)

    def cleanup_cache(self, max_age_seconds: int = 3600) -> int:
        return self.backend.cleanup_cache(max_age_seconds=max_age_seconds)

    @contextlib.contextmanager
    def temporary_materialized_file(
        self,
        file_key_or_path: str,
        auto_cleanup: bool = False
    ) -> Generator[str, None, None]:
        local_path = self.get_file_path_for_processing(file_key_or_path)
        try:
            yield local_path
        finally:
            if auto_cleanup and os.path.exists(local_path):
                try:
                    os.remove(local_path)
                except Exception:
                    pass


storage_service = StorageService()
