"""
정부조달 입찰 모니터링 에이전트 — 설정 파일
API 키와 엔드포인트는 .env 파일에서 로드합니다.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ─── 조달청 API 설정 ─────────────────────────────────────────────
# .env에 PROCUREMENT_API_KEY, PROCUREMENT_API_URL 설정 필요
PROCUREMENT_API_KEY = os.getenv("PROCUREMENT_API_KEY", "YOUR_API_KEY_HERE")

# 나라장터 API 엔드포인트 목록
# 용역(법률·컨설팅·ODA 등)에 집중하기 위해 용역 전용 + 전체 통합 두 곳을 수집
PROCUREMENT_API_URLS = [
    # 용역 입찰공고 기본 조회 (법률자문, 타당성조사, ODA 컨설팅 등)
    "https://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoServc",
]

# .env에 PROCUREMENT_API_URL 값이 있으면 우선 적용
_single_url = os.getenv("PROCUREMENT_API_URL")
if _single_url:
    PROCUREMENT_API_URLS = [_single_url]

# 한 번에 가져올 공고 수 (최대 100)
API_PAGE_SIZE = int(os.getenv("API_PAGE_SIZE", "100"))

# ─── Claude API 설정 ──────────────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = "claude-opus-4-6"

# ─── 스케줄 설정 ─────────────────────────────────────────────────
INTERVAL_DAYS = int(os.getenv("INTERVAL_DAYS", "3"))   # 3일에 한 번 실행
STATE_FILE = os.getenv("STATE_FILE", "procurement_agent/state.json")
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "output/reports")

# ─── 검색 도메인 및 키워드 ──────────────────────────────────────
SEARCH_DOMAINS = {
    "법률_법령": {
        "description": "법률제정, 법령제정 관련 입찰",
        "keywords": [
            "법률", "법령", "제정", "개정", "입법", "법제", "법무",
            "규정", "조례", "고시", "훈령", "법률자문", "법제처",
            "입법지원", "법령정비", "규제개선", "행정규칙",
        ],
        "claude_prompt": (
            "이 입찰이 법률·법령의 제정, 개정, 입법지원, 법무 자문, "
            "법령 정비, 규정·조례·고시 관련 업무인지 판단하세요."
        ),
    },
    "에너지_인프라": {
        "description": "에너지 인프라 타당성 조사 관련 입찰",
        "keywords": [
            "에너지", "인프라", "타당성", "타당성조사", "발전", "송전", "배전",
            "전력", "재생에너지", "태양광", "풍력", "수력", "원전",
            "ESS", "에너지저장", "스마트그리드", "전력망", "가스", "LNG",
            "에너지전환", "탄소중립", "온실가스", "기반시설",
        ],
        "claude_prompt": (
            "이 입찰이 에너지(전력·재생에너지·가스 등) 또는 인프라(발전·송배전·전력망 등)의 "
            "타당성 조사, 기획, 설계, 컨설팅 관련 업무인지 판단하세요."
        ),
    },
    "해외_ODA": {
        "description": "해외사업, 국제사업, ODA 관련 입찰",
        "keywords": [
            "ODA", "해외", "국제", "개발도상", "KOICA", "EDCF",
            "원조", "무상원조", "유상원조", "공적개발원조",
            "해외사업", "국제협력", "국제개발", "해외진출",
            "개도국", "해외투자", "해외자문", "글로벌",
        ],
        "claude_prompt": (
            "이 입찰이 해외사업, 국제사업, ODA(공적개발원조), 해외 인프라 개발, "
            "KOICA/EDCF 사업, 개도국 지원, 해외 컨설팅 관련 업무인지 판단하세요."
        ),
    },
}
