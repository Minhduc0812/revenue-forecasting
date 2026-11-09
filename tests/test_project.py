import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd
from revenue.api import create_app
from revenue.eventlog import EventLog
from revenue.ingestion import ingest
from revenue.model import features, load, predict, save, supervised, train, train_one
from revenue.monitoring import evaluate
from download_data import download


def example_daily():
    dates = pd.date_range("2020-01-01", periods=420)
    values = 100+np.arange(420)*0.1+10*np.sin(np.arange(420)*2*np.pi/7)
    return pd.DataFrame({"United Kingdom": values, "France": values/2, "all": values*1.5}, index=dates)


class ModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.daily = example_daily()
        cls.bundle = train(cls.daily, top_countries=2)

    def test_target_is_exactly_next_30_days(self):
        series = self.daily["all"]
        x, y, dates = supervised(series)
        self.assertAlmostEqual(y[0], series.iloc[90:120].sum())
        self.assertAlmostEqual(x[0, 3], series.iloc[60:90].mean())
        self.assertEqual(dates[0], series.index[90])

    def test_features_ignore_future(self):
        values = self.daily["all"].to_numpy().copy()
        before = features(values[:100], self.daily.index[100])
        values[100:] = 1e12
        np.testing.assert_array_equal(before, features(values[:100], self.daily.index[100]))

    def test_all_and_country_prediction(self):
        for country in ["all", "France"]:
            result = predict(self.bundle, country)
            self.assertTrue(np.isfinite(result["revenue"]))
            self.assertEqual(result["horizon_days"], 30)
            self.assertEqual(result["country"], country)

    def test_invalid_country_date_and_short_history(self):
        for country, date in [("missing", None), ("all", "not-a-date"), ("all", "2035-01-01"), ("all", "2020-02-01")]:
            with self.assertRaises(ValueError):
                predict(self.bundle, country, date)
        with self.assertRaises(ValueError):
            train_one(self.daily["all"].iloc[:100])
        with self.assertRaises(ValueError):
            features([float("nan")]*90, pd.Timestamp("2020-01-01"))

    def test_purged_splits_and_selection(self):
        report = self.bundle["models"]["all"]["report"]
        self.assertLess(report["train_last_target"], report["validation_first_origin"])
        self.assertLess(report["validation_last_target"], report["test_first_origin"])
        self.assertEqual(report["winner"], min(report["validation"], key=lambda n: report["validation"][n]["mae"]))
        self.assertEqual(set(report["test"]), {"baseline", "ridge", "random_forest"})

    def test_historical_predictions_do_not_read_future(self):
        date = str(self.daily.index[380].date())
        expected = predict(self.bundle, "all", date)
        changed = dict(self.bundle)
        changed["daily"] = self.daily.copy()
        changed["daily"].loc[date:, "all"] = 1e12
        self.assertEqual(expected, predict(changed, "all", date))

    def test_atomic_round_trip_uses_temporary_model_directory(self):
        with TemporaryDirectory() as directory:
            path = Path(directory)/"models"/"model.pkl"
            save(self.bundle, path)
            self.assertEqual(predict(self.bundle), predict(load(path)))
            self.assertEqual(list(path.parent.glob("*.tmp")), [])


class IngestionTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        self.rows = [dict(country="France", customer_id=1, day=1, invoice="A123", month=1,
                          total_price=10, StreamID="x", TimesViewed=50, year=2020),
                     dict(country="France", customer_id=1, day=3, invoice="A124", month=1,
                          total_price=-2, StreamID="x", TimesViewed=2, year=2020)]

    def write(self):
        (self.path/"part.json").write_text(json.dumps(self.rows), encoding="utf-8")

    def test_aliases_refunds_missing_days_and_idempotence(self):
        self.write()
        result = ingest(self.path)
        self.assertEqual(result["all"].tolist(), [10, 0, -2])
        self.assertEqual(result["France"].sum(), 8)
        pd.testing.assert_frame_equal(result, ingest(self.path))

    def test_reject_empty_directory(self):
        with self.assertRaises(ValueError):
            ingest(self.path)

    def test_reject_missing_columns(self):
        del self.rows[0]["country"]
        del self.rows[1]["country"]
        self.write()
        with self.assertRaises(ValueError):
            ingest(self.path)

    def test_reject_invalid_date(self):
        self.rows[0]["month"] = 13
        self.write()
        with self.assertRaises(ValueError):
            ingest(self.path)

    def test_reject_missing_price(self):
        self.rows[0]["total_price"] = None
        self.write()
        with self.assertRaises(ValueError):
            ingest(self.path)


