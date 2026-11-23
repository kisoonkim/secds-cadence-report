#!/usr/bin/env python3
"""SEC DS monthly report: validate reply attachments, analyze, and build the deck.

Usage:
  build_report.py validate --dir DATA_DIR --month 2026-10 [--quarterly]
  build_report.py build --dir DATA_DIR --month 2026-10 --template PREV.pptx \
      --history history.csv --base-date 2026.11.03 --out OUT.pptx [--history-out NEW_HISTORY.csv]

DATA_DIR holds the reply attachments saved under their ORIGINAL file names.
"""
import argparse, csv, glob, json, math, os, re, sys
from collections import OrderedDict

TENANTS = OrderedDict([("SECDSPMIX", "pmix"), ("MEMBP", "bp"), ("MEMLTP", "ltp")])
MONTH_ABBR = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
MONTH_LONG = ["January", "February", "March", "April", "May", "June", "July", "August",
              "September", "October", "November", "December"]
QUERIES = {
    "users": "top_1000_users_usage_duration_for_{m}_in_{y}",
    "hits": "top_10_views_by_total_hits_for_{m}_in_{y}",
    "dur": "top_10_views_by_usage_duration_for_{m}_in_{y}",
}
QUARTERLY_QUERIES = {  # extra files expected in quarterly replies
    "q_users": "quarterly_individual_users_usage_duration_and_total_hits",
    "q_hits": "views_by_total_hits_in_last_3_months",
    "q_dur": "views_by_usage_duration_in_last_3_months",
}


def norm(s):
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def hrs(v):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return 0.0
    if hasattr(v, "hour") and not isinstance(v, str):  # datetime.time
        return v.hour + v.minute / 60 + v.second / 3600
    if hasattr(v, "total_seconds"):
        return v.total_seconds() / 3600
    parts = [float(p) for p in str(v).strip().split(":")]
    while len(parts) < 3:
        parts.insert(0, 0.0)
    return parts[0] + parts[1] / 60 + parts[2] / 3600


def find_files(d, y, mon):
    """Map (tenant, key) -> path. Tolerates ' (1)' suffixes and case differences."""
    files = {os.path.basename(p): p for p in glob.glob(os.path.join(d, "*"))}
    found, problems = {}, []
    for tenant, prefix in TENANTS.items():
        users = [p for n, p in files.items() if re.match(rf"o9\.UsersForTenant_{tenant}_.*\.csv$", n, re.I)]
        if len(users) != 1:
            problems.append(f"{tenant}: 사용자정보 CSV {len(users)}개 (1개 필요)")
        else:
            found[(tenant, "roles")] = users[0]
        for key, pat in QUERIES.items():
            want = norm(f"{prefix}_" + pat.format(m=MONTH_ABBR[mon - 1], y=y))
            hits = [p for n, p in files.items()
                    if n.lower().endswith(".xlsx") and norm(re.sub(r"\s*\(\d+\)", "", n[:-5])) == want]
            if len(hits) != 1:
                problems.append(f"{tenant}: '{want}.xlsx' {len(hits)}개 (1개 필요)")
            else:
                found[(tenant, key)] = hits[0]
    return found, problems, files


def read_sheet(path):
    import openpyxl
    ws = openpyxl.load_workbook(path, data_only=True).worksheets[0]
    rows = [list(r) for r in ws.iter_rows(values_only=True)]
    title = rows[0][0] if rows else None
    header = rows[1] if len(rows) > 1 else []
    body = [r for r in rows[2:] if any(c not in (None, "") for c in r)]
    return title, header, body


