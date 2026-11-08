"""Read ARC winter training workbook tabs named like 'Comp Wk1 Wo1' / 'Fit Wk3 Wo2'
and write details.json for the ARC Winter Erg Plan page.
Also reads the 'Competitive' and 'Fitness & Community' season tabs into plan.json.
Usage: python3 -I parse_sessions.py <workbook.xlsx> <output folder>  (writes details.json and plan.json)"""
import json, re, sys
import openpyxl

NAME = re.compile(r"^\s*(Comp|Fit)\w*\s+Wk\s*(\d+)\s+Wo\s*(\d+)\s*$", re.I)
SECTIONS = {"WARM UP": "warmup", "WARMUP": "warmup", "WORKOUT": "workout", "COOL DOWN": "cooldown", "COOLDOWN": "cooldown"}
GENERIC_ERG = {"erg data link", "erg data:", "erg data", "ergdata"}


def txt(v):
    if v is None:
        return ""
    if isinstance(v, float):
        # "- 22" typed in Excel becomes -22.0
        n = int(v) if v.is_integer() else v
        return f"– {abs(n)}" if n < 0 else str(n)
    return str(v).replace(" ", " ").rstrip()


def parse(ws):
    rows = {}
    for row in ws.iter_rows():
        cells = [(c.column, txt(c.value), c.hyperlink.target if c.hyperlink else None)
                 for c in row if txt(c.value).strip()]
        if cells:
            rows[row[0].row] = cells
    d = {"tab": ws.title, "erg": [], "coach": [], "focus": "", "type": "", "dynamic": [],
         "dynamicLink": None, "video": None, "form": None, "warmup": [], "workout": [], "cooldown": []}

    coach_col = None
    for r, cells in rows.items():
        for i, (col, t, link) in enumerate(cells):
            low = t.strip().lower()
            after = [x for x in cells[i + 1:]]
            if low.startswith("coach"):
                coach_col = col
                d["coach"].append(" ".join(x[1].strip() for x in after).strip())
            elif low.startswith("technical focus") and after:
                d["focus"] = after[0][1].strip()
            elif low.startswith("workout type") and after:
                d["type"] = after[0][1].strip()
            elif low.startswith("video app"):
                d["video"] = link or next((x[2] or x[1] for x in after if x[1].startswith("http") or x[2]), None)
            elif low.startswith("dynamic warm"):
                d["dynamicLink"] = link

    # coach continuation rows (second line under the coach column)
    if coach_col:
        for r, cells in rows.items():
            if any(t.lower().startswith("coach") for _, t, _ in cells):
                continue
            right = [t.strip() for col, t, _ in cells if col > coach_col - 1 and not t.lower().startswith(("video", "http", "erg"))]
            if right and r < 12:
                d["coach"].append(" ".join(right))
    d["coach"] = [c for c in d["coach"] if c]

    # ErgData links: any ergdata hyperlink in the header rows
    for r, cells in sorted(rows.items()):
        if r > 12:
            break
        for col, t, link in cells:
            if link and "ergdata" in link:
                label = t.strip()
                if label.lower() in GENERIC_ERG:
                    label = "ErgData workout"
                if link not in [e["url"] for e in d["erg"]]:
                    d["erg"].append({"label": label, "url": link})

    # body sections
    cur, base_col, last_row = None, None, None
    dyn_on = False
    side = {"warmup": [], "workout": [], "cooldown": []}
    for r, cells in sorted(rows.items()):
        line_cells = [(c, t, l) for c, t, l in cells]
        # a side panel (e.g. a body-weight circuit in column L) is read as its own stream
        if cur is not None and base_col is not None:
            right = [x for x in line_cells if x[0] - base_col >= 8]
            if right:
                line_cells = [x for x in line_cells if x[0] - base_col < 8]
                rc = right[0][0]
                rtext = " ".join(t.strip() for _, t, _ in right).strip()
                rlink = next((l for _, _, l in right if l), None)
                ri = (len(right[0][1]) - len(right[0][1].lstrip())) // 4
                if rtext.startswith("- "):
                    rtext = rtext[2:].strip()
                side[cur if not (cur == "warmup" and last_row and r - last_row >= 5 and d["warmup"]) else "workout"].append(
                    {"t": rtext, "i": min(ri + (1 if right[0][1].lstrip().startswith("-") else 0), 3),
                     **({"url": rlink} if rlink else {})})
                if not line_cells:
                    continue
        head = line_cells[0][1].strip().upper()
        if head in SECTIONS:
            cur, base_col, last_row, dyn_on = SECTIONS[head], line_cells[0][0], r, False
            continue
        if head.startswith("DYNAMIC WARM"):
            dyn_on = True
            continue
        if dyn_on and cur is None:
            d["dynamic"].append(" ".join(t.strip() for _, t, _ in line_cells))
            continue
        if cur is None:
            continue
        # no WORKOUT header: a long gap after the warm-up starts the workout
        if cur == "warmup" and last_row and r - last_row >= 5 and d["warmup"]:
            cur = "workout"
        last_row = r
        text = " ".join(t.strip() for _, t, _ in line_cells).strip()
        link = next((l for _, _, l in line_cells if l), None)
        if link and "forms.gle" in link or (link and "docs.google.com/forms" in link):
            d["form"] = link
            continue
        if text.lower().startswith("please enter data"):
            continue
        first = line_cells[0]
        indent = max(0, first[0] - base_col) + (len(first[1]) - len(first[1].lstrip())) // 4
        if indent and text.startswith("- "):
            pass
        d[cur].append({"t": text.lstrip("- ").strip() if text.startswith("- ") else text,
                       "i": min(indent, 3), **({"url": link} if link else {})})
    for s in ("warmup", "workout", "cooldown"):
        d[s].extend(side[s])
        if d[s]:
            m = min(x["i"] for x in d[s])
            for x in d[s]:
                x["i"] -= m
    return d


