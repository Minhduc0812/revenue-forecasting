"""Direct 30-day forecasting with purged chronological model selection."""
from datetime import datetime, timezone
import os
from pathlib import Path
import pickle
import tempfile
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

HORIZON = 30
LOOKBACK = 90


def features(values, date):
    values = np.asarray(values, dtype=float)
    if len(values) < LOOKBACK or not np.isfinite(values).all():
        raise ValueError("Need at least 90 finite historical daily revenues")
    recent = values[-LOOKBACK:]
    return np.array([recent[-1], recent[-7:].mean(), recent[-14:].mean(),
                     recent[-30:].mean(), recent.mean(), recent[-30:].std(),
                     np.sin(2*np.pi*date.dayofyear/365.25),
                     np.cos(2*np.pi*date.dayofyear/365.25)], dtype=float)


def supervised(series):
    values = series.to_numpy(dtype=float)
    origins = range(LOOKBACK, len(values)-HORIZON+1)
    x = np.array([features(values[:i], series.index[i]) for i in origins])
    y = np.array([values[i:i+HORIZON].sum() for i in origins])
    dates = series.index[LOOKBACK:len(values)-HORIZON+1]
    return x, y, dates


def estimator(name):
    if name == "ridge":
        return make_pipeline(StandardScaler(), Ridge(alpha=10.0))
    if name == "random_forest":
        return RandomForestRegressor(n_estimators=60, min_samples_leaf=5, random_state=42, n_jobs=1)
    raise ValueError(f"Unknown estimator: {name}")


def score(actual, predicted):
    actual, predicted = np.asarray(actual), np.asarray(predicted)
    error = actual-predicted
    return {"mae": float(np.abs(error).mean()), "rmse": float(np.sqrt(np.mean(error**2)))}


def train_one(series):
    if len(series) < 360:
        raise ValueError("Need at least 360 calendar days for training/validation/test")
    x, y, dates = supervised(series)
    n = len(y)
    test_start, val_start = n-45, n-120
    # The latest training target ends strictly before the validation origin.
    train_stop = val_start-HORIZON+1
    val_stop = test_start-HORIZON+1
    candidates, validation, test = {}, {}, {}
    for name in ["baseline", "ridge", "random_forest"]:
        if name == "baseline":
            pred = x[val_start:val_stop, 3]*HORIZON
        else:
            model = estimator(name).fit(x[:train_stop], y[:train_stop])
            pred = model.predict(x[val_start:val_stop])
        validation[name] = score(y[val_start:val_stop], pred)
    winner = min(validation, key=lambda name: validation[name]["mae"])
    predictions = {}
    for name in validation:
        if name == "baseline":
            pred = x[test_start:, 3]*HORIZON
        else:
            model = estimator(name).fit(x[:test_start-HORIZON+1], y[:test_start-HORIZON+1])
            pred = model.predict(x[test_start:])
        test[name] = score(y[test_start:], pred)
        predictions[name] = pred.tolist()
    final = None if winner == "baseline" else estimator(winner).fit(x, y)
    report = {"winner": winner, "validation": validation, "test": test,
              "test_dates": dates[test_start:].strftime("%Y-%m-%d").tolist(),
              "actual": y[test_start:].tolist(), "predictions": predictions,
              "train_last_target": str((dates[train_stop-1]+pd.Timedelta(days=29)).date()),
              "validation_first_origin": str(dates[val_start].date()),
              "validation_last_target": str((dates[val_stop-1]+pd.Timedelta(days=29)).date()),
              "test_first_origin": str(dates[test_start].date())}
    return {"model": final, "report": report}


def train(daily, top_countries=10):
    countries = daily.drop(columns="all").sum().nlargest(top_countries).index.tolist()
    models = {country: train_one(daily[country]) for country in ["all"]+countries}
    return {"version": datetime.now(timezone.utc).isoformat(), "daily": daily,
            "models": models, "horizon_days": HORIZON}


def predict(bundle, country="all", date=None):
    if country not in bundle["models"]:
        raise ValueError(f"Unknown country; available: {list(bundle['models'])}")
    daily = bundle["daily"]
    latest = daily.index[-1]+pd.Timedelta(days=1)
    if date is None:
        origin = latest
    else:
        try:
            origin = pd.Timestamp(datetime.strptime(date, "%Y-%m-%d"))
        except (ValueError, TypeError):
            raise ValueError("date must be YYYY-MM-DD") from None
    if origin > latest:
        raise ValueError("Missing observations before requested forecast date; ingest more data")
    history = daily.loc[daily.index < origin, country]
    # Historical requests reselect and refit using only information before origin.
    fitted = bundle["models"][country] if origin == latest else train_one(history)
    x = features(history.to_numpy(), origin).reshape(1, -1)
    value = x[0, 3]*HORIZON if fitted["model"] is None else fitted["model"].predict(x)[0]
    return {"country": country, "forecast_start": str(origin.date()),
            "forecast_end": str((origin+pd.Timedelta(days=29)).date()),
            "horizon_days": HORIZON, "revenue": float(value),
            "model": fitted["report"]["winner"], "version": bundle["version"]}


def save(bundle, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as handle:
            pickle.dump(bundle, handle)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def load(path):
    # Only load artifacts created locally by this project; pickle is not an upload format.
    with open(path, "rb") as handle:
        return pickle.load(handle)
