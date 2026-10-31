#!/usr/bin/env python3
"""
미국 원자력 수출통제 공식 데이터 수집기 (수출통제 사전검증 앱용)

수집 대상 (모두 미국 정부 공개 데이터):
  1. eCFR  - 10 CFR Part 110 (NRC), 10 CFR Part 810 (DOE),
             15 CFR Part 734/738/740/744/746 (EAR) 원문 및 개정 이력
  2. CSL   - trade.gov Consolidated Screening List
             (BIS Entity/DPL/UVL/MEU, OFAC SDN·Non-SDN, State Debarred 등 통합)
  3. FR    - Federal Register API: 위 Part들의 최근 개정 고시

출력 (이 스크립트와 같은 폴더):
  manifest.json   수집 시각, 출처 URL, 기준일, 건수
  screening.json  통합 제재명단 (조회용으로 압축)
  regs.json       규정 원문 섹션, 810 부록 A 국가 목록, Commerce Country Chart
  fr_updates.json 최근 개정 고시 목록

실행: python3 fetch_data.py
필요 네트워크: www.ecfr.gov, data.trade.gov, www.federalregister.gov
의존성 없음 (표준 라이브러리만 사용).
"""
import json, re, sys, time, datetime, urllib.request, urllib.error
import xml.etree.ElementTree as ET
from pathlib import Path

OUT = Path(__file__).resolve().parent
UA = {"User-Agent": "export-control-checker/1.0 (legal research tool)", "Accept": "*/*"}

ECFR = "https://www.ecfr.gov/api/versioner/v1"
CSL_URL = "https://data.trade.gov/downloadable_consolidated_screening_list/v1/consolidated.json"
FR_API = "https://www.federalregister.gov/api/v1/documents.json"

PARTS = [
    # (title, part, label, keep_full_text)
    (10, 110, "NRC 10 CFR Part 110 — 원자력 장비·물질 수출입", True),
    (10, 810, "DOE 10 CFR Part 810 — 외국 원자력 활동 지원", True),
    (15, 734, "EAR Part 734 — EAR 적용 범위 (de minimis, FDP)", True),
    (15, 738, "EAR Part 738 — Commerce Control List 개요·국가표", True),
    (15, 740, "EAR Part 740 — 허가예외·국가그룹", False),
    (15, 744, "EAR Part 744 — 최종용도·최종사용자 통제", False),
    (15, 746, "EAR Part 746 — 금수 및 특별통제", False),
]
# 전문을 싣지 않는 Part에서 원문을 보관할 섹션
KEEP_SECTIONS = {
    740: ["740.2", "Supplement No. 1 to Part 740"],
    744: ["744.2", "744.6", "744.11", "744.21", "744.22"],
    746: ["746.1", "746.8"],
}


def get(url, tries=4, timeout=120):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except (urllib.error.URLError, TimeoutError) as e:
            if i == tries - 1:
                raise
            wait = 2 ** (i + 1)
            print(f"  재시도 {i+1}/{tries-1} ({e}); {wait}s 대기", file=sys.stderr)
            time.sleep(wait)


def text_of(el):
    return re.sub(r"\s+", " ", "".join(el.itertext())).strip()


# ---------------------------------------------------------------- eCFR
def ecfr_title_dates():
    data = json.loads(get(f"{ECFR}/titles.json"))
    return {t["number"]: t for t in data.get("titles", [])}


def ecfr_part_xml(title, part, date):
    return get(f"{ECFR}/full/{date}/title-{title}.xml?part={part}")


def ecfr_versions(title, part):
    try:
        data = json.loads(get(f"{ECFR}/versions/title-{title}.json?part={part}"))
        dates = sorted({v.get("amendment_date") for v in data.get("content_versions", []) if v.get("amendment_date")})
        return dates[-5:]
    except Exception as e:
        print(f"  개정 이력 실패 {title}/{part}: {e}", file=sys.stderr)
        return []


