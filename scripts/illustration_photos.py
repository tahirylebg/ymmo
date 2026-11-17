"""Give demo listings an illustration photo matching their category (CC0 images).

The demo data has no real pictures, and 344 identical placeholders read as a template. This
script picks, for every listing on sale that has no photo yet, one to three royalty-free photos of
its category (apartment, house, land, office, retail, warehouse) from `scripts/stock_photos/`.
Sources, authors and licences are listed in `docs/photos-libres.md` (all CC0 / public domain).

Each photo goes through the same storage as a back-office upload (`ImageStorage`: resized
WebP + thumbnail), so it behaves exactly like an agent's picture. The alt text starts with
"Photo d’illustration libre de droits": visitors are told it is not the actual property, and
`remove` finds them again. Listings that already have photos are never touched, and `add` does
nothing once illustrations exist (it runs at every container start: listings created later by
staff, still waiting for their real photos, must not get stock pictures).

Usage (inside the app container):
    python -m scripts.illustration_photos add [--gallery-every 4] [--force]
    python -m scripts.illustration_photos remove
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models import Property, PropertyPhoto
from app.models.enums import PropertyStatus
from app.services.image_service import ImageStorage

ALT_PREFIX = "Photo d’illustration libre de droits"
STOCK_DIR = Path(__file__).resolve().parent / "stock_photos"


def stock() -> dict[str, list[bytes]]:
    """Image bytes per category value, in manifest order."""
    manifest = json.loads((STOCK_DIR / "manifest.json").read_text(encoding="utf-8"))
    return {
        category: [(STOCK_DIR / entry["file"]).read_bytes() for entry in entries]
        for category, entries in manifest.items()
    }


def _illustrated(db: Session) -> bool:
    marker = PropertyPhoto.alt_text.startswith(ALT_PREFIX)
    return db.scalar(select(PropertyPhoto.id).where(marker).limit(1)) is not None


def add(
    db: Session,
    gallery_every: int = 4,
    storage: ImageStorage | None = None,
    force: bool = False,
) -> int:
    storage = storage or ImageStorage()
    if _illustrated(db) and not force:
        return 0
    photos = stock()
    listings = db.scalars(
        # Listings on sale only: the sold history (thousands of rows) is never shown as cards.
        select(Property)
        .where(Property.status != PropertyStatus.SOLD, ~Property.photos.any())
        .order_by(Property.id)
    ).all()
    saved: list[str] = []  # files written so far, deleted again if anything fails
    try:
        for prop in listings:
            choices = photos.get(prop.category.value)
            if not choices:
                continue
            # One cover photo; every n-th listing gets a small gallery (detail page layout).
            count = min(3, len(choices)) if gallery_every and prop.id % gallery_every == 0 else 1
            for position in range(count):
                content = choices[(prop.id + position) % len(choices)]
                saved.append(storage.save_property_photo(prop.id, content))
                db.add(
                    PropertyPhoto(
                        property_id=prop.id,
                        file_path=saved[-1],
                        alt_text=f"{ALT_PREFIX}, vue {position + 1}",
                        position=position,
                    )
                )
        db.commit()
    except BaseException:  # nothing half done: no rows, no orphan files
        db.rollback()
        for path in saved:
            storage.delete(path)
        raise
    return len(saved)


def remove(db: Session, storage: ImageStorage | None = None) -> int:
    storage = storage or ImageStorage()
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
    add_cmd = sub.add_parser("add", help="illustrate every listing that has no photo")
    add_cmd.add_argument(
        "--gallery-every", type=int, default=4, help="every n-th listing gets 3 photos (0: never)"
    )
    add_cmd.add_argument(
        "--force", action="store_true", help="also run when illustrations already exist"
    )
    sub.add_parser("remove", help="delete every illustration photo (files and rows)")
    args = parser.parse_args()
    with SessionLocal() as db:
        if args.command == "add":
            created = add(db, args.gallery_every, force=args.force)
            print(f"{created} photo(s) d’illustration ajoutée(s).")
        else:
            print(f"{remove(db)} photo(s) d’illustration supprimée(s).")


if __name__ == "__main__":
    main()
