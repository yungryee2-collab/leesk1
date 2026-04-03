"""
입찰 모니터링 결과를 HTML 이메일로 발송합니다.
SMTP (Gmail 앱 비밀번호 또는 다른 SMTP 서버) 사용.
"""

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime
from .config import SEARCH_DOMAINS

# ─── 이메일 설정 (.env에서 로드) ────────────────────────────────
SMTP_HOST = os.getenv("EMAIL_SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("EMAIL_SMTP_PORT", "587"))
EMAIL_SENDER = os.getenv("EMAIL_SENDER", "")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "")
EMAIL_RECIPIENT = os.getenv("EMAIL_RECIPIENT", "seunkgyo.lee@barunlaw.com")


def _build_html(results: dict[str, list[dict]], period_days: int) -> str:
    """분류 결과를 HTML 이메일 본문으로 변환합니다."""
    total = sum(len(v) for v in results.values())
    run_dt = datetime.now().strftime("%Y년 %m월 %d일 %H:%M")

    # ── 도메인별 요약 뱃지 ──
    summary_badges = ""
    for domain, bids in results.items():
        cfg = SEARCH_DOMAINS[domain]
        color = {"법률_법령": "#1a56db", "에너지_인프라": "#057a55", "해외_ODA": "#7e3af2"}.get(domain, "#374151")
        summary_badges += f"""
        <span style="display:inline-block;background:{color};color:#fff;
                     padding:4px 14px;border-radius:20px;font-size:13px;
                     margin:4px 6px 4px 0;">{cfg['description']} {len(bids)}건</span>"""

    # ── 본문 섹션 ──
    sections_html = ""
    for domain, bids in results.items():
        cfg = SEARCH_DOMAINS[domain]
        header_color = {"법률_법령": "#1a56db", "에너지_인프라": "#057a55", "해외_ODA": "#7e3af2"}.get(domain, "#374151")

        if not bids:
            sections_html += f"""
            <div style="margin:28px 0 12px;">
              <h2 style="color:{header_color};border-left:4px solid {header_color};
                         padding-left:12px;font-size:16px;margin:0 0 8px;">
                {cfg['description']} (0건)
              </h2>
              <p style="color:#6b7280;font-size:13px;margin:0;">해당 기간 관련 공고 없음</p>
            </div>"""
            continue

        rows = ""
        for i, bid in enumerate(bids, 1):
            title    = bid.get("title") or "(제목 없음)"
            org      = bid.get("org") or ""
            bid_id   = bid.get("bid_id") or ""
            budget   = bid.get("budget") or ""
            deadline = bid.get("deadline") or ""
            notice_dt= bid.get("notice_date") or ""
            reason   = bid.get("_reason") or ""
            source   = bid.get("source") or ""
            url      = bid.get("url") or ""

            title_cell = f'<a href="{url}" style="color:#1a56db;text-decoration:none;">{title}</a>' if url else title
            source_badge = (
                f'<span style="font-size:10px;background:#f3f4f6;color:#374151;'
                f'padding:1px 6px;border-radius:10px;margin-left:6px;">{source}</span>'
                if source else ""
            )
            row_bg = "#f9fafb" if i % 2 == 0 else "#ffffff"

            rows += f"""
            <tr style="background:{row_bg};">
              <td style="padding:10px 12px;border-bottom:1px solid #e5e7eb;
                         font-size:13px;font-weight:600;color:#111827;">
                {title_cell}{source_badge}
              </td>
              <td style="padding:10px 12px;border-bottom:1px solid #e5e7eb;
                         font-size:12px;color:#374151;">{org}</td>
              <td style="padding:10px 12px;border-bottom:1px solid #e5e7eb;
                         font-size:12px;color:#374151;white-space:nowrap;">{notice_dt[:10] if notice_dt else ""}</td>
              <td style="padding:10px 12px;border-bottom:1px solid #e5e7eb;
                         font-size:12px;color:#dc2626;font-weight:600;white-space:nowrap;">{deadline[:10] if deadline else ""}</td>
              <td style="padding:10px 12px;border-bottom:1px solid #e5e7eb;
                         font-size:12px;color:#6b7280;">{reason}</td>
            </tr>"""

        sections_html += f"""
        <div style="margin:28px 0 12px;">
          <h2 style="color:{header_color};border-left:4px solid {header_color};
                     padding-left:12px;font-size:16px;margin:0 0 12px;">
            {cfg['description']} ({len(bids)}건)
          </h2>
          <table style="width:100%;border-collapse:collapse;font-family:sans-serif;">
            <thead>
              <tr style="background:{header_color};color:#fff;">
                <th style="padding:8px 12px;text-align:left;font-size:12px;font-weight:600;">공고명</th>
                <th style="padding:8px 12px;text-align:left;font-size:12px;font-weight:600;">발주기관</th>
                <th style="padding:8px 12px;text-align:left;font-size:12px;font-weight:600;">공고일</th>
                <th style="padding:8px 12px;text-align:left;font-size:12px;font-weight:600;">마감일</th>
                <th style="padding:8px 12px;text-align:left;font-size:12px;font-weight:600;">분류근거</th>
              </tr>
            </thead>
            <tbody>{rows}</tbody>
          </table>
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="ko">
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f3f4f6;font-family:'Apple SD Gothic Neo',
             'Malgun Gothic',sans-serif;">
  <div style="max-width:860px;margin:24px auto;background:#fff;
              border-radius:10px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.08);">

    <!-- 헤더 -->
    <div style="background:#111827;padding:24px 28px;">
      <div style="color:#f9fafb;font-size:11px;letter-spacing:1px;
                  text-transform:uppercase;margin-bottom:6px;">
        정부조달 입찰 모니터링
      </div>
      <h1 style="color:#fff;margin:0;font-size:20px;font-weight:700;">
        입찰공고 리포트
      </h1>
      <div style="color:#9ca3af;font-size:12px;margin-top:6px;">
        {run_dt} 기준 · 최근 {period_days}일 조회
      </div>
    </div>

    <!-- 요약 -->
    <div style="padding:20px 28px;border-bottom:1px solid #e5e7eb;background:#f9fafb;">
      <div style="font-size:13px;color:#6b7280;margin-bottom:8px;">총 관련 공고</div>
      <div style="font-size:28px;font-weight:700;color:#111827;margin-bottom:10px;">
        {total}건
      </div>
      {summary_badges}
    </div>

    <!-- 본문 -->
    <div style="padding:20px 28px;">
      {sections_html}
    </div>

    <!-- 푸터 -->
    <div style="padding:16px 28px;background:#f9fafb;border-top:1px solid #e5e7eb;
                font-size:11px;color:#9ca3af;text-align:center;">
      정부조달 입찰 모니터링 에이전트 · 자동 발송 · {run_dt}
    </div>
  </div>
</body>
</html>"""


