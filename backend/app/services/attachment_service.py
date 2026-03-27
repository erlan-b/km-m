from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status


@dataclass(slots=True)
class SavedAttachmentFile:
    stored_name: str
    original_name: str
    mime_type: str
    file_size: int
    relative_path: str
    absolute_path: Path


def sanitize_original_name(file_name: str | None) -> str:
    candidate = (file_name or "attachment").strip()
    safe_name = Path(candidate).name
    return safe_name or "attachment"


def save_upload_file(
    upload_file: UploadFile,
    *,
    base_dir: Path,
    sub_dir: str,
    max_size_bytes: int,
    allowed_mime_types: set[str],
) -> SavedAttachmentFile:
    mime_type = (upload_file.content_type or "").lower()
    if mime_type not in allowed_mime_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported attachment mime type: {mime_type or 'unknown'}",
        )

    original_name = sanitize_original_name(upload_file.filename)
    extension = Path(original_name).suffix.lower()
    stored_name = f"{uuid4().hex}{extension}"

    target_dir = base_dir / sub_dir
    target_dir.mkdir(parents=True, exist_ok=True)

    absolute_path = target_dir / stored_name
    total_bytes = 0

    try:
        with absolute_path.open("wb") as output_file:
            while True:
                chunk = upload_file.file.read(1024 * 1024)
                if not chunk:
                    break
                total_bytes += len(chunk)
                if total_bytes > max_size_bytes:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Attachment exceeds max size of {max_size_bytes} bytes",
                    )
                output_file.write(chunk)
    except HTTPException:
        if absolute_path.exists():
            absolute_path.unlink(missing_ok=True)
        raise

    relative_path = str(Path(sub_dir) / stored_name).replace("\\", "/")
    return SavedAttachmentFile(
        stored_name=stored_name,
        original_name=original_name,
        mime_type=mime_type,
        file_size=total_bytes,
        relative_path=relative_path,
        absolute_path=absolute_path,
    )
