"""Add or remove clearly-labelled PROVISIONAL photos on demo listings (test only).

These images are generated, not real pictures: each one is stamped
"PHOTO PROVISOIRE" with the listing type and city, and its alt text starts with
"Photo provisoire", which is also how `remove` finds them again. They exist to check
the card ratio, object-fit, lazy loading and the detail gallery until real photos
are uploaded from the back-office.

They go through the same storage as a back-office upload (resized WebP + thumbnail),
so the rendering is identical to a real photo. Varied sizes (landscape, portrait,
panoramic) are used on purpose to exercise `object-fit: cover`.

Usage (inside the app container):
    python -m scripts.provisional_photos add [--limit 8] [--gallery 5]
    python -m scripts.provisional_photos remove
"""

from __future__ import annotations

import argparse
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.database import SessionLocal
from app.core.formatting import label
from app.models import Property, PropertyPhoto
from app.models.enums import PropertyStatus
from app.services.image_service import ImageStorage

ALT_PREFIX = "Photo provisoire (image de test)"
SIZES = [(1600, 1200), (1200, 1600), (1920, 1080), (1600, 1200), (1400, 1400)]
# Palette of the site, so test images never pass for real pictures
TONES = [("#e6decb", "#d9cdb6"), ("#dfe0c8", "#c9cba8"), ("#eadfcf", "#d6c3a8")]
INK = "#4a3728"


def _font(size: int) -> ImageFont.ImageFont:
    # DejaVu Sans ships with matplotlib (already a dependency) and has French accents;
    # Pillow's built-in font does not.
    try:
        from matplotlib import font_manager

        return ImageFont.truetype(font_manager.findfont("DejaVu Sans"), size)
    except (ImportError, OSError):
        return ImageFont.load_default(size=size)


def render(category: str, city: str, index: int, total: int) -> bytes:
    width, height = SIZES[index % len(SIZES)]
    light, dark = TONES[index % len(TONES)]
    image = Image.new("RGB", (width, height), light)
    draw = ImageDraw.Draw(image)
    # Diagonal hatching: reads as "placeholder", never as a photograph
    step = max(width, height) // 24
    for x in range(-height, width, step):
        draw.line([(x, height), (x + height, 0)], fill=dark, width=max(2, step // 6))
    # Centered label block
    unit = min(width, height)
    lines = [
        ("PHOTO PROVISOIRE", _font(unit // 11)),
        (f"{category} · {city}", _font(unit // 22)),
        (f"Image de test {index + 1}/{total} · à remplacer", _font(unit // 30)),
    ]
    sizes = [draw.textbbox((0, 0), text, font=font) for text, font in lines]
    block_w = max(b[2] - b[0] for b in sizes) + unit // 10
    block_h = sum(b[3] - b[1] for b in sizes) + unit // 6
    x0, y0 = (width - block_w) // 2, (height - block_h) // 2
    draw.rectangle([x0, y0, x0 + block_w, y0 + block_h], fill="#f5f0e6", outline=INK, width=4)
    y = y0 + unit // 20
    for (text, font), box in zip(lines, sizes, strict=True):
        draw.text(((width - (box[2] - box[0])) // 2, y), text, font=font, fill=INK)
        y += (box[3] - box[1]) + unit // 30
    buffer = BytesIO()
    image.save(buffer, "PNG")
    return buffer.getvalue()


def add(db: Session, limit: int, gallery: int) -> int:
    storage = ImageStorage()
    listings = db.scalars(
        select(Property)
        .where(Property.status == PropertyStatus.AVAILABLE, ~Property.photos.any())
        .order_by(Property.published_at.desc(), Property.id.desc())
        .options(selectinload(Property.city))
        .limit(limit)
    ).all()
    created = 0
    for rank, prop in enumerate(listings):
        # Leave every third listing without photo to keep the empty state visible
        if rank % 3 == 2:
            continue
        count = gallery if rank == 0 else 1 + rank % 2
        for i in range(count):
            content = render(label(prop.category), prop.city.name, i, count)
            path = storage.save_property_photo(prop.id, content)
            db.add(
                PropertyPhoto(
                    property_id=prop.id,
                    file_path=path,
                    alt_text=f"{ALT_PREFIX}, vue {i + 1}",
                    position=i,
                )
            )
            created += 1
    db.commit()
    return created


def remove(db: Session) -> int:
    storage = ImageStorage()
    photos = db.scalars(
        select(PropertyPhoto).where(PropertyPhoto.alt_text.startswith(ALT_PREFIX))
    ).all()
    for photo in photos:
        storage.delete(photo.file_path)
        db.delete(photo)
    db.commit()
    return len(photos)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    add_cmd = sub.add_parser("add", help="add provisional photos to the newest listings")
    add_cmd.add_argument("--limit", type=int, default=8, help="listings considered")
    add_cmd.add_argument("--gallery", type=int, default=5, help="photos on the first listing")
    sub.add_parser("remove", help="delete every provisional photo (files and rows)")
    args = parser.parse_args()
    with SessionLocal() as db:
        if args.command == "add":
            print(f"{add(db, args.limit, args.gallery)} photo(s) provisoire(s) ajoutée(s).")
        else:
            print(f"{remove(db)} photo(s) provisoire(s) supprimée(s).")


if __name__ == "__main__":
    main()
