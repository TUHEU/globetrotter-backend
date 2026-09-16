# =============================================================================
# storage.py  -  ITINERARY SERVICE's OWN DATABASE
#
# Owns: the destination catalogue, itineraries (trips), and favorites.
#
# WHY DESTINATIONS LIVE HERE AND NOT IN THEIR OWN SERVICE
# ---------------------------------------------------------
# The assignment names exactly three data-owning services (User, Itinerary,
# Recommendation-with-no-data) plus a Gateway. Destinations don't have their
# own noun in that list, but every itinerary "stop" IS a destination
# reference (see the `stops` field below) - they're the same trip-planning
# domain, just two tables of it. Splitting them into a fourth data-owning
# service would technically go beyond the spec, so they stay here, next to
# the itineraries that reference them. Recommendation Service still reaches
# them the required way: an HTTP call to GET /destinations on THIS service,
# never by reading this file.
#
# Same JSON-file simplification as every other service in this project -
# see user-service/app/storage.py for the fuller explanation.
# =============================================================================

import copy
import json
import os
import threading
import uuid
from pathlib import Path

from app.seed import SEED_DESTINATIONS

# ITINERARY_DB_PATH: same idea as USER_DB_PATH in user-service/app/storage.py
# - lets Recommendation Service's integration tests run a throwaway copy of
# this service against its own temp file instead of the real data.
DB_PATH = Path(os.environ.get("ITINERARY_DB_PATH") or (Path(__file__).resolve().parent.parent / "data" / "itinerary_db.json"))

_lock = threading.Lock()


def _empty_db() -> dict:
    return {
        # BUG FIX - deep-copy, don't hand out the SAME list object every
        # time. This used to be `"destinations": SEED_DESTINATIONS` - every
        # test that created a fresh "empty" database (via isolated_database
        # in conftest.py) got the identical in-memory list SEED_DESTINATIONS
        # points to, not a copy of it. apply_create()'s
        # `db["destinations"].append(record)` therefore mutated that ONE
        # shared list permanently for the rest of the test process -
        # a destination created by one test (often with bare-minimum
        # fields, like no history) leaked into every test that ran after
        # it, including ones asserting things about "all seed destinations"
        # (see test_the_history_is_substantial). A deep copy means each
        # fresh database genuinely starts from its own independent seed,
        # exactly as "empty database" implies - this also protects the
        # real, running server the same way if it's ever reset/reseeded.
        "destinations": copy.deepcopy(SEED_DESTINATIONS),
        "itineraries": [],
        "favorites": {},
        # Pending/approved/rejected proposals from regular users to
        # create/edit/delete a destination - see routers/
        # destination_requests.py. Regular travellers can no longer write
        # to "destinations" directly; only an admin's approval does that.
        "destination_requests": [],
        # Ratings/comments/likes - see app/social.py.
        "destination_ratings": {},  # {destination_id: {user_id: 1-5}}
        "destination_comments": [],  # [{id, destination_id, user_id, text, created_at}]
        "destination_likes": {},  # {destination_id: [user_id, ...]}
    }


def uploads_dir() -> Path:
    """Folder where uploaded destination photos/videos are stored. Created
    on first use, next to itinerary_db.json (so tests that monkeypatch
    DB_PATH move this too - see tests/conftest.py)."""
    directory = DB_PATH.parent / "uploads"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _read_db() -> dict:
    if not DB_PATH.exists():
        db = _empty_db()
        _write_db(db)
        return db
    with open(DB_PATH, "r", encoding="utf-8") as f:
        db = json.load(f)
    for key, default in _empty_db().items():
        if key != "destinations":  # never overwrite the seeded destinations
            db.setdefault(key, default)
    return db


def _write_db(db: dict) -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def read_db() -> dict:
    with _lock:
        return _read_db()


def update_db(mutate_fn) -> dict:
    with _lock:
        db = _read_db()
        result = mutate_fn(db)
        _write_db(db)
        return result
