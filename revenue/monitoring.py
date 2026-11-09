"""Evaluate only forecasts whose entire 30-day actual window is observed."""
import argparse
import json
from pathlib import Path
import pandas as pd
from .eventlog import EventLog
from .ingestion import ingest
from .model import score


def evaluate(events, daily):
    grouped = {}
    seen = set()
    for record in events:
        if record.get("event") != "prediction":
            continue
        start, end = pd.Timestamp(record["forecast_start"]), pd.Timestamp(record["forecast_end"])
        country = record["country"]
        key = (country, record["version"], record["model"])
        identity = (*key, str(start))
        if identity in seen or country not in daily or start < daily.index.min() or end > daily.index.max():
            continue
        actuals = daily.loc[start:end, country]
        if len(actuals) != 30:
            continue
        seen.add(identity)
        grouped.setdefault(key, []).append((float(actuals.sum()), record["revenue"]))
    return [{"country": k[0], "version": k[1], "model": k[2], "matured_forecasts": len(rows),
             **score([r[0] for r in rows], [r[1] for r in rows])} for k, rows in grouped.items()]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--logs", default="logs/events.jsonl")
    parser.add_argument("--output", default="reports/monitoring.json")
    args = parser.parse_args()
    result = evaluate(EventLog(args.logs).read(), ingest(args.source))
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