def sections_from_xml(xml_bytes):
    """eCFR XML의 DIV8(섹션)·DIV9(부록/보충) 단위로 제목과 본문 추출."""
    root = ET.fromstring(xml_bytes)
    out = []
    for div in root.iter():
        if div.tag in ("DIV8", "DIV9"):
            head = div.find("HEAD")
            out.append({
                "n": div.get("N", ""),
                "type": div.get("TYPE", ""),
                "head": text_of(head) if head is not None else "",
                "text": "\n".join(text_of(p) for p in div if p.tag != "HEAD" and text_of(p)),
                "_el": div,
            })
    return out


def parse_table(div_el):
    """GPOTABLE → {headers, rows}. 국가표처럼 첫 열이 국가명인 표에 사용."""
    tables = []
    for tbl in div_el.iter("GPOTABLE"):
        headers = [text_of(c) for c in tbl.iter("CHED")]
        rows = []
        for row in tbl.iter("ROW"):
            cells = [text_of(e) for e in row.findall("ENT")]
            if cells and any(cells):
                rows.append(cells)
        tables.append({"headers": headers, "rows": rows})
    return tables


def parse_810_appendix_a(sections):
    """Part 810 부록 A(일반허가 대상국) 국가명 목록."""
    for s in sections:
        if "appendix a" in s["head"].lower() and "810" in s["head"]:
            names = []
            for p in s["_el"].iter("P"):
                t = re.sub(r"^\(?\d+\)?\.?\s*", "", text_of(p)).strip(" .;")
                if 2 < len(t) < 60 and not re.search(r"\b(appendix|part|the following|generally authorized)\b", t, re.I):
                    names.append(t)
            # 표 형식으로 수록된 경우
            if not names:
                for tb in parse_table(s["_el"]):
                    for r in tb["rows"]:
                        names += [c for c in r if 2 < len(c) < 60]
            return {"head": s["head"], "countries": sorted(set(names)), "raw": s["text"][:20000]}
    return None


def parse_country_chart(sections):
    for s in sections:
        if "supplement no. 1 to part 738" in s["head"].lower():
            tables = parse_table(s["_el"])
            if tables:
                big = max(tables, key=lambda t: len(t["rows"]))
                return {"head": s["head"], **big}
    return None


def parse_country_groups(sections):
    for s in sections:
        if "supplement no. 1 to part 740" in s["head"].lower():
            return {"head": s["head"], "tables": parse_table(s["_el"])}
    return None


def collect_regs():
    titles = ecfr_title_dates()
    regs = {"parts": [], "app810A": None, "countryChart": None, "countryGroups": None}
    meta = {}
    for title, part, label, full in PARTS:
        date = titles[title]["up_to_date_as_of"]
        print(f"eCFR {title} CFR Part {part} ({date})")
        secs = sections_from_xml(ecfr_part_xml(title, part, date))
        if part == 810:
            regs["app810A"] = parse_810_appendix_a(secs)
        if part == 738:
            regs["countryChart"] = parse_country_chart(secs)
        if part == 740:
            regs["countryGroups"] = parse_country_groups(secs)
        keep = secs if full else [s for s in secs if any(k.lower() in (s["n"] + " " + s["head"]).lower() for k in KEEP_SECTIONS.get(part, []))]
        regs["parts"].append({
            "title": title, "part": part, "label": label, "asOf": date,
            "recentAmendments": ecfr_versions(title, part),
            "url": f"https://www.ecfr.gov/current/title-{title}/part-{part}",
            "sections": [{k: v for k, v in s.items() if k != "_el"} for s in keep],
        })
        meta[f"{title}CFR{part}"] = date
    return regs, meta


