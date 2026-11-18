"""Measure .docx layout; append measured + matched events."""
import argparse, collections, hashlib, io, json, re, zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
import ledger
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
S, D = {}, {}
def _props(e):
    if e is None: return {}
    o = {}; sp = e.find(".//"+W+"spacing")
    if sp is not None:
        o.update({k: sp.get(W+k) for k in ("line", "after", "before") if sp.get(W+k) is not None})
        if sp.get(W+"lineRule"): o["lineRule"] = sp.get(W+"lineRule")
    if e.find(".//"+W+"bidi") is not None: o["bidi"] = True
    sz, rf = e.find(".//"+W+"sz"), e.find(".//"+W+"rFonts")
    if sz is not None and sz.get(W+"val"): o["sz"] = sz.get(W+"val")
    if rf is not None and rf.get(W+"ascii"): o["font"] = rf.get(W+"ascii")
    return o
def _chain(sid, seen=None):
    seen = seen or set()
    if not sid or sid in seen or sid not in S: return {}
    seen.add(sid); st = S[sid]
    b = _chain(st["b"], seen); b.update(_props(st["el"]))
    return b
def _load_styles(root):
    global S, D
    S, D = {}, {}
    if root is None: return
    dd = root.find(W+"docDefaults")
    if dd is not None:
        pd, rd = dd.find(W+"pPrDefault"), dd.find(W+"rPrDefault")
        D.update(_props(pd.find(W+"pPr") if pd is not None else None))
        D.update(_props(rd.find(W+"rPr") if rd is not None else None))
    for st in root.findall(W+"style"):
        sid, b, n = st.get(W+"styleId"), st.find(W+"basedOn"), st.find(W+"name")
        if sid: S[sid] = {"el": st, "b": b.get(W+"val") if b is not None else None,
                          "name": (n.get(W+"val") if n is not None else "") or ""}
def _heading(p, sid):
    if sid:
        m = re.match(r"^Heading([1-9])$", sid) or re.search(r"heading\s+([1-9])", S.get(sid, {}).get("name", ""), re.I)
        if m: return int(m.group(1))
    ppr = p.find(W+"pPr"); ol = ppr.find(W+"outlineLvl") if ppr is not None else None
    if ol is not None and ol.get(W+"val", "").isdigit() and 0 <= int(ol.get(W+"val")) <= 8:
        return int(ol.get(W+"val")) + 1
    return None
def _para(p):
    ppr = p.find(W+"pPr"); ps = ppr.find(W+"pStyle") if ppr is not None else None
    sid = ps.get(W+"val") if ps is not None else None
    pr = dict(D); pr.update(_chain(sid)); pr.update(_props(ppr))
    rpr = next((r.find(W+"rPr") for r in p.iter(W+"r") if r.find(W+"rPr") is not None), None)
    pr.update(_props(rpr))
    fp = float(pr.get("sz", "20")) / 2.0; lr = pr.get("line")
    if lr is None: line = 1.0
    elif pr.get("lineRule", "auto") in ("exact", "atLeast"): line = (float(lr) / 20.0) / fp
    else: line = float(lr) / 240.0
    return {"font_pt": fp, "font": pr.get("font", ""), "line": round(line, 2),
            "after_pt": round(float(pr.get("after", "0")) / 20.0, 1),
            "before_pt": round(float(pr.get("before", "0")) / 20.0, 1),
            "bidi": bool(pr.get("bidi", False)), "text": "".join(t.text or "" for t in p.iter(W+"t")),
            "heading": _heading(p, sid),
            "page_break": any(b.get(W+"type") == "page" for b in p.iter(W+"br"))}
def _walk(body):
    out, cur = [], []
    for el in body:
        for p in ([el] if el.tag == W+"p" else (el.iter(W+"p") if el.tag == W+"tbl" else [])):
            cur.append(p); ppr = p.find(W+"pPr")
            if ppr is not None and ppr.find(W+"sectPr") is not None:
                out.append((cur, ppr.find(W+"sectPr"))); cur = []
    fin = body.find(W+"sectPr")
    if cur or fin is not None: out.append((cur, fin))
    return out
def _names(ms):
    out, seen = [], set()
    for m in ms:
        if m["heading"] is not None: continue
        prev = "."
        for tok in re.findall(r"[A-Za-z][A-Za-z']*|[.!?]", m["text"]):
            if tok in ".!?": prev = tok; continue
            if prev not in ".!?" and re.fullmatch(r"[A-Z][a-z]{2,}", tok) and tok.lower() not in seen:
                seen.add(tok.lower()); out.append(tok)
                if len(out) >= 12: return out
            prev = " "
    return out
