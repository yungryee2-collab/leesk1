"""
정부조달 입찰 모니터링 — 즉시 실행 스크립트
Python만 설치되어 있으면 됩니다.

사용법:
  python run_now.py
"""

import subprocess, sys, os

# 필요한 패키지 자동 설치
REQUIRED = ["anthropic", "requests", "python-dotenv", "schedule"]
for pkg in REQUIRED:
    try:
        __import__(pkg.replace("-", "_"))
    except ImportError:
        print(f"[설치] {pkg} 설치 중...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", pkg, "-q"])

# .env 로드 (스크립트와 같은 폴더에 있어야 함)
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

import json, smtplib, requests, anthropic
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import xml.etree.ElementTree as ET

CONFIG = {
    "PROCUREMENT_API_KEY": os.environ["PROCUREMENT_API_KEY"],
    "ANTHROPIC_API_KEY":   os.environ["ANTHROPIC_API_KEY"],
    "EMAIL_SENDER":        os.environ["EMAIL_SENDER"],
    "EMAIL_PASSWORD":      os.environ["EMAIL_PASSWORD"],
    "EMAIL_RECIPIENT":     os.getenv("EMAIL_RECIPIENT", "seunkgyo.lee@barunlaw.com"),
    "DAYS_BACK":           int(os.getenv("INTERVAL_DAYS", "3")),
}

DOMAINS = {
    "법률_법령": {
        "label": "법률제정·법령제정",
        "color": "#1a56db",
        "keywords": ["법률","법령","제정","개정","입법","법제","법무","규정","조례","법률자문","입법지원","법령정비"],
        "prompt": "이 입찰이 법률·법령의 제정, 개정, 입법지원, 법무자문, 법령정비 관련 업무인지 판단하세요.",
    },
    "에너지_인프라": {
        "label": "에너지 인프라 타당성 조사",
        "color": "#057a55",
        "keywords": ["에너지","인프라","타당성","발전","송전","배전","전력","재생에너지","태양광","풍력","LNG","에너지저장","탄소중립"],
        "prompt": "이 입찰이 에너지·인프라(발전·송배전·전력망 등)의 타당성조사, 기획, 컨설팅 관련 업무인지 판단하세요.",
    },
    "해외_ODA": {
        "label": "해외사업·국제사업·ODA",
        "color": "#7e3af2",
        "keywords": ["ODA","해외","국제","KOICA","EDCF","원조","무상원조","유상원조","공적개발원조","해외사업","국제협력","개도국"],
        "prompt": "이 입찰이 해외사업, ODA, 국제협력, KOICA/EDCF 사업, 해외컨설팅 관련 업무인지 판단하세요.",
    },
}

API_ENDPOINTS = [
    {
        "url": "https://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoServc",
        "source": "나라장터(공공)",
        "date_start": "inqryBgnDt",
        "date_end": "inqryEndDt",
        "date_fmt": "12",   # YYYYMMDDHHmm
        "extra": {"inqryDiv": "1"},
    },
    {
        "url": "https://apis.data.go.kr/1230000/ao/PrvtBidNtceService/getPrvtBidNtceSrchList",
        "source": "누리장터(민간)",
        "date_start": "prvtBidNtceBgnDt",
        "date_end": "prvtBidNtceEndDt",
        "date_fmt": "14",   # YYYYMMDDHHmmss
        "extra": {},
    },
]

# ─── 1. 입찰 수집 ─────────────────────────────────────────────
def fetch_bids():
    days  = CONFIG["DAYS_BACK"]
    # 나라장터: YYYYMMDDHHmm (12자리), 누리장터: YYYYMMDDHHmmss (14자리)
    start_12 = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d%H%M")
    end_12   = datetime.now().strftime("%Y%m%d%H%M")
    start_14 = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d%H%M%S")
    end_14   = datetime.now().strftime("%Y%m%d%H%M%S")
    all_bids, seen = [], set()

    for ep in API_ENDPOINTS:
        url    = ep["url"]
        source = ep["source"]
        ds = start_12 if ep["date_fmt"] == "12" else start_14
        de = end_12   if ep["date_fmt"] == "12" else end_14
        params = {
            "serviceKey": CONFIG["PROCUREMENT_API_KEY"],
            "numOfRows": "100", "pageNo": "1", "type": "json",
            ep["date_start"]: ds,
            ep["date_end"]:   de,
        }
        params.update(ep["extra"])

        print(f"[수집] {url.split('/')[-1]} ...")
        for page in range(1, 21):
            params["pageNo"] = str(page)
            try:
                r = requests.get(url, params=params, timeout=30)
                r.raise_for_status()
            except Exception as e:
                print(f"  오류: {e}"); break

            items = []
            if r.text.strip().startswith("<"):
                root = ET.fromstring(r.text)
                for item in root.findall(".//item"):
                    items.append({c.tag: c.text or "" for c in item})
            else:
                try:
                    d = r.json()
                    # 응답 코드 확인
                    code = (d.get("response", {}) or {}).get("header", {}).get("resultCode", "")
                    if code and code != "00":
                        msg = (d.get("response", {}) or {}).get("header", {}).get("resultMsg", "")
                        print(f"  API 오류 코드 {code}: {msg}"); break
                    for k in ("response", "body"):
                        if k in d: d = d[k]
                    if "items" in d:
                        it = d["items"]
                        if isinstance(it, dict) and "item" in it: it = it["item"]
                        if isinstance(it, dict): it = [it]
                        items = it if isinstance(it, list) else []
                except: break

            if not items: break
            for raw in items:
                raw["_source"] = source
                raw["_url_base"] = url
                bid = _norm(raw)
                uid = bid.get("bid_id") or str(raw)
                if uid not in seen:
                    seen.add(uid); all_bids.append(bid)
            if len(items) < 100: break

        print(f"  → 누적 {len(all_bids)}건")
    return all_bids


