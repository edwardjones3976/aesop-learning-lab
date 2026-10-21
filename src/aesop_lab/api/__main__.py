"""Run the explicitly gated development-fixture local API."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone

from aesop_lab.storage.sqlite import SQLiteStore

from .dev_fixture import CONCEPT, fixture_items
from .http import serve
from .service import LearningService


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--development-fixtures", action="store_true",
                        help="required; serves unreviewed sample content only")
    parser.add_argument("--db", default="aesop-dev.sqlite3")
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    if not args.development_fixtures:
        parser.error("reviewed content integration is pending; pass --development-fixtures")
    with SQLiteStore(args.db) as store:
        service = LearningService(store, CONCEPT, fixture_items(), reviewed=False,
                                  allow_development_fixtures=True)
        # The fixture content and learner are synthetic; record consent explicitly
        # so the server-side gate stays in force for every other path.
        store.confirm_consent(datetime.now(timezone.utc))
        service.complete_lesson()
        print(f"Development fixture API on http://127.0.0.1:{args.port}", flush=True)
        serve(service, args.port)


if __name__ == "__main__":
    main()
