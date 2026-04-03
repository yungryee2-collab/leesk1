"""
정부조달 입찰 모니터링 에이전트 — 메인 실행 파일

실행 방법:
  python -m procurement_agent.main          # 즉시 1회 실행
  python -m procurement_agent.main --schedule  # 3일 주기 자동 실행
  python -m procurement_agent.main --days 7   # 최근 7일치 조회
"""

import json
import argparse
import schedule
import time
import os
from datetime import datetime, timedelta
from .fetcher import fetch_bids
from .analyzer import analyze_bids
from .report import generate_report
from .emailer import send_email
from .config import INTERVAL_DAYS, STATE_FILE, ANTHROPIC_API_KEY, PROCUREMENT_API_KEY


def _check_config() -> bool:
    """필수 설정값 확인"""
    ok = True
    if not ANTHROPIC_API_KEY or ANTHROPIC_API_KEY == "":
        print("[ERROR] ANTHROPIC_API_KEY가 설정되지 않았습니다. .env 파일을 확인하세요.")
        ok = False
    if not PROCUREMENT_API_KEY or PROCUREMENT_API_KEY == "YOUR_API_KEY_HERE":
        print("[WARN] PROCUREMENT_API_KEY가 설정되지 않았습니다. .env 파일에 조달청 API 키를 입력하세요.")
        ok = False
    return ok


def _load_state() -> dict:
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {"last_run": None}


def _save_state(state: dict) -> None:
    os.makedirs(os.path.dirname(STATE_FILE) or ".", exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def run_once(days_back: int | None = None) -> str | None:
    """
    입찰공고 수집 → 분류 → 리포트 생성을 1회 실행합니다.

    Args:
        days_back: 조회 기간(일). None이면 state 기반으로 자동 계산.

    Returns:
        생성된 리포트 파일 경로
    """
    state = _load_state()

    if days_back is None:
        if state["last_run"]:
            last_dt = datetime.fromisoformat(state["last_run"])
            days_back = max(1, (datetime.now() - last_dt).days + 1)
        else:
            days_back = INTERVAL_DAYS

    print(f"\n{'='*60}")
    print(f"[START] 정부조달 입찰 모니터링 실행")
    print(f"        조회 기간: 최근 {days_back}일")
    print(f"        실행 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")

    # 1. API 호출
    bids = fetch_bids(days_back=days_back)
    if not bids:
        print("[WARN] 수집된 입찰공고 없음 — 결과 없음 알림 발송")
        results = {}
        report_path = None
    else:
        # 2. 분류
        results = analyze_bids(bids)

        # 3. 리포트 파일 저장
        report_path = generate_report(results)

    # 4. 이메일 발송
    send_email(results, report_path, period_days=days_back)

    # 5. 상태 저장
    _save_state({"last_run": datetime.now().isoformat()})

    print(f"\n{'='*60}")
    print(f"[DONE] 완료. 리포트: {report_path or '(없음)'}")
    print(f"{'='*60}\n")

    return report_path


def run_scheduled() -> None:
    """3일 주기로 자동 실행하는 스케줄러를 시작합니다."""
    print(f"[SCHEDULER] {INTERVAL_DAYS}일 주기 스케줄 시작")
    print(f"            Ctrl+C로 중단하세요.\n")

    # 시작 시 즉시 1회 실행
    run_once()

    # 이후 INTERVAL_DAYS일마다 실행
    schedule.every(INTERVAL_DAYS).days.do(run_once)

    while True:
        schedule.run_pending()
        next_run = schedule.next_run()
        remaining = next_run - datetime.now() if next_run else timedelta(days=INTERVAL_DAYS)
        print(
            f"[WAIT] 다음 실행: {next_run.strftime('%Y-%m-%d %H:%M') if next_run else 'N/A'} "
            f"({int(remaining.total_seconds()//3600)}시간 후)",
            end="\r",
        )
        time.sleep(60)  # 1분마다 체크


def main() -> None:
    parser = argparse.ArgumentParser(
        description="정부조달 입찰 모니터링 에이전트"
    )
    parser.add_argument(
        "--schedule", action="store_true",
        help=f"스케줄 모드: {INTERVAL_DAYS}일 주기로 자동 실행"
    )
    parser.add_argument(
        "--days", type=int, default=None,
        help="조회할 과거 일수 (기본: 마지막 실행 이후)"
    )
    args = parser.parse_args()

    if not _check_config():
        print("\n.env.example 파일을 참고하여 .env 파일을 설정하세요.")
        return

    if args.schedule:
        run_scheduled()
    else:
        run_once(days_back=args.days)


if __name__ == "__main__":
    main()
