
import re
import zipfile
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = REPO_ROOT / "data" / "raw"
STAGED_DIR = REPO_ROOT / "data" / "staged"

# Commissioner columns are summed away anyway. 'Total' is unreliable: it is
# null on incomplete-pathway rows. 'Total All' is the populated one.
DROP_COLS = {
    "Commissioner Parent Org Code",
    "Commissioner Parent Name",
    "Commissioner Org Code",
    "Commissioner Org Name",
    "Total",
}

RENAMES = {
    "Provider Parent Org Code": "provider_parent_code",
    "Provider Parent Name": "provider_parent_name",
    "Provider Org Code": "provider_code",
    "Provider Org Name": "provider_name",
    "Treatment Function Code": "specialty_code",
    "Treatment Function Name": "specialty_name",
    "Total All": "reported_total",
    "Patients with unknown clock start date": "Unknown clock start",
}

ID_COLS = [
    "provider_parent_code", "provider_parent_name",
    "provider_code", "provider_name",
    "specialty_code", "specialty_name",
]

BAND_PATTERN = re.compile(r"^Gt \d+")


def transform_month(month):
    with zipfile.ZipFile(RAW_DIR / f"{month}.zip") as archive:
        with archive.open(archive.namelist()[0]) as handle:
            df = pd.read_csv(handle, usecols=lambda c: c not in DROP_COLS)

    rows_in = len(df)

    df = df[df["RTT Part Type"] == "Part_2"]
    df = df[df["Treatment Function Name"] != "Total"]
    df = df.rename(columns=RENAMES).copy()

    band_cols = [c for c in df.columns if BAND_PATTERN.match(c)]
    value_cols = band_cols + ["Unknown clock start"]

    # Nulls here mean "no patients", so make that explicit before any arithmetic.
    df[value_cols + ["reported_total"]] = df[value_cols + ["reported_total"]].fillna(0)

    grouped = df.groupby(ID_COLS, dropna=False, as_index=False)[
        value_cols + ["reported_total"]
    ].sum()

    # Reconcile before reshaping: bands plus unknowns should equal the reported total.
    grouped["_check"] = grouped[value_cols].sum(axis=1) - grouped["reported_total"]
    mismatches = int((grouped["_check"] != 0).sum())
    grouped = grouped.drop(columns=["_check", "reported_total"])

    long = grouped.melt(
        id_vars=ID_COLS,
        value_vars=value_cols,
        var_name="band_label",
        value_name="patients",
    )

    long = long[long["patients"] > 0]
    long.insert(0, "month", month)

    STAGED_DIR.mkdir(parents=True, exist_ok=True)
    out_path = STAGED_DIR / f"{month}.parquet"
    long.to_parquet(out_path, index=False)

    return {
        "month": month,
        "rows_in": rows_in,
        "groups": len(grouped),
        "rows_out": len(long),
        "patients": int(long["patients"].sum()),
        "mismatches": mismatches,
        "size_mb": out_path.stat().st_size / 1_000_000,
    }


def main():
    months = sorted(p.stem for p in RAW_DIR.glob("*.zip"))
    total_mismatches = 0

    for month in months:
        s = transform_month(month)
        total_mismatches += s["mismatches"]
        flag = "  MISMATCH" if s["mismatches"] else ""
        print(
            f"  {s['month']}  {s['rows_in']:>7,} raw -> {s['groups']:>6,} groups"
            f" -> {s['rows_out']:>7,} rows   {s['patients']:>10,} patients"
            f"   ({s['size_mb']:.1f} MB){flag}"
        )

    print(f"\n{len(months)} months, {total_mismatches} mismatches")


if __name__ == "__main__":
    main()