SEASON_TABS = {"competitive": "Competitive", "fitness": "Fitness & Community"}
TEAM = re.compile(r"(?:\s*\[\s*|\s{2,})Team:\s*(.*?)\s*\]?\s*$", re.S)


def season(ws):
    hdr = None
    for row in ws.iter_rows(max_row=10):
        vals = [txt(c.value).strip().lower() for c in row]
        if "workout #" in vals and "workout" in vals:
            hdr = {v: i for i, v in enumerate(vals) if v}
            hrow = row[0].row
            break
    if not hdr:
        return []
    col = lambda name: hdr.get(name, next((i for k, i in hdr.items() if k.startswith(name)), None))
    cW, cP, cT, cD, cN, cK, cF, cX, cWo, cR, cAM, cPM = (col("week"), col("phase"), col("week type"), col("week dates"),
        col("workout #"), col("erg data"), col("data form"), col("technical"), col("workout"), col("rate"), col("coach am"), col("coach pm"))
    weeks, cur, phase = [], None, ""
    for row in ws.iter_rows(min_row=hrow + 1):
        g = lambda i: txt(row[i].value).strip() if i is not None and i < len(row) else ""
        link = lambda i: row[i].hyperlink.target if i is not None and i < len(row) and row[i].hyperlink else None
        if not any(g(i) for i in (cW, cD, cN, cWo)):
            # continuation line (e.g. a second ErgData link under a workout)
            if cur and cur["workouts"] and link(cK):
                cur["workouts"][-1]["erg"].append({"label": g(cK), "url": link(cK)})
            continue
        if g(cP):
            phase = g(cP)
        if g(cW) or g(cD):
            wk = g(cW)
            cur = {"wk": int(float(wk)) if re.match(r"^\d+(\.0)?$", wk) else 0, "phase": phase if g(cP) != "—" else "",
                   "type": g(cT), "dates": g(cD), "workouts": []}
            weeks.append(cur)
        if cur is None:
            continue
        wo = g(cWo)
        if not wo and not g(cN):
            continue
        team = ""
        m = TEAM.search(wo)
        if m:
            team, wo = m.group(1), wo[:m.start()].strip()
        num = re.match(r"#\s*(\d+)", g(cN))
        rate = g(cR)
        cur["workouts"].append({
            "n": int(num.group(1)) if num else 0, "label": g(cN), "kind": g(cK) if cur["wk"] else "",
            "focus": g(cX), "workout": wo, "team": team,
            "rate": "" if rate.lower() == "as noted" else rate,
            "coachAm": g(cAM), "coachPm": g(cPM),
            "erg": [{"label": g(cK), "url": link(cK)}] if link(cK) else [],
            "form": link(cF), "formLabel": g(cF)})
    return weeks


def main(src, outdir):
    wb = openpyxl.load_workbook(src)
    result = {}
    for ws in wb.worksheets:
        m = NAME.match(ws.title)
        if not m or ws.sheet_state != "visible":
            continue
        track = "competitive" if m.group(1).lower().startswith("comp") else "fitness"
        key = f"{'comp' if track == 'competitive' else 'fit'}-{int(m.group(2))}-{int(m.group(3))}"
        s = parse(ws)
        if not (s["warmup"] or s["workout"]):
            continue
        result[key] = s
    import os
    os.makedirs(outdir, exist_ok=True)
    with open(os.path.join(outdir, "details.json"), "w") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    plan = {k: season(wb[t]) for k, t in SEASON_TABS.items() if t in wb.sheetnames}
    with open(os.path.join(outdir, "plan.json"), "w") as f:
        json.dump(plan, f, ensure_ascii=False, indent=1)
    print(f"{len(result)} sessions:", ", ".join(sorted(result)))
    for k, v in plan.items():
        print(f"{k}: {len(v)} weeks, {sum(len(w['workouts']) for w in v)} workouts")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
