"""Illustration photos: one per listing (by category), stored like a back-office upload."""

import json

from sqlalchemy import select

from app.models import PropertyPhoto
from app.services.image_service import ImageStorage
from scripts.illustration_photos import ALT_PREFIX, STOCK_DIR, add, remove


def test_stock_photos_are_documented_and_free():
    manifest = json.loads((STOCK_DIR / "manifest.json").read_text(encoding="utf-8"))
    assert set(manifest) == {"apartment", "house", "land", "office", "retail", "warehouse"}
    for entries in manifest.values():
        for entry in entries:
            assert (STOCK_DIR / entry["file"]).is_file()
            assert entry["license"] in {"CC0", "Public domain"}
            assert entry["source"].startswith("https://commons.wikimedia.org/")


def test_add_illustrates_listings_without_photo_then_remove(db, world, tmp_path):
    storage = ImageStorage(tmp_path)
    created = add(db, gallery_every=0, storage=storage)
    assert created == 3  # flat, house, office: one cover each

    photos = db.scalars(select(PropertyPhoto)).all()
    listings = {world["flat"].id, world["house"].id, world["office"].id}
    assert {p.property_id for p in photos} == listings
    assert all(p.alt_text.startswith(ALT_PREFIX) for p in photos)
    for photo in photos:  # same files as an upload: WebP + thumbnail
        assert (tmp_path / photo.file_path).is_file()
        assert (tmp_path / photo.file_path.replace(".webp", "_thumb.webp")).is_file()

    assert add(db, storage=storage) == 0  # listings with photos are left alone
    assert remove(db, storage=storage) == 3
    assert not list(tmp_path.rglob("*.webp"))