def _norm(raw):
    fm = {
        "bid_id":      ["bidNtceNo","prvtBidNtceNo","ntceNo"],
        "title":       ["bidNtceNm","bidNm","ntceNm"],
        "org":         ["ntceInsttNm","dmstcInsttNm","orgnztNm"],
        "budget":      ["presmptPrce","bsisAmt"],
        "deadline":    ["bidClseDt","prvtBidClseDt"],
        "notice_date": ["bidNtceDt","prvtBidNtceDt","ntceDt"],
        "url":         ["detailUrl","linkUrl"],
        "source":      ["_source"],
    }
    out = {}
    for k, cands in fm.items():
        for c in cands:
            if raw.get(c): out[k] = raw[c]; break
    out.setdefault("title",""); out.setdefault("bid_id","")
    out["_raw"] = raw
    return out


# ─── 2. Claude 분류 ────────────────────────────────────────────
def analyze(bids):
    client  = anthropic.Anthropic(api_key=CONFIG["ANTHROPIC_API_KEY"])
    results = {}
    for domain, cfg in DOMAINS.items():
        cands = []
        for b in bids:
            txt = (b.get("title","") + " " + b.get("org","")).lower()
            if any(k.lower() in txt for k in cfg["keywords"]):
                cands.append(b)

        print(f"[분류] {cfg['label']}: 키워드 {len(cands)}건 → Claude 판단 중...")
        relevant = []
        for i in range(0, len(cands), 20):
            batch    = cands[i:i+20]
            bid_json = json.dumps(
                [{"index":j,"title":b.get("title",""),"org":b.get("org","")}
                 for j,b in enumerate(batch)],
                ensure_ascii=False, indent=2)
            try:
                res = client.messages.create(
                    model="claude-opus-4-6",
                    max_tokens=2000,
                    thinking={"type": "adaptive"},
                    messages=[{"role":"user","content":
                        f"다음 입찰공고들이 아래 기준에 해당하는지 판단하세요.\n"
                        f"기준: {cfg['prompt']}\n\n{bid_json}\n\n"
                        "JSON 배열로만 응답: [{\"index\":숫자,\"relevant\":true/false,\"reason\":\"한줄\"}]"}])
                text = next((b.text for b in res.content if b.type == "text"), "")
                if "```" in text:
                    text = text.split("```")[1]
                    text = text[4:] if text.startswith("json") else text
                for r in json.loads(text.strip()):
                    if r.get("relevant"):
                        b = batch[r["index"]].copy()
                        b["_reason"] = r.get("reason",""); relevant.append(b)
            except Exception as e:
                print(f"  Claude 오류: {e}")
                relevant.extend(cands[i:i+20])

        results[domain] = relevant
        print(f"  → 최종 {len(relevant)}건 선별")
    return results


