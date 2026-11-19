"""Append-only event ledger (JSONL)."""
import hashlib, json, os, re
from datetime import datetime, timezone
from pathlib import Path

def now():
    f = os.environ.get("MICRO_FIXED_TIME")
    if f: return f
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def read(path):
    p = Path(path)
    if not p.exists(): return []
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]

def append(path, type, source, shape="", drift=0, count=1, detail=None):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    text = p.read_text(encoding="utf-8") if p.exists() else ""
    n = len([l for l in text.splitlines() if l.strip()])
    ts = now()
    eid = hashlib.sha1(f"{n}|{type}|{source}|{ts}".encode("utf-8")).hexdigest()[:10]
    event = {"id": eid, "type": type, "source": source, "shape": shape,
             "drift": drift, "count": count, "timestamp": ts}
    if detail is not None: event["detail"] = detail
    line = json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n"
    with p.open("a", encoding="utf-8") as f:
        if text and not text.endswith("\n"): f.write("\n")
        f.write(line)
    return event

ALLOWED = {"id","type","source","shape","drift","count","timestamp","detail"}
TYPES = {"window_opened","window_compared"}

def ingest(path, label, body, issue_no):
    if not body: return 0
    added = 0
    if label == "seed":
        for line in body.splitlines():
            line = line.strip()
            if not line.lower().startswith("seed:"): continue
            word = line.split(":", 1)[1].strip()
            if not re.fullmatch(r"[A-Za-z]{3,30}", word): continue
            append(path, "matched", f"issue#{issue_no}", detail={"word": word.lower(), "seed": True})
            added += 1
    elif label == "log":
        for line in body.splitlines()[:200]:
            line = line.strip()
            if not line.startswith("{"): continue
            try: obj = json.loads(line)
            except ValueError: continue
            if not isinstance(obj, dict) or obj.get("type") not in TYPES: continue
            if not set(obj.keys()) <= ALLOWED: continue
            src = obj.get("source")
            if not isinstance(src, str) or not src: continue
            append(path, obj["type"], src,
                   shape=str(obj.get("shape") or ""),
                   drift=float(obj.get("drift") or 0),
                   count=int(obj.get("count") or 1),
                   detail=obj.get("detail") if isinstance(obj.get("detail"), dict) else None)
            added += 1
    return added
