"""Image processing for listing photos (performance: resized WebP + thumbnail)."""

import uuid
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.config import get_settings
from app.core.exceptions import BusinessRuleError

MAX_UPLOAD_BYTES = 8 * 1024 * 1024
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
FULL_SIZE = (1600, 1200)
THUMB_SIZE = (640, 480)


class ImageStorage:
    """Validates, normalises and stores images on the local media volume.

    Single responsibility: everything about files lives here, so the property service
    does not know about Pillow or the filesystem (and the storage could be swapped for
    Azure Blob Storage without touching the service).
    """

    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root or get_settings().media_dir)

    def save_property_photo(self, property_id: int, content: bytes) -> str:
        if len(content) > MAX_UPLOAD_BYTES:
            raise BusinessRuleError("Image trop lourde (8 Mo maximum).")
        try:
            image = Image.open(BytesIO(content))
            image_format = image.format
            image.verify()  # detects truncated / malicious files
            image = Image.open(BytesIO(content))
        except (UnidentifiedImageError, OSError) as exc:
            raise BusinessRuleError("Le fichier envoyé n'est pas une image valide.") from exc
        if image_format not in ALLOWED_FORMATS:
            raise BusinessRuleError("Formats acceptés : JPEG, PNG, WebP.")

        # Apply EXIF orientation, drop metadata (GPS privacy), convert to RGB.
        image = ImageOps.exif_transpose(image).convert("RGB")
        relative_dir = Path("properties") / str(property_id)
        target_dir = self.root / relative_dir
        target_dir.mkdir(parents=True, exist_ok=True)

        name = uuid.uuid4().hex
        full = image.copy()
        full.thumbnail(FULL_SIZE)
        full.save(target_dir / f"{name}.webp", "WEBP", quality=80, method=6)
        thumb = image.copy()
        thumb.thumbnail(THUMB_SIZE)
        thumb.save(target_dir / f"{name}_thumb.webp", "WEBP", quality=75, method=6)
        return (relative_dir / f"{name}.webp").as_posix()

    def delete(self, relative_path: str) -> None:
        for path in (relative_path, relative_path.replace(".webp", "_thumb.webp")):
            (self.root / path).unlink(missing_ok=True)