# ─── 3. HTML 이메일 생성 ───────────────────────────────────────
def build_html(results):
    total = sum(len(v) for v in results.values())
    now   = datetime.now().strftime("%Y년 %m월 %d일 %H:%M")
    days  = CONFIG["DAYS_BACK"]

    badges = "".join(
        f'<span style="background:{DOMAINS[d]["color"]};color:#fff;padding:4px 14px;'
        f'border-radius:20px;font-size:13px;margin:4px 6px 4px 0;display:inline-block;">'
        f'{DOMAINS[d]["label"]} {len(bids)}건</span>'
        for d, bids in results.items()
    )

    sections = ""
    for d, bids in results.items():
        c, label = DOMAINS[d]["color"], DOMAINS[d]["label"]
        if not bids:
            sections += (f'<div style="margin:24px 0 8px;">'
                         f'<h2 style="color:{c};border-left:4px solid {c};padding-left:12px;font-size:16px;margin:0 0 8px;">'
                         f'{label} (0건)</h2><p style="color:#6b7280;font-size:13px;">해당 기간 관련 공고 없음</p></div>')
            continue

        rows = ""
        for i, b in enumerate(bids, 1):
            title  = b.get("title","(제목없음)")
            org    = b.get("org","")
            nd     = (b.get("notice_date","") or "")[:10]
            dl     = (b.get("deadline","") or "")[:10]
            reason = b.get("_reason","")
            source = b.get("source","")
            url    = b.get("url","")
            t_cell = f'<a href="{url}" style="color:#1a56db;text-decoration:none;">{title}</a>' if url else title
            sbadge = (f'<span style="font-size:10px;background:#f3f4f6;color:#374151;'
                      f'padding:1px 6px;border-radius:10px;margin-left:6px;">{source}</span>') if source else ""
            bg = "#f9fafb" if i%2==0 else "#fff"
            rows += (f'<tr style="background:{bg};">'
                     f'<td style="padding:10px 12px;border-bottom:1px solid #e5e7eb;font-size:13px;font-weight:600;">{t_cell}{sbadge}</td>'
                     f'<td style="padding:10px 12px;border-bottom:1px solid #e5e7eb;font-size:12px;color:#374151;">{org}</td>'
                     f'<td style="padding:10px 12px;border-bottom:1px solid #e5e7eb;font-size:12px;white-space:nowrap;">{nd}</td>'
                     f'<td style="padding:10px 12px;border-bottom:1px solid #e5e7eb;font-size:12px;color:#dc2626;font-weight:600;white-space:nowrap;">{dl}</td>'
                     f'<td style="padding:10px 12px;border-bottom:1px solid #e5e7eb;font-size:12px;color:#6b7280;">{reason}</td></tr>')

        sections += (f'<div style="margin:24px 0 12px;">'
                     f'<h2 style="color:{c};border-left:4px solid {c};padding-left:12px;font-size:16px;margin:0 0 12px;">{label} ({len(bids)}건)</h2>'
                     f'<table style="width:100%;border-collapse:collapse;">'
                     f'<thead><tr style="background:{c};color:#fff;">'
                     f'<th style="padding:8px 12px;text-align:left;font-size:12px;">공고명</th>'
                     f'<th style="padding:8px 12px;text-align:left;font-size:12px;">발주기관</th>'
                     f'<th style="padding:8px 12px;text-align:left;font-size:12px;">공고일</th>'
                     f'<th style="padding:8px 12px;text-align:left;font-size:12px;">마감일</th>'
                     f'<th style="padding:8px 12px;text-align:left;font-size:12px;">분류근거</th>'
                     f'</tr></thead><tbody>{rows}</tbody></table></div>')

    return f"""<!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f3f4f6;font-family:'Apple SD Gothic Neo','Malgun Gothic',sans-serif;">
<div style="max-width:880px;margin:24px auto;background:#fff;border-radius:10px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.08);">
  <div style="background:#111827;padding:24px 28px;">
    <div style="color:#9ca3af;font-size:11px;letter-spacing:1px;margin-bottom:6px;">정부조달 입찰 모니터링</div>
    <h1 style="color:#fff;margin:0;font-size:20px;font-weight:700;">입찰공고 리포트</h1>
    <div style="color:#9ca3af;font-size:12px;margin-top:6px;">{now} 기준 · 최근 {days}일 조회</div>
  </div>
  <div style="padding:20px 28px;border-bottom:1px solid #e5e7eb;background:#f9fafb;">
    <div style="font-size:13px;color:#6b7280;margin-bottom:8px;">총 관련 공고</div>
    <div style="font-size:28px;font-weight:700;color:#111827;margin-bottom:10px;">{total}건</div>
    {badges}
  </div>
  <div style="padding:20px 28px;">{sections}</div>
  <div style="padding:16px 28px;background:#f9fafb;border-top:1px solid #e5e7eb;font-size:11px;color:#9ca3af;text-align:center;">
    정부조달 입찰 모니터링 에이전트 · 자동 발송 · {now}
  </div>
</div></body></html>"""


# ─── 4. 이메일 발송 ────────────────────────────────────────────
def send(results):
    total   = sum(len(v) for v in results.values())
    subject = (f"[입찰모니터링] {datetime.now().strftime('%Y.%m.%d')} "
               f"관련 공고 {total}건 ({CONFIG['DAYS_BACK']}일 기준)")
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = CONFIG["EMAIL_SENDER"]
    msg["To"]      = CONFIG["EMAIL_RECIPIENT"]
    msg.attach(MIMEText(build_html(results), "html", "utf-8"))

    print(f"\n[이메일] {CONFIG['EMAIL_RECIPIENT']} 으로 발송 중...")
    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as s:
            s.starttls()
            s.login(CONFIG["EMAIL_SENDER"], CONFIG["EMAIL_PASSWORD"])
            s.sendmail(CONFIG["EMAIL_SENDER"], CONFIG["EMAIL_RECIPIENT"], msg.as_string())
        print(f"[완료] 발송 성공!  제목: {subject}")
    except Exception as e:
        print(f"[오류] 발송 실패: {e}")


# ─── 실행 ─────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 55)
    print("  정부조달 입찰 모니터링 에이전트")
    print(f"  실행 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 55)
    bids    = fetch_bids()
    results = analyze(bids) if bids else {d: [] for d in DOMAINS}
    send(results)