def read_roles(path):
    roles = {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        r = csv.reader(f)
        hdr = next(r)
        ei, ri = hdr.index("Email"), hdr.index("UserRoles")
        for row in r:
            if len(row) > ei and row[ei]:
                roles[row[ei].strip().lower()] = [x.strip() for x in row[ri:] if x.strip()]
    return hdr, roles


def validate(d, y, mon, quarterly=False):
    found, problems, files = find_files(d, y, mon)
    checks = []
    mtxt = f"for {MONTH_ABBR[mon - 1]} in {y}".lower()
    for (tenant, key), path in found.items():
        name = os.path.basename(path)
        try:
            if key == "roles":
                hdr, roles = read_roles(path)
                ok = "Email" in hdr and "UserRoles" in hdr and len(roles) > 0
                checks.append(f"{name}: 사용자 {len(roles)}명")
                if not ok:
                    problems.append(f"{name}: Email/UserRoles 컬럼 또는 데이터 없음")
                continue
            title, header, body = read_sheet(path)
            if not body:
                problems.append(f"{name}: 데이터 행 없음")
            if title and mtxt not in str(title).lower():
                problems.append(f"{name}: 시트 제목 '{title}' 이 대상 월과 다름")
            need = {"users": ["User", "Usage Duration"], "hits": ["Workspace", "Page", "View", "TotalHits"],
                    "dur": ["Workspace", "Page", "View", "Usage Duration"]}[key]
            if [str(h).strip() if h else "" for h in header[:len(need)]] != need:
                problems.append(f"{name}: 헤더 {header} (예상 {need})")
            checks.append(f"{name}: {len(body)}행")
        except Exception as e:  # noqa
            problems.append(f"{name}: 읽기 실패 ({e})")
    # cross-check: every top-1000 user should exist in that tenant's user file
    for tenant in TENANTS:
        if (tenant, "roles") in found and (tenant, "users") in found:
            _, roles = read_roles(found[(tenant, "roles")])
            _, _, body = read_sheet(found[(tenant, "users")])
            miss = [r[0] for r in body if str(r[0]).strip().lower() not in roles]
            if len(miss) > max(3, 0.05 * len(body)):
                problems.append(f"{tenant}: top1000 사용자 중 {len(miss)}명이 사용자정보 CSV에 없음 (테넌트가 바뀌었을 수 있음)")
    if quarterly:
        for key, pat in QUARTERLY_QUERIES.items():
            for tenant, prefix in TENANTS.items():
                if not any(pat in norm(n) and norm(n).startswith(prefix) for n in files):
                    problems.append(f"{tenant}: 분기 파일 '{prefix}_{pat}*.xlsx' 없음")
    extra = [n for n in files if not any(os.path.basename(p) == n for p in found.values())
             and not n.lower().endswith((".png", ".jpg", ".gif"))]
    return {"ok": not problems, "problems": problems, "checks": checks, "unrecognized_files": extra}


def analyze(d, y, mon):
    found, problems, _ = find_files(d, y, mon)
    if problems:
        raise SystemExit("validation failed: " + "; ".join(problems))
    emails, total_h = set(), 0.0
    role_hours, top_hits, top_dur, tenant_users, known_roles = {}, [], [], {}, {}
    for tenant in TENANTS:
        _, roles = read_roles(found[(tenant, "roles")])
        _, _, users = read_sheet(found[(tenant, "users")])
        agg = {}
        tenant_users[tenant] = len(users)
        for r in users:
            e, h = str(r[0]).strip().lower(), hrs(r[1])
            emails.add(e)
            total_h += h
            for role in roles.get(e, []):
                agg[role] = agg.get(role, 0.0) + h
        role_hours[tenant] = agg
        known_roles[tenant] = {x.lower() for rs in roles.values() for x in rs}
        for key, dest in (("hits", top_hits), ("dur", top_dur)):
            _, _, body = read_sheet(found[(tenant, key)])
            for r in body:
                v = int(r[3]) if key == "hits" else hrs(r[3])
                dest.append([tenant, r[0], r[1], r[2], v])
    top_hits.sort(key=lambda x: -x[4])
    top_dur.sort(key=lambda x: -x[4])
    return {"users": len(emails), "hours": round(total_h), "tenant_users": tenant_users,
            "role_hours": role_hours, "known_roles": known_roles, "top_hits": top_hits[:10], "top_dur": top_dur[:10]}


# ---------------------------------------------------------------- deck editing
def set_text(shape_or_cell, text):
    """Replace text keeping the first run's formatting."""
    tf = shape_or_cell.text_frame
    p0 = tf.paragraphs[0]
    runs = p0.runs
    if runs:
        runs[0].text = text
        for r in runs[1:]:
            r._r.getparent().remove(r._r)
    else:
        p0.add_run().text = text
    for p in tf.paragraphs[1:]:
        p._p.getparent().remove(p._p)


def replace_in_shape(shape, pattern, repl):
    if not shape.has_text_frame:
        return
    for p in shape.text_frame.paragraphs:
        for r in p.runs:
            new = re.sub(pattern, repl, r.text)
            if new != r.text:
                r.text = new
        full = "".join(r.text for r in p.runs)  # pattern split across runs
        if p.runs and re.search(pattern, full) and re.sub(pattern, repl, full) != full:
            p.runs[0].text = re.sub(pattern, repl, full)
            for r in p.runs[1:]:
                r.text = ""


def find_slide(prs, title_contains):
    out = []
    for s in prs.slides:
        for sh in s.shapes:
            if sh.has_text_frame and title_contains in sh.text_frame.text:
                out.append(s)
                break
    return out


def remove_shape(sh):
    sh._element.getparent().remove(sh._element)


def add_bar_chart(slide, pic, title, cats, vals):
    from pptx.chart.data import CategoryChartData
    from pptx.enum.chart import XL_CHART_TYPE
    from pptx.dml.color import RGBColor
    from pptx.util import Pt
    cd = CategoryChartData()
    cd.categories = cats
    cd.add_series(title, vals)
    gf = slide.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, pic.left, pic.top, pic.width, pic.height, cd)
    ch = gf.chart
    ch.has_legend = False
    ch.has_title = True
    ch.chart_title.text_frame.text = title
    tr = ch.chart_title.text_frame.paragraphs[0].runs[0]
    tr.font.size, tr.font.bold, tr.font.color.rgb = Pt(18), True, RGBColor(0x75, 0x75, 0x75)
    plot = ch.plots[0]
    plot.gap_width = 60
    plot.has_data_labels = True
    plot.data_labels.font.size = Pt(12)
    plot.data_labels.number_format = "#,##0"
    plot.data_labels.number_format_is_linked = False
    ser = plot.series[0]
    ser.format.fill.solid()
    ser.format.fill.fore_color.rgb = RGBColor(0x42, 0x85, 0xF4)
    ch.value_axis.minimum_scale = 0
    ch.value_axis.has_major_gridlines = True
    ch.value_axis.major_gridlines.format.line.color.rgb = RGBColor(0xCC, 0xCC, 0xCC)
    ch.value_axis.tick_labels.font.size = Pt(10)
    ch.category_axis.tick_labels.font.size = Pt(10)
    remove_shape(pic)


