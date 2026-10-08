#!/usr/bin/env python3
"""Restore the exact font bytes required by the 2026-10-05 Unity checkpoint."""
import argparse
import hashlib
import lzma
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
ARCHIVE = ROOT / "backup-assets/fonts/NotoSansCJKsc-Regular.otf.xz"
TARGET = ROOT / "unity/Assets/DesertRV/UI/Fonts/NotoSansCJKsc-Regular.otf"
ARCHIVE_SHA256 = "e8affaf0b8f8e8fccecf5476bf05999c891f94ef66ef9b55474fda32ce1ec786"
FONT_SHA256 = "a6a530f3e7e7a2c299470c42efff2e109fcc0a5be92686b96d5e84a05f3ecb2b"
FONT_SIZE = 16437340

def digest(data):
    return hashlib.sha256(data).hexdigest()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", action="store_true", help="Check restored font without writing")
    args = parser.parse_args()
    packed = ARCHIVE.read_bytes()
    if digest(packed) != ARCHIVE_SHA256:
        raise ValueError("Compressed font SHA256 mismatch; refusing restoration")
    if TARGET.exists():
        existing = TARGET.read_bytes()
        if len(existing) != FONT_SIZE or digest(existing) != FONT_SHA256:
            raise ValueError("Existing font differs from the checkpoint; refusing to overwrite it")
        print("OK: restored font matches the checkpoint SHA256")
        return
    if args.verify_only:
        raise FileNotFoundError("Font is missing; run this script without --verify-only before opening Unity")
    data = lzma.decompress(packed)
    if len(data) != FONT_SIZE or digest(data) != FONT_SHA256:
        raise ValueError("Decompressed font size or SHA256 mismatch; refusing restoration")
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=TARGET.parent, prefix=".restore-font-", delete=False) as tmp:
        temporary = Path(tmp.name)
        tmp.write(data)
    try:
        if TARGET.exists():
            raise FileExistsError("Font appeared during restoration; refusing to overwrite it")
        temporary.replace(TARGET)
    finally:
        temporary.unlink(missing_ok=True)
    if digest(TARGET.read_bytes()) != FONT_SHA256:
        raise ValueError("Post-write font verification failed")
    print("Restored exact Noto font: " + FONT_SHA256)

if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, lzma.LZMAError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        sys.exit(1)
