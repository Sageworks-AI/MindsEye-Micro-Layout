"""Ingest issue events, regroup, write views/*.xml from the ledger."""
import argparse
import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path
import group
import ledger
import mindscript

def _fmt(v):
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)

def _slug(filename):
    stem = Path(filename).stem.lower()
    return re.sub(r"[^a-z0-9]+", "-", stem).strip("-")

def _says(d, hit):
    parts = []
    if hit is not None:
        d2 = d
        if hit["type"] == "matched" and hit.get("shape"):
            parts.append(mindscript.say(
                "section_shape",
                shape_label=mindscript.label(hit["shape"]),
                font_pt=_fmt(d2.get("font_pt", "")),
                line=_fmt(d2.get("line", "")),
                margin_pct=round(float(d2.get("margin_ratio") or 0) * 100)))
        else:
            parts.append(mindscript.say(
                "section_candidate",
                drift=round(float(hit.get("drift") or 0), 3),
                shape_label=mindscript.label(hit["shape"]) if hit.get("shape") else "unknown"))
    pw = d.get("para_words", [])
    avg = sum(pw) / len(pw) if pw else 0
    parts.append(mindscript.say(
        "texture",
        density=mindscript.density_word(avg),
        rhythm=mindscript.rhythm_word(pw)))
    return " ".join(x for x in parts if x)

def _section(m, hit):
    d = m.get("detail") or {}
    n = m["source"].rsplit("#s", 1)[1] if "#s" in m["source"] else ""
    title = d.get("title") or f"Section {n}"
    status = "candidate" if hit and hit["type"] == "new_shape_candidate" else "matched"
    shape = (hit or {}).get("shape", "")
    drift = round(float((hit or {}).get("drift", 0)), 3)
    el = ET.Element("section", {
        "id": m["source"], "title": title, "status": status,
        "shape": shape, "drift": str(drift),
        "page": str(d.get("page", "")), "font": str(d.get("font_family", "")),
        "font_pt": _fmt(d.get("font_pt", "")), "line": _fmt(d.get("line", "")),
        "after_pt": _fmt(d.get("after_pt", "")),
        "margin_ratio": str(d.get("margin_ratio", "")),
        "direction": str(d.get("text_direction", "ltr")),
    })
    ET.SubElement(el, "says").text = _says(d, hit)
    pw = d.get("para_words", [])
    avg = sum(pw) / len(pw) if pw else 0
    ET.SubElement(el, "texture", {
        "density": mindscript.density_word(avg),
        "rhythm": mindscript.rhythm_word(pw)})
    ET.SubElement(el, "rhythm").text = " ".join(str(w) for w in pw)
    h = ET.SubElement(el, "headings")
    for lvl, cnt in (d.get("headings") or {}).get("by_level", {}).items():
        ET.SubElement(h, "h", {"level": str(lvl), "count": str(cnt)})
    nms = ET.SubElement(el, "names")
    for name in d.get("names", []):
        ET.SubElement(nms, "name").text = name
    ET.SubElement(el, "text").text = d.get("excerpt", "")
    return el

def _write_views(data_dir, events):
    vdir = Path(data_dir) / "views"
    vdir.mkdir(parents=True, exist_ok=True)
    by_of = {(e.get("detail") or {}).get("of"): e
             for e in events if e["type"] in ("matched", "new_shape_candidate")
             and (e.get("detail") or {}).get("of")}
    docs = {}
    for m in events:
        if m["type"] != "measured":
            continue
        src = m["source"]
        name = Path(src.rsplit("#", 1)[0]).name
        slug = _slug(name)
        docs.setdefault(slug, {"src": src.rsplit("#", 1)[0], "sections": []})
        docs[slug]["sections"].append((m, by_of.get(m["id"])))
    for slug, info in docs.items():
        root = ET.Element("micro-view", {"version": "0.1", "src": info["src"]})
        for m, hit in info["sections"]:
            root.append(_section(m, hit))
        ET.ElementTree(root).write(vdir / f"{slug}.xml", encoding="utf-8", xml_declaration=True)
    idx = ET.Element("micro-index", {"version": "0.1"})
    for slug, info in docs.items():
        ET.SubElement(idx, "doc", {"slug": slug, "file": f"{slug}.xml", "src": info["src"]})
    ET.ElementTree(idx).write(vdir / "index.xml", encoding="utf-8", xml_declaration=True)

def run(data_dir, label=None, issue_body=None):
    lp = Path(data_dir) / "ledger" / "events.jsonl"
    if label:
        ledger.ingest(lp, label, issue_body or "", os.environ.get("ISSUE_NUMBER", "0"))
    group.run(data_dir)
    _write_views(data_dir, ledger.read(lp))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=".")
    a = ap.parse_args()
    run(a.data, os.environ.get("LABEL") or None, os.environ.get("ISSUE_BODY") or None)

if __name__ == "__main__":
    main()
