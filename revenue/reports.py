import argparse
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from .ingestion import ingest
from .model import train, save


def generate(daily, bundle, destination):
    out = Path(destination)
    out.mkdir(parents=True, exist_ok=True)
    plt.style.use("seaborn-v0_8-whitegrid")
    fig, axes = plt.subplots(2, 1, figsize=(11, 8), layout="constrained")
    daily["all"].plot(ax=axes[0], color="#156b87", title="Observed daily revenue: all countries")
    axes[0].set_ylabel("Revenue (source units)")
    daily.drop(columns="all").sum().nlargest(10).sort_values().plot.barh(ax=axes[1], color="#156b87", title="Top 10 countries by total revenue")
    fig.savefig(out/"eda.png", dpi=150)
    plt.close(fig)
    report = bundle["models"]["all"]["report"]
    names = list(report["test"])
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), layout="constrained")
    axes[0].bar(names, [report["test"][n]["mae"] for n in names], color=["#94a3b8", "#156b87", "#e69935"])
    axes[0].set(title="Untouched test set: MAE", ylabel="Revenue error (lower is better)")
    axes[1].plot(report["test_dates"], report["actual"], label="Actual", color="black")
    for name in names:
        label = name + (" (selected)" if name == report["winner"] else "")
        axes[1].plot(report["test_dates"], report["predictions"][name], label=label, linestyle="--" if name == "baseline" else "-", alpha=0.85)
    axes[1].set(title="30-day revenue by forecast start", ylabel="Revenue")
    axes[1].set_xticks(report["test_dates"][::14])
    axes[1].tick_params(axis="x", rotation=20)
    axes[1].legend()
    fig.savefig(out/"model_comparison.png", dpi=150)
    plt.close(fig)
    metrics = {country: item["report"] for country, item in bundle["models"].items()}
    (out/"evaluation.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    summary = {"first_date": str(daily.index.min().date()), "last_date": str(daily.index.max().date()),
               "days": len(daily), "countries": len(daily.columns)-1, "served_countries": list(bundle["models"]),
               "negative_daily_cells": int((daily < 0).sum().sum())}
    (out/"data_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--output", default="reports")
    parser.add_argument("--model", default="models/revenue.pkl")
    args = parser.parse_args()
    daily = ingest(args.source)
    bundle = train(daily)
    save(bundle, args.model)
    generate(daily, bundle, args.output)
    print("Training, EDA and evaluation complete")
