"""Normalize the AAVAIL course JSON schema, without guessing column positions."""
import argparse
from pathlib import Path
import numpy as np
import pandas as pd

ALIASES = {"StreamID": "stream_id", "TimesViewed": "times_viewed", "total_price": "price"}
REQUIRED = {"country", "customer_id", "day", "invoice", "month", "price", "stream_id", "times_viewed", "year"}


def ingest(source):
    files = sorted(Path(source).glob("*.json"))
    if not files:
        raise ValueError("No JSON files in source directory")
    frames = []
    for file in files:
        frame = pd.read_json(file).rename(columns=ALIASES)
        if frame.columns.duplicated().any() or not REQUIRED.issubset(frame.columns):
            raise ValueError(f"Invalid columns in {file.name}: expected {sorted(REQUIRED)}")
        if frame.empty:
            raise ValueError(f"Empty file: {file.name}")
        frame["date"] = pd.to_datetime(frame[["year", "month", "day"]], errors="raise")
        frame["price"] = pd.to_numeric(frame["price"], errors="raise")
        if not np.isfinite(frame["price"]).all():
            raise ValueError(f"Non-finite revenue in {file.name}")
        if frame["country"].isna().any() or frame["country"].astype(str).str.strip().eq("").any():
            raise ValueError(f"Missing country in {file.name}")
        frame["country"] = frame["country"].astype(str).str.strip()
        if frame["country"].str.lower().eq("all").any():
            raise ValueError("Country name 'all' is reserved")
        frames.append(frame[["date", "country", "price"]])
    data = pd.concat(frames, ignore_index=True)
    # Retain signed amounts (refunds) and repeated rows: no verified transaction key.
    dates = pd.date_range(data.date.min(), data.date.max(), freq="D")
    daily = data.groupby(["date", "country"])["price"].sum().unstack(fill_value=0)
    daily = daily.reindex(dates, fill_value=0).astype(float)
    daily["all"] = daily.sum(axis=1)
    daily.index.name = "date"
    return daily


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--output", default="data/processed/daily.csv")
    args = parser.parse_args()
    daily = ingest(args.source)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    daily.to_csv(args.output)
    print(f"Saved {len(daily)} days and {len(daily.columns)-1} countries to {args.output}")