class LoggingTests(unittest.TestCase):
    def test_round_trip_append_and_isolation(self):
        with TemporaryDirectory() as directory:
            log = EventLog(Path(directory)/"logs"/"events.jsonl")
            self.assertEqual(log.read(), [])
            log.append("prediction", country="Việt Nam", revenue=12.5)
            log.append("prediction", country="all", revenue=20)
            records = log.read()
            self.assertEqual(len(records), 2)
            self.assertEqual(records[0]["country"], "Việt Nam")
            self.assertIn("timestamp", records[0])
            with self.assertRaises(ValueError):
                log.append("prediction", revenue=float("nan"))
            self.assertEqual(len(log.read()), 2)


class APITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = train(example_daily(), top_countries=2)

    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.config = {"TESTING": True, "MODEL_PATH": str(root/"models/model.pkl"),
                       "LOG_PATH": str(root/"logs/events.jsonl"), "DATA_DIR": str(root/"raw")}
        self.client = create_app(self.config).test_client()

    def test_health_untrained_and_metrics(self):
        self.assertFalse(self.client.get("/health").json["model_ready"])
        self.assertEqual(self.client.post("/predict", json={}).status_code, 503)
        metrics = self.client.get("/metrics").json
        self.assertEqual(metrics["requests"], 2)
        self.assertEqual(metrics["errors"], 1)
        self.assertGreaterEqual(metrics["mean_latency_seconds"], 0)

    def test_predict_country_all_and_logs(self):
        save(self.bundle, self.config["MODEL_PATH"])
        for country in ["France", "all"]:
            response = self.client.post("/predict", json={"country": country})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json["country"], country)
        events = self.client.get("/logs").json["events"]
        self.assertEqual(sum(r["event"] == "prediction" for r in events), 2)
        self.assertIn("France", self.client.get("/countries").json["countries"])

    def test_invalid_inputs(self):
        save(self.bundle, self.config["MODEL_PATH"])
        for payload in [[], {"country": []}, {"country": "unknown"}, {"date": "invalid"}, {"duration": 5}]:
            self.assertEqual(self.client.post("/predict", json=payload).status_code, 400)
        self.assertEqual(self.client.post("/predict", data="{", content_type="application/json").status_code, 400)
        self.assertEqual(self.client.get("/missing").status_code, 404)

    def test_train_endpoint_writes_only_configured_paths(self):
        with patch("revenue.api.ingest", return_value=example_daily()) as ingest_mock:
            result = self.client.post("/train")
        ingest_mock.assert_called_once_with(self.config["DATA_DIR"])
        self.assertEqual(result.status_code, 200)
        self.assertTrue(Path(self.config["MODEL_PATH"]).exists())
        self.assertTrue(Path(self.config["LOG_PATH"]).exists())
        self.assertEqual(self.client.post("/predict", json={}).status_code, 200)

    def test_train_missing_data(self):
        self.assertEqual(self.client.post("/train").status_code, 400)


class MonitoringTests(unittest.TestCase):
    def test_only_mature_forecasts_deduplicated(self):
        daily = example_daily()
        record = {"event": "prediction", "country": "all", "version": "test", "model": "baseline",
                  "forecast_start": "2020-01-01", "forecast_end": "2020-01-30",
                  "revenue": float(daily["all"].iloc[:30].sum())}
        future = {**record, "forecast_start": "2030-01-01", "forecast_end": "2030-01-30"}
        result = evaluate([record, record, future], daily)
        self.assertEqual(result[0]["matured_forecasts"], 1)
        self.assertEqual(result[0]["mae"], 0)
        self.assertEqual(evaluate([future], daily), [])


class DownloadTests(unittest.TestCase):
    def test_download_pins_commit_and_keeps_manifest_outside_raw(self):
        with TemporaryDirectory() as directory:
            destination = Path(directory)/"raw"
            content = b'[{"country":"France"}]'
            def response(url):
                if url.endswith("/commits/master"):
                    return b'{"sha":"commit123"}'
                if "/git/trees/commit123" in url:
                    return json.dumps({"sha":"tree456", "tree":[{"path":"cs-train/part.json", "size":len(content)}]}).encode()
                self.assertIn("/commit123/cs-train/part.json", url)
                return content
            with patch("download_data.get", side_effect=response):
                download(destination, "cs-train")
            self.assertEqual(list(destination.glob("*.json")), [destination/"part.json"])
            self.assertEqual(json.loads((destination.parent/"raw-manifest.json").read_text())["commit"], "commit123")
