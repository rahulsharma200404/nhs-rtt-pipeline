import csv
import re
import requests
from collections import defaultdict

PAGES = [
    "https://www.england.nhs.uk/statistics/statistical-work-areas/rtt-waiting-times/rtt-data-2024-25/",
    "https://www.england.nhs.uk/statistics/statistical-work-areas/rtt-waiting-times/rtt-data-2025-26/",
]

HEADERS = {"User-Agent": "Mozilla/5.0"}

MONTHS = {
    "jan": "01", "feb": "02", "mar": "03", "apr": "04",
    "may": "05", "jun": "06", "jul": "07", "aug": "08",
    "sep": "09", "oct": "10", "nov": "11", "dec": "12",
}

MONTH_IN_NAME = re.compile(r"Full-CSV-data-file-([A-Za-z]{3})(\d{2})", re.IGNORECASE)

candidates = defaultdict(list)

for page in PAGES:
    html = requests.get(page, headers=HEADERS, timeout=30).text
    zips = sorted(set(re.findall(r'href="([^"]+\.zip)"', html)))
    matched = 0
    for url in zips:
        m = MONTH_IN_NAME.search(url)
        if not m:
            continue
        mon, yy = m.group(1).lower(), m.group(2)
        candidates[f"20{yy}-{MONTHS[mon]}"].append(url)
        matched += 1
    print(f"{page}\n  {len(zips)} zips found, {matched} matched a month")

# Where a month has both an original and a revised file, take the latest revision.
final = {}
for month, urls in candidates.items():
    revised = [u for u in urls if "revised" in u.lower()]
    final[month] = sorted(revised)[-1] if revised else sorted(urls)[-1]

rows = sorted(final.items())

with open("pipeline/manifest.csv", "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["month", "url"])
    writer.writerows(rows)

print(f"\nWrote {len(rows)} rows to pipeline/manifest.csv")
if rows:
    print(f"Range: {rows[0][0]} to {rows[-1][0]}")
    print("Months:", ", ".join(m for m, _ in rows))