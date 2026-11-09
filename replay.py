"""Simulate daily historical requests and evaluate matured forecasts."""
import argparse
from pathlib import Path
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from revenue.eventlog import EventLog
from revenue.model import load, predict
from revenue.monitoring import evaluate


def replay(bundle, destination, days=30):
    out = Path(destination)
    out.mkdir(parents=True, exist_ok=True)
    log = EventLog(out/"replay.jsonl")
    daily = bundle["daily"]
    # All labels for these origins are present; each prediction refits on its past.
    dates = daily.index[-(days+29):-29]
    actual, predicted = [], []
    for date in dates:
        result = predict(bundle, "all", str(date.date()))
        log.append("prediction", **result)
        predicted.append(result["revenue"])
        actual.append(float(daily.loc[result["forecast_start"]:result["forecast_end"], "all"].sum()))
    metrics = evaluate(log.read(), daily)
    (out/"monitoring.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    fig, ax = plt.subplots(figsize=(10, 4), layout="constrained")
    ax.plot(dates, actual, label="Actual", color="black")
    ax.plot(dates, predicted, label="Forecast using only prior observations", color="#156b87")
    ax.set(title="Historical daily replay: 30-day revenue", ylabel="Revenue (source units)", xlabel="Forecast start")
    ax.set_xticks(dates[::7], labels=dates[::7].strftime("%Y-%m-%d"))
    ax.legend()
    fig.savefig(out/"monitoring.png", dpi=150)
    plt.close(fig)
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="models/revenue.pkl")
    parser.add_argument("--output", default="reports/replay")
    args = parser.parse_args()
    replay(load(args.model), args.output)
