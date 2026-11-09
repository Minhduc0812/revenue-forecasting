"""Download public course data with SHA256 provenance; never executed on import."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
from urllib.request import Request, urlopen

REPO = "https://api.github.com/repos/aavail/ai-workflow-capstone"


def get(url):
    with urlopen(Request(url, headers={"User-Agent": "revenue-course-project"}), timeout=120) as response:
        return response.read()


def download(destination, split):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    commit = json.loads(get(REPO+"/commits/master"))["sha"]
    tree = json.loads(get(REPO+f"/git/trees/{commit}?recursive=1"))
    if tree.get("truncated"):
        raise ValueError("Repository listing was truncated")
    entries = [x for x in tree["tree"] if x["path"].startswith(split+"/") and x["path"].endswith(".json")]
    if not entries:
        raise ValueError("No course files found")
    def fetch(entry):
        url = f"https://raw.githubusercontent.com/aavail/ai-workflow-capstone/{commit}/{entry['path']}"
        content = get(url)
        if len(content) != entry["size"]:
            raise ValueError("Incomplete download")
        json.loads(content)
        (destination/Path(entry["path"]).name).write_bytes(content)
        return {"path": entry["path"], "sha256": hashlib.sha256(content).hexdigest(), "url": url}
    with ThreadPoolExecutor(max_workers=4) as pool:
        files = list(pool.map(fetch, entries))
    manifest = {"commit": commit, "split": split, "files": files}
    # Outside raw directory so ingestion does not mistake this for transaction data.
    (destination.parent/(destination.name+"-manifest.json")).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Downloaded {len(files)} files to {destination}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="data/raw")
    parser.add_argument("--split", choices=["cs-train", "cs-production"], default="cs-train")
    args = parser.parse_args()
    download(args.output, args.split)