def send_email(
    results: dict[str, list[dict]],
    report_path: str | None,
    period_days: int,
) -> bool:
    """
    분류 결과를 HTML 이메일로 발송합니다.
    report_path가 있으면 .md 파일을 첨부합니다.

    Returns:
        발송 성공 여부
    """
    if not EMAIL_SENDER or not EMAIL_PASSWORD:
        print("[EMAIL] EMAIL_SENDER / EMAIL_PASSWORD 미설정 — 이메일 발송 건너뜀")
        return False

    total = sum(len(v) for v in results.values())
    subject = (
        f"[입찰모니터링] {datetime.now().strftime('%Y.%m.%d')} "
        f"관련 공고 {total}건 ({period_days}일 기준)"
    )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = EMAIL_SENDER
    msg["To"] = EMAIL_RECIPIENT

    # HTML 본문
    html_body = _build_html(results, period_days)
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    # 첨부 파일 (.md 리포트)
    if report_path and os.path.exists(report_path):
        with open(report_path, "rb") as f:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header(
            "Content-Disposition",
            f'attachment; filename="{os.path.basename(report_path)}"',
        )
        msg.attach(part)

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_SENDER, EMAIL_RECIPIENT, msg.as_string())
        print(f"[EMAIL] 발송 완료 → {EMAIL_RECIPIENT}")
        return True
    except smtplib.SMTPException as e:
        print(f"[EMAIL] 발송 실패: {e}")
        return False
