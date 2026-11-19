"""Replay the ledger to group options and fire restructure events."""
import json
import xml.etree.ElementTree as ET
from pathlib import Path
import ledger

ROOT = Path(__file__).resolve().parent.parent
TRIGGER_APPEARANCES = 3

def _keys(ev):
    d = ev.get("detail") or {}
    if ev["type"] == "measured":
        for n in d.get("names", []):
            yield "word:" + n.lower()
    elif ev["type"] == "matched":
        if d.get("word"):
            yield "word:" + d["word"]
        if ev.get("shape"):
            yield "shape:" + ev["shape"]
    elif ev["type"] == "window_compared":
        yield ev["source"]

def _appearances(events):
    counts = {}
    for ev in events:
        if ev["type"] == "restructured":
            counts[ev["source"]] = 0
        else:
            for k in _keys(ev):
                counts[k] = counts.get(k, 0) + 1
    return counts

def _regroup(events, opts):
    usage = {o["id"]: 0 for o in opts}
    for e in events:
        if e["type"] == "window_opened":
            opt = (e.get("detail") or {}).get("option")
            if opt in usage:
                usage[opt] += 1
    order = {o["id"]: i for i, o in enumerate(opts)}
    ranked = sorted(opts, key=lambda o: (-usage[o["id"]], order[o["id"]]))
    primary = ranked[:3]
    pid = {o["id"] for o in primary}
    pcats = {o["category"] for o in primary}
    nearby = [o for o in opts if o["id"] not in pid and o["category"] in pcats]
    nid = {o["id"] for o in nearby}
    rest = [o for o in opts if o["id"] not in pid and o["id"] not in nid]
    return {"primary": primary, "nearby": nearby, "rest": rest}

def run(data_dir):
    lp = Path(data_dir) / "ledger" / "events.jsonl"
    events = ledger.read(lp)
    opts = json.loads((ROOT / "config" / "windows.json").read_text(encoding="utf-8"))["options"]
    counts = _appearances(events)
    fired = [k for k, c in counts.items() if c >= TRIGGER_APPEARANCES]
    groups = _regroup(events, opts)
    ids = {g: [o["id"] for o in groups[g]] for g in groups}
    for key in fired:
        ledger.append(lp, "restructured", key,
                      shape=key[6:] if key.startswith("shape:") else "",
                      count=counts[key],
                      detail={"groups": ids, "trigger": key})
    if fired:
        events = ledger.read(lp)
    grouped = any(e["type"] == "restructured" for e in events)
    p = Path(data_dir) / "views" / "options.xml"
    p.parent.mkdir(parents=True, exist_ok=True)
    root = ET.Element("options", {"state": "grouped" if grouped else "flat"})
    if not grouped:
        g = ET.SubElement(root, "group", {"name": "all"})
        for o in opts:
            ET.SubElement(g, "option", {"id": o["id"], "label": o["label"], "category": o["category"]})
    else:
        for name in ("primary", "nearby", "rest"):
            g = ET.SubElement(root, "group", {"name": name})
            for o in groups[name]:
                ET.SubElement(g, "option", {"id": o["id"], "label": o["label"], "category": o["category"]})
    ET.ElementTree(root).write(p, encoding="utf-8", xml_declaration=True)