def _section(paras, sect):
    ms = [_para(p) for p in paras]
    body = [m for m in ms if m["heading"] is None and m["text"].strip()]
    sample = body or ms
    best = collections.Counter((m["font_pt"], m["line"], m["after_pt"]) for m in sample).most_common(1)
    best = best[0][0] if best else (10.0, 1.0, 0.0)
    mt = [m for m in sample if (m["font_pt"], m["line"], m["after_pt"]) == best]
    font = collections.Counter(m["font"] for m in mt if m["font"]).most_common(1)
    before = collections.Counter(m["before_pt"] for m in mt).most_common(1)
    bidi = bool(body) and sum(1 for m in body if m["bidi"]) * 2 > len(body)
    w, h, orient, left, right = 11906, 16838, "portrait", 1440, 1440
    if sect is not None:
        pg, pm = sect.find(W+"pgSz"), sect.find(W+"pgMar")
        if pg is not None:
            w, h = int(pg.get(W+"w", 11906)), int(pg.get(W+"h", 16838))
            orient = pg.get(W+"orient") or ("landscape" if w > h else "portrait")
        if pm is not None:
            left, right = int(pm.get(W+"left", 1440)), int(pm.get(W+"right", 1440))
    te = sect.find(W+"textDirection") if sect is not None else None
    td = "rtl" if bidi else ("ltr" if te is None or not te.get(W+"val") or "rl" not in te.get(W+"val") else "rtl")
    by = collections.Counter(str(m["heading"]) for m in ms if m["heading"])
    per = [0]
    for m in ms:
        if m["page_break"]: per.append(0)
        per[-1] += bool(m["heading"])
    s = sorted((w, h))
    page = next((n for n, (a, b) in (("A4",(11906,16838)),("A5",(8391,11906)),("Letter",(12240,15840))) if abs(s[0]-a)<=30 and abs(s[1]-b)<=30), "other")
    return {"title": next((m["text"].strip() for m in ms if m["heading"] == 1 and m["text"].strip()), None),
            "page": page, "orientation": orient, "text_direction": td,
            "font_family": font[0][0] if font else "", "font_pt": best[0], "line": best[1],
            "after_pt": best[2], "before_pt": before[0][0] if before else 0.0,
            "margin_ratio": round(((left+right)/2)/w, 3),
            "headings": {"by_level": dict(by), "per_page": per}, "names": _names(ms),
            "para_words": [len(m["text"].split()) for m in ms][:60],
            "excerpt": "\n".join(m["text"] for m in ms)[:1500]}
def run(docs_dir, data_dir):
    lp = Path(data_dir) / "ledger" / "events.jsonl"
    spec = json.loads((Path("baselines") / "shapes.json").read_text(encoding="utf-8"))
    seen = {(e.get("detail") or {}).get("sha256") for e in ledger.read(lp) if e["type"] == "measured"}
    pending = []
    for docx in sorted(Path(docs_dir).glob("*.docx")):
        raw = docx.read_bytes(); sha = hashlib.sha256(raw).hexdigest()
        if sha in seen: continue
        z = zipfile.ZipFile(io.BytesIO(raw))
        try: _load_styles(ET.fromstring(z.read("word/styles.xml")))
        except KeyError: _load_styles(None)
        for i, (paras, sect) in enumerate(_walk(ET.fromstring(z.read("word/document.xml")).find(W+"body")), 1):
            d = _section(paras, sect); d["sha256"] = sha
            pending.append((d, ledger.append(lp, "measured", f"docs/{docx.name}#s{i}", count=len(paras), detail=d)))
    ws, sc = spec["weights"], spec["scales"]
    for d, ev in pending:
        cands = [s for s in spec["shapes"] if s["page"] == d["page"]]
        hit = min(((round(sum(ws[k]*abs(d[k]-s[k])/sc[k] for k in ws), 3), s) for s in cands), default=None)
        if hit is None: continue
        dist, shp = hit
        kind = "matched" if dist <= spec["threshold"] else "new_shape_candidate"
        md = {"page": d["page"], "font_pt": d["font_pt"], "line": d["line"], "after_pt": d["after_pt"],
              "margin_ratio": d["margin_ratio"], "title": d["title"], "of": ev["id"]}
        if kind != "matched": md["proposed"] = {k: d[k] for k in ("page","font_pt","line","after_pt","margin_ratio")}
        ledger.append(lp, kind, ev["source"], shape=shp["id"], drift=dist, detail=md)
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs", default="docs"); ap.add_argument("--data", default=".")
    a = ap.parse_args(); run(a.docs, a.data)
if __name__ == "__main__": main()