def add_update_badge(slide, text="⚠ 업데이트 필요"):
    from pptx.util import Inches, Pt
    from pptx.dml.color import RGBColor
    from pptx.enum.shapes import MSO_SHAPE
    from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
    b = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(8.05), Inches(0.82), Inches(1.8), Inches(0.3))
    b.name = "UPDATE_NEEDED_BADGE"
    b.fill.solid()
    b.fill.fore_color.rgb = RGBColor(0xE5, 0x39, 0x35)
    b.line.fill.background()
    tf = b.text_frame
    tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = text
    r.font.size, r.font.bold = Pt(11), True
    r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)


def build(args):
    from pptx import Presentation
    y, mon = map(int, args.month.split("-"))
    a = analyze(args.dir, y, mon)
    ym = f"{y}.{mon:02d}"

    # history (month,users,hours)
    hist = OrderedDict()
    if args.history and os.path.exists(args.history):
        with open(args.history, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                hist[r["month"]] = (int(r["users"]), int(r["hours"]))
    hist[ym] = (a["users"], a["hours"])
    hist = OrderedDict(sorted(hist.items()))
    last3 = list(hist.items())[-3:]
    if args.history_out:
        with open(args.history_out, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["month", "users", "hours"])
            for k, (u, h) in hist.items():
                w.writerow([k, u, h])

    prs = Presentation(args.template)
    period3 = f"{last3[0][0]} - {last3[-1][0]}"
    warnings = []

    stale_keys = ("Scheduled Batch Performance -", "서포트 티켓 현황 -", "서포트 티켓 분석", "서포트 티켓 생성",
                  "환경별 테넌트 현황")
    stale = {id(sl) for k in stale_keys for sl in find_slide(prs, k)}

    for s in prs.slides:
        if id(s) in stale:
            continue  # copied as-is from last month; flagged below
        for sh in s.shapes:
            replace_in_shape(sh, r"기준일: \d{4}\.\d{2}\.\d{2}", f"기준일: {args.base_date}")
            replace_in_shape(sh, r"분석 기준일: \d{4}\.\d{2}\.\d{2}", f"분석 기준일: {args.base_date}")
            replace_in_shape(sh, r"분석기간: \d{4}\.\d{2} - \d{4}\.\d{2}", f"분석기간: {period3}")
            replace_in_shape(sh, r"분석기간: \d{4}\.\d{2}(?! -)", f"분석기간: {ym}")
            replace_in_shape(sh, r"\((\d{1,2})월\)", f"({mon}월)")

    # cover
    cover = prs.slides[0]
    for sh in cover.shapes:
        if sh.has_text_frame and "Monthly Status Report" in sh.text_frame.text:
            paras = sh.text_frame.paragraphs
            for p in paras:
                if re.search(r"\d{4}", p.text) and p.runs:
                    p.runs[0].text = f"{MONTH_LONG[mon - 1]}. {y}"
                    for r in p.runs[1:]:
                        r.text = ""
        elif sh.has_text_frame and re.fullmatch(r"\s*\d{4}\.\d{2}\.\d{2}\s*", sh.text_frame.text):
            set_text(sh, args.base_date)

    cats = [k.replace(".", ". ") for k, _ in last3]
    for title, idx, ctitle in (("사용자 기준", 0, "월별 Platform 사용자 수"), ("사용량 기준", 1, "월별 Platform 사용량")):
        sl = find_slide(prs, f"Platform 사용 현황 - {title}")
        pics = [sh for sh in sl[0].shapes if sh.shape_type == 13] if sl else []
        if not pics:
            warnings.append(f"'{title}' 슬라이드의 차트 이미지를 찾지 못함")
            continue
        add_bar_chart(sl[0], max(pics, key=lambda p: p.width * p.height), ctitle, cats, [v[idx] for _, v in last3])

    # top-10 tables
    for slide in find_slide(prs, "주요 사용 UI"):
        tbl = next((sh.table for sh in slide.shapes if sh.has_table), None)
        if tbl is None:
            continue
        hdr = tbl.cell(0, 4).text
        data = a["top_hits"] if "횟수" in hdr else a["top_dur"]
        for i in range(1, len(tbl.rows)):
            row = data[i - 1] if i - 1 < len(data) else ["", "", "", "", ""]
            vals = list(row[:4]) + [f"{row[4]:,}" if "횟수" in hdr and row[4] != "" else
                                    (f"{int(row[4])}" if row[4] != "" else "")]
            for j, v in enumerate(vals):
                set_text(tbl.cell(i, j), str(v))

    # role tables: keep the role list in the template, recompute hours (floored like the original)
    for slide in find_slide(prs, "Role 별 사용시간"):
        txt = " ".join(sh.text_frame.text for sh in slide.shapes if sh.has_text_frame)
        m = re.search(r"Tenant: (\w+)", txt)
        tbl = next((sh.table for sh in slide.shapes if sh.has_table), None)
        if not m or tbl is None or m.group(1) not in a["role_hours"]:
            warnings.append(f"Role 슬라이드 테넌트 인식 실패: {m.group(1) if m else '?'}")
            continue
        rh = a["role_hours"][m.group(1)]
        lower = {k.lower(): v for k, v in rh.items()}
        for i in range(1, len(tbl.rows)):
            for name_col, val_col in ((0, 1), (2, 3)):
                role = tbl.cell(i, name_col).text.strip()
                if not role:
                    continue
                if role.lower() not in lower and role.lower() not in a["known_roles"][m.group(1)]:
                    warnings.append(f"{m.group(1)}: Role '{role}' 이 사용자정보에 없음 (이름 변경?) → 0")
                set_text(tbl.cell(i, val_col), f"{math.floor(lower.get(role.lower(), 0.0)):.2f}")

    # Sections 2-4: keep last month's content unchanged, flag each slide for manual update
    for slide in prs.slides:
        if id(slide) in stale:
            add_update_badge(slide)
    warnings.append(f"Section 2~4 슬라이드 {len(stale)}장은 전월 내용 그대로 복사됨 → '업데이트 필요' 표시")

    prs.save(args.out)
    summary = {k: a[k] for k in ("users", "hours", "tenant_users")}
    summary.update({"history_last3": last3, "warnings": warnings,
                    "top_hits": a["top_hits"][:3], "top_dur": [r[:4] + [round(r[4], 1)] for r in a["top_dur"][:3]]})
    print(json.dumps(summary, ensure_ascii=False, indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["validate", "build"])
    ap.add_argument("--dir", required=True)
    ap.add_argument("--month", required=True, help="YYYY-MM of the reported month")
    ap.add_argument("--quarterly", action="store_true")
    ap.add_argument("--template")
    ap.add_argument("--history")
    ap.add_argument("--history-out")
    ap.add_argument("--base-date")
    ap.add_argument("--out")
    args = ap.parse_args()
    y, mon = map(int, args.month.split("-"))
    if args.cmd == "validate":
        print(json.dumps(validate(args.dir, y, mon, args.quarterly), ensure_ascii=False, indent=1))
    else:
        build(args)


if __name__ == "__main__":
    sys.exit(main())