# ---------------------------------------------------------------- CSL
def collect_csl():
    print("Consolidated Screening List")
    raw = json.loads(get(CSL_URL, timeout=300))
    items = raw.get("results", raw) if isinstance(raw, dict) else raw
    out, by_source = [], {}
    for it in items:
        src = it.get("source", "")
        by_source[src] = by_source.get(src, 0) + 1
        addrs = it.get("addresses") or []
        out.append({
            "n": it.get("name", ""),
            "a": [a for a in (it.get("alt_names") or []) if a][:25],
            "s": src,
            "t": it.get("type", ""),
            "c": sorted({(a.get("country") or "") for a in addrs if a.get("country")}),
            "p": it.get("programs") or [],
            "lr": it.get("license_requirement", ""),
            "lp": it.get("license_policy", ""),
            "fr": it.get("federal_register_notice", ""),
            "d": it.get("start_date", ""),
            "u": it.get("source_list_url", ""),
        })
    return out, by_source


# ---------------------------------------------------------------- Federal Register
FR_CFR = [(10, 110), (10, 810), (15, 734), (15, 738), (15, 740), (15, 744), (15, 746), (15, 774)]


def collect_fr():
    print("Federal Register")
    seen, docs = set(), []
    for title, part in FR_CFR:
        q = (f"{FR_API}?per_page=10&order=newest"
             f"&conditions[cfr][title]={title}&conditions[cfr][part]={part}"
             "&fields[]=title&fields[]=publication_date&fields[]=html_url&fields[]=type"
             "&fields[]=document_number&fields[]=agencies&fields[]=effective_on")
        try:
            for d in json.loads(get(q)).get("results", []):
                if d["document_number"] in seen:
                    continue
                seen.add(d["document_number"])
                docs.append({
                    "title": d.get("title"), "date": d.get("publication_date"),
                    "effective": d.get("effective_on"), "type": d.get("type"),
                    "url": d.get("html_url"), "no": d.get("document_number"),
                    "cfr": f"{title} CFR {part}",
                    "agency": ", ".join(a.get("name", "") for a in (d.get("agencies") or [])),
                })
        except Exception as e:
            print(f"  FR 실패 {title}/{part}: {e}", file=sys.stderr)
    docs.sort(key=lambda d: d["date"] or "", reverse=True)
    return docs[:40]


def main():
    now = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    manifest = {"fetchedAt": now, "sources": {}}

    regs, reg_dates = collect_regs()
    (OUT / "regs.json").write_text(json.dumps(regs, ensure_ascii=False), encoding="utf-8")
    manifest["sources"]["ecfr"] = {"label": "eCFR (10 CFR 110·810, 15 CFR 734·738·740·744·746)",
                                   "url": "https://www.ecfr.gov", "asOf": reg_dates,
                                   "app810A": len((regs["app810A"] or {}).get("countries", [])),
                                   "countryChartRows": len((regs["countryChart"] or {}).get("rows", []))}

    csl, by_source = collect_csl()
    (OUT / "screening.json").write_text(json.dumps(csl, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    manifest["sources"]["csl"] = {"label": "Consolidated Screening List (BIS·OFAC·State 통합)",
                                  "url": CSL_URL, "asOf": now[:10], "count": len(csl), "bySource": by_source}

    fr = collect_fr()
    (OUT / "fr_updates.json").write_text(json.dumps(fr, ensure_ascii=False), encoding="utf-8")
    manifest["sources"]["fr"] = {"label": "Federal Register 최근 개정 고시", "url": "https://www.federalregister.gov",
                                 "asOf": now[:10], "count": len(fr)}

    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    for f in ("regs.json", "screening.json", "fr_updates.json", "manifest.json"):
        print(f"  {f}: {(OUT / f).stat().st_size/1e6:.2f} MB")
    big = [f for f in ("regs.json", "screening.json") if (OUT / f).stat().st_size > 15.5e6]
    if big:
        print(f"경고: 아티팩트 파일 한도(16MB)에 근접/초과: {big}", file=sys.stderr)


if __name__ == "__main__":
    main()
