"""
Extract stage: download the monthly RTT zip files listed in the manifest.

Idempotent by design. A month already present in data/raw is skipped, so
re-running this costs nothing and changes nothing.
"""

import csv
import sys
from pathlib import Path

import requests

# Resolve paths from this file's location rather than the current working
# directory, so the script behaves the same however it gets launched.
REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST = REPO_ROOT / "pipeline" / "manifest.csv"
RAW_DIR = REPO_ROOT / "data" / "raw"

HEADERS = {"User-Agent": "Mozilla/5.0"}
TIMEOUT = 60


def read_manifest(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def download(url, destination):
    """Download url to destination via a temp file, so a failure leaves nothing usable behind."""
    temp = destination.parent / (destination.name + ".tmp")

    response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    response.raise_for_status()

    temp.write_bytes(response.content)
    temp.rename(destination)
    return len(response.content)


def main():
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    rows = read_manifest(MANIFEST)
    fetched = 0
    skipped = 0
    failed = []

    for row in rows:
        month = row["month"]
        destination = RAW_DIR / f"{month}.zip"

        if destination.exists():
            print(f"  skip   {month}")
            skipped += 1
            continue

        try:
            size = download(row["url"], destination)
            print(f"  fetch  {month}  ({size / 1_000_000:.1f} MB)")
            fetched += 1
        except Exception as error:
            print(f"  FAIL   {month}  {error}")
            failed.append(month)

    print(f"\nfetched {fetched}, skipped {skipped}, failed {len(failed)}")

    if failed:
        print("failed months:", ", ".join(failed))
        sys.exit(1)


if __name__ == "__main__":
    main()