import os
import shutil
from typing import Tuple
from fastapi import UploadFile, HTTPException
from app.config import settings

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

class StorageService:
    def __init__(self):
        self.backend = settings.STORAGE_BACKEND
        self.local_dir = settings.LOCAL_STORAGE_DIR
        os.makedirs(self.local_dir, exist_ok=True)

    def validate_file(self, file: UploadFile) -> Tuple[str, str]:
        mime_type = file.content_type or "application/octet-stream"
        if mime_type not in ALLOWED_MIME_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type '{mime_type}'. Supported: PDF, PNG, JPG, WEBP, SVG, TXT"
            )
        
        # Check size if available
        if hasattr(file, "size") and file.size and file.size > MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=400,
                detail=f"File exceeds maximum allowed size of 25MB."
            )
        
        ext = ALLOWED_MIME_TYPES[mime_type]
        return mime_type, ext

    async def save_file(self, file: UploadFile, org_id: str, subfolder: str = "documents") -> Tuple[str, int]:
        mime_type, ext = self.validate_file(file)
        org_folder = os.path.join(self.local_dir, org_id, subfolder)
        os.makedirs(org_folder, exist_ok=True)
        
        safe_filename = os.path.basename(file.filename or f"upload{ext}")
        dest_path = os.path.join(org_folder, safe_filename)
        
        # Write file in chunks to ensure memory efficiency
        bytes_written = 0
        with open(dest_path, "wb") as buffer:
            while chunk := await file.read(1024 * 1024):
                bytes_written += len(chunk)
                if bytes_written > MAX_FILE_SIZE_BYTES:
                    buffer.close()
                    if os.path.exists(dest_path):
                        os.remove(dest_path)
                    raise HTTPException(status_code=400, detail="File size limit of 25MB exceeded.")
                buffer.write(chunk)
        
        return dest_path, bytes_written

storage_service = StorageService()
