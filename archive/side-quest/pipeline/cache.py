"""Disk cache for model calls: same request -> same stored response (free, reproducible reruns).

Delete the cache folder to re-ask the models live.
"""
import hashlib
import json
from pathlib import Path


def cached(cache_dir: Path, kind: str, request: dict, call):
    key = hashlib.sha256(json.dumps(request, sort_keys=True, default=str).encode()).hexdigest()[:24]
    path = cache_dir / kind / f"{key}.json"
    if path.exists():
        out = json.loads(path.read_text())
        out["cached"] = True
        return out
    out = call()
    if out.get("error"):          # never cache failures
        out["cached"] = False
        return out
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, default=str))
    out["cached"] = False
    return out
