import os
from pathlib import Path
from threading import Lock
from time import perf_counter
from flask import Flask, g, jsonify, request
from werkzeug.exceptions import HTTPException
from .eventlog import EventLog
from .ingestion import ingest
from .model import load, predict, save, train


def create_app(config=None):
    app = Flask(__name__)
    app.config.update(MODEL_PATH=os.getenv("MODEL_PATH", "models/revenue.pkl"),
                      LOG_PATH=os.getenv("LOG_PATH", "logs/events.jsonl"),
                      DATA_DIR=os.getenv("DATA_DIR", "data/raw"))
    app.config.update(config or {})
    log = EventLog(app.config["LOG_PATH"])
    counters = {"requests": 0, "errors": 0, "total_latency_seconds": 0.0}
    lock = Lock()
    train_lock = Lock()

    @app.before_request
    def begin():
        g.start = perf_counter()

    @app.after_request
    def finish(response):
        duration = perf_counter()-g.start
        with lock:
            counters["requests"] += 1
            counters["errors"] += int(response.status_code >= 400)
            counters["total_latency_seconds"] += duration
        log.append("request", path=request.path, status=response.status_code, latency_seconds=duration)
        return response

    @app.errorhandler(HTTPException)
    def http_error(error):
        return jsonify(error=error.description), error.code

    @app.get("/health")
    def health():
        return jsonify(status="ok", model_ready=Path(app.config["MODEL_PATH"]).exists())

    @app.get("/metrics")
    def metrics():
        with lock:
            snapshot = dict(counters)
        snapshot["mean_latency_seconds"] = snapshot["total_latency_seconds"]/max(1, snapshot["requests"])
        return jsonify(snapshot)

    @app.get("/countries")
    def countries():
        if not Path(app.config["MODEL_PATH"]).exists():
            return jsonify(error="Train a model first"), 503
        return jsonify(countries=list(load(app.config["MODEL_PATH"])["models"]))

    @app.post("/train")
    def training():
        if not train_lock.acquire(blocking=False):
            return jsonify(error="Training already running"), 409
        try:
            bundle = train(ingest(app.config["DATA_DIR"]))
            save(bundle, app.config["MODEL_PATH"])
            log.append("training", version=bundle["version"], countries=list(bundle["models"]))
            return jsonify(version=bundle["version"], countries=list(bundle["models"]))
        except ValueError as error:
            return jsonify(error=str(error)), 400
        finally:
            train_lock.release()

    @app.post("/predict")
    def prediction():
        payload = request.get_json()
        if not isinstance(payload, dict):
            return jsonify(error="Expected a JSON object"), 400
        if set(payload)-{"country", "date"}:
            return jsonify(error="Supported fields: country, date"), 400
        country, date = payload.get("country", "all"), payload.get("date")
        if not isinstance(country, str) or (date is not None and not isinstance(date, str)):
            return jsonify(error="country and date must be strings"), 400
        if not Path(app.config["MODEL_PATH"]).exists():
            return jsonify(error="Train a model first"), 503
        try:
            result = predict(load(app.config["MODEL_PATH"]), country, date)
        except ValueError as error:
            return jsonify(error=str(error)), 400
        log.append("prediction", **result)
        return jsonify(result)

    @app.get("/logs")
    def logs():
        return jsonify(events=log.read()[-100:])

    return app
