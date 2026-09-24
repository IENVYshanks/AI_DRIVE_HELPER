"""Analyze and persist the fixed public-demo image collection."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = BACKEND_ROOT.parent
sys.path.insert(0, str(BACKEND_ROOT))

from src.db.database import SessionLocal  # noqa: E402
from src.services.demo_ingestion_service import (  # noqa: E402
    analyze_demo_assets,
    build_demo_manifest,
    ingest_demo_assets,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--asset-dir", type=Path, default=REPOSITORY_ROOT / "asset")
    parser.add_argument("--user-email", default="demo@atelier.local")
    parser.add_argument(
        "--manifest-path",
        type=Path,
        default=REPOSITORY_ROOT / "frontend" / "src" / "lib" / "demo-data.json",
    )
    parser.add_argument("--skip-storage", action="store_true")
    parser.add_argument(
        "--manifest-only",
        action="store_true",
        help="Generate frontend data without writing external services",
    )
    args = parser.parse_args()

    analyses = analyze_demo_assets(args.asset_dir.resolve())
    manifest = build_demo_manifest(analyses)
    args.manifest_path.parent.mkdir(parents=True, exist_ok=True)
    args.manifest_path.write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )
    if args.manifest_only:
        print(
            json.dumps(
                {
                    "photos": len(manifest["photos"]),
                    "faces": len(manifest["faces"]),
                    "matches": len(manifest["matches"]),
                },
                indent=2,
            )
        )
        return

    db = SessionLocal()
    try:
        result = ingest_demo_assets(
            db,
            analyses=analyses,
            user_email=args.user_email,
            upload_originals=not args.skip_storage,
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    print(json.dumps(result.__dict__, indent=2))


if __name__ == "__main__":
    main()
