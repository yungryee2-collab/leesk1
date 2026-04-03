"""
입찰 분석 결과를 마크다운 리포트로 저장합니다.
"""

import os
from datetime import datetime
from .config import SEARCH_DOMAINS, OUTPUT_DIR


def generate_report(results: dict[str, list[dict]], run_date: str | None = None) -> str:
    """
    분류 결과를 마크다운 리포트로 생성하고 저장합니다.

    Args:
        results: {도메인명: [입찰공고 목록]}
        run_date: 실행일자 (기본: 오늘)

    Returns:
        저장된 파일 경로
    """
    if run_date is None:
        run_date = datetime.now().strftime("%Y-%m-%d")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    total = sum(len(v) for v in results.values())

    lines = [
        f"# 정부조달 입찰공고 모니터링 리포트",
        f"",
        f"**실행일시**: {datetime.now().strftime('%Y년 %m월 %d일 %H:%M')}",
        f"**총 관련 공고**: {total}건",
        f"",
        "---",
        "",
    ]

    for domain, bids in results.items():
        cfg = SEARCH_DOMAINS[domain]
        lines += [
            f"## {cfg['description']} ({len(bids)}건)",
            "",
        ]

        if not bids:
            lines += ["> 해당 기간 중 관련 공고 없음", ""]
            continue

        for i, bid in enumerate(bids, 1):
            title = bid.get("title") or "(제목 없음)"
            org = bid.get("org") or ""
            budget = bid.get("budget") or ""
            deadline = bid.get("deadline") or ""
            notice_date = bid.get("notice_date") or ""
            reason = bid.get("_reason") or ""
            bid_id = bid.get("bid_id") or ""
            url = bid.get("url") or ""

            lines += [f"### {i}. {title}"]

            meta_parts = []
            if org:
                meta_parts.append(f"**발주기관**: {org}")
            if bid_id:
                meta_parts.append(f"**공고번호**: {bid_id}")
            if notice_date:
                meta_parts.append(f"**공고일**: {notice_date}")
            if deadline:
                meta_parts.append(f"**마감일**: {deadline}")
            if budget:
                meta_parts.append(f"**추정가격**: {budget}원")

            if meta_parts:
                lines += ["  \n".join(meta_parts), ""]

            if reason:
                lines += [f"**분류 근거**: {reason}", ""]

            if url:
                lines += [f"[상세보기]({url})", ""]

            lines.append("")

        lines.append("")

    lines += [
        "---",
        f"*자동 생성: 정부조달 입찰 모니터링 에이전트 | {datetime.now().strftime('%Y-%m-%d %H:%M')}*",
    ]

    content = "\n".join(lines)

    # 저장
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    filename = f"procurement_report_{timestamp}.md"
    filepath = os.path.join(OUTPUT_DIR, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    # 최신 리포트를 latest.md로도 저장
    latest_path = os.path.join(OUTPUT_DIR, "procurement_latest.md")
    with open(latest_path, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"[REPORT] 저장 완료: {filepath}")
    return filepath
