"""Persist named demo portraits and add their matches to the frontend manifest."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = BACKEND_ROOT.parent
sys.path.insert(0, str(BACKEND_ROOT))

from src.db.database import SessionLocal  # noqa: E402
from src.services.demo_people_service import (  # noqa: E402
    analyze_demo_people,
    build_demo_people_manifest,
    ingest_demo_people,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--face-dir", type=Path, default=REPOSITORY_ROOT / "faces")
    parser.add_argument("--user-email", default="demo@atelier.local")
    parser.add_argument(
        "--manifest-path",
        type=Path,
        default=REPOSITORY_ROOT / "frontend" / "src" / "lib" / "demo-data.json",
    )
    parser.add_argument(
        "--public-dir",
        type=Path,
        default=REPOSITORY_ROOT / "frontend" / "public" / "demo" / "people",
    )
    args = parser.parse_args()

    analyses = analyze_demo_people(args.face_dir.resolve())
    manifest = json.loads(args.manifest_path.read_text(encoding="utf-8"))

    db = SessionLocal()
    try:
        results = ingest_demo_people(
            db,
            analyses=analyses,
            user_email=args.user_email,
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    args.public_dir.mkdir(parents=True, exist_ok=True)
    for analysis in analyses:
        for portrait in analysis.portrait_paths:
            shutil.copy2(portrait, args.public_dir / portrait.name)

    manifest["people"] = build_demo_people_manifest(
        results,
        photos=manifest["photos"],
    )
    args.manifest_path.write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "people": len(results),
                "portraits": sum(len(item.portraits) for item in results),
                "matched_photos": {
                    item.name: len(item.matches) for item in results
                },
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
