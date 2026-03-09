from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from uuid import UUID


class LocalFileStorage:
    """FileStoragePort implementation using local filesystem."""

    def __init__(self, data_dir: str) -> None:
        self._data_dir = Path(data_dir)
        self._originals_dir = self._data_dir / "originals"
        self._thumbnails_dir = self._data_dir / "thumbnails"
        self._images_dir = self._data_dir / "images"

    async def save_original(
        self, file_data: bytes, document_id: UUID, filename: str
    ) -> str:
        doc_dir = self._originals_dir / str(document_id)
        doc_dir.mkdir(parents=True, exist_ok=True)
        file_path = doc_dir / filename
        file_path.write_bytes(file_data)
        return str(file_path.relative_to(self._data_dir))

    async def get_original_path(self, document_id: UUID) -> Path | None:
        doc_dir = self._originals_dir / str(document_id)
        if not doc_dir.exists():
            return None
        files = list(doc_dir.iterdir())
        return files[0] if files else None

    async def save_thumbnail(
        self, image_data: bytes, document_id: UUID
    ) -> str:
        self._thumbnails_dir.mkdir(parents=True, exist_ok=True)
        thumb_path = self._thumbnails_dir / f"{document_id}.png"
        thumb_path.write_bytes(image_data)
        return str(thumb_path.relative_to(self._data_dir))

    async def delete_document_files(self, document_id: UUID) -> None:
        doc_dir = self._originals_dir / str(document_id)
        if doc_dir.exists():
            shutil.rmtree(doc_dir)
        thumb_path = self._thumbnails_dir / f"{document_id}.png"
        if thumb_path.exists():
            thumb_path.unlink()
        img_dir = self._images_dir / str(document_id)
        if img_dir.exists():
            shutil.rmtree(img_dir)

    @staticmethod
    def compute_file_hash(file_data: bytes) -> str:
        return hashlib.sha256(file_data).hexdigest()
