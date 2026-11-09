import json
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock


class EventLog:
    def __init__(self, path):
        self.path = Path(path)
        self.lock = Lock()

    def append(self, event, **fields):
        record = {"timestamp": datetime.now(timezone.utc).isoformat(), "event": event, **fields}
        line = json.dumps(record, allow_nan=False)
        with self.lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(line+"\n")

    def read(self):
        with self.lock:
            if not self.path.exists():
                return []
            return [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines()]
