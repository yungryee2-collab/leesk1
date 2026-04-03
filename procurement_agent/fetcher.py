"""
조달청 입찰공고 API 호출 모듈
API 응답 형식(XML/JSON)은 사용하는 API 종류에 따라 자동 감지합니다.
"""

import requests
import json
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Any
from .config import PROCUREMENT_API_KEY, PROCUREMENT_API_URLS, API_PAGE_SIZE


def _parse_xml_response(text: str) -> list[dict]:
    """XML 응답 파싱 (나라장터 표준 형식)"""
    root = ET.fromstring(text)
    items = []

    # 나라장터 API 응답 구조: response > body > items > item
    for item in root.findall(".//item"):
        bid = {}
        for child in item:
            bid[child.tag] = child.text or ""
        items.append(bid)

    return items


def _parse_json_response(data: dict) -> list[dict]:
    """JSON 응답 파싱"""
    # 일반적인 중첩 구조 탐색
    if "response" in data:
        data = data["response"]
    if "body" in data:
        data = data["body"]
    if "items" in data:
        items = data["items"]
        if isinstance(items, dict) and "item" in items:
            items = items["item"]
        if isinstance(items, dict):
            items = [items]
        return items if isinstance(items, list) else []
    return []


def _normalize_bid(raw: dict) -> dict:
    """다양한 API 응답 필드명을 표준 필드로 정규화
    - 나라장터 용역 API (BidPublicInfoService)
    - 누리장터 민간입찰 API (PrvtBidNtceService) 필드명 포함
    """
    field_map = {
        "bid_id": [
            "bidNtceNo",        # 나라장터
            "prvtBidNtceNo",    # 누리장터 민간
            "ntceNo", "공고번호", "bid_id",
        ],
        "title": [
            "bidNtceNm",        # 나라장터
            "bidNm",            # 누리장터 민간
            "ntceNm", "공고명", "title", "공고제목",
        ],
        "org": [
            "ntceInsttNm",      # 나라장터 수요기관
            "dmstcInsttNm",     # 누리장터 수요기관
            "orgnztNm", "발주기관", "org", "기관명",
        ],
        "budget": [
            "presmptPrce",      # 나라장터 추정가격
            "bsisAmt",          # 누리장터 기초금액
            "추정가격", "budget", "예산",
        ],
        "deadline": [
            "bidClseDt",        # 나라장터
            "prvtBidClseDt",    # 누리장터
            "입찰마감일시", "deadline", "마감일",
        ],
        "notice_date": [
            "bidNtceDt",        # 나라장터
            "prvtBidNtceDt",    # 누리장터
            "ntceDt", "notice_date", "공고일시", "공고일",
        ],
        "method": ["bidMethdNm", "입찰방식", "method"],
        "type": ["cntrctCnclsMthdNm", "계약방법", "type"],
        "url": ["detailUrl", "linkUrl", "url"],
        "source": ["_source"],  # 수집 출처 (fetcher에서 주입)
    }

    normalized = {}
    for std_key, candidates in field_map.items():
        for cand in candidates:
            if cand in raw and raw[cand]:
                normalized[std_key] = raw[cand]
                break
        if std_key not in normalized:
            normalized[std_key] = ""

    normalized["_raw"] = raw
    return normalized


def _fetch_from_url(url: str, start_date: str, end_date: str) -> list[dict]:
    """단일 API URL에서 전체 페이지를 수집합니다."""
    # 누리장터 민간 API는 날짜 파라미터명이 다름
    is_prvt = "PrvtBidNtce" in url
    date_param_start = "prvtBidNtceBgnDt" if is_prvt else "inqryBgnDt"
    date_param_end   = "prvtBidNtceEndDt" if is_prvt else "inqryEndDt"
    source_label     = "누리장터(민간)" if is_prvt else "나라장터(공공)"

    params = {
        "serviceKey": PROCUREMENT_API_KEY,
        "numOfRows": str(API_PAGE_SIZE),
        "pageNo": "1",
        date_param_start: start_date,
        date_param_end: end_date,
        "type": "json",
    }
    if not is_prvt:
        params["inqryDiv"] = "1"

    collected = []
    page = 1

    while True:
        params["pageNo"] = str(page)
        try:
            resp = requests.get(
                url, params=params, timeout=30,
                headers={"Accept": "application/json, application/xml"},
            )
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"[ERROR] API 호출 실패 ({url.split('/')[-1]}, page {page}): {e}")
            break

        content_type = resp.headers.get("Content-Type", "")
        raw_items: list[dict] = []

        if "xml" in content_type or resp.text.strip().startswith("<"):
            raw_items = _parse_xml_response(resp.text)
        else:
            try:
                data: Any = resp.json()
                raw_items = _parse_json_response(data)
            except json.JSONDecodeError:
                print(f"[ERROR] 응답 파싱 실패: {resp.text[:200]}")
                break

        if not raw_items:
            break

        for item in raw_items:
            item["_source"] = source_label  # 출처 태깅
        collected.extend([_normalize_bid(item) for item in raw_items])

        if len(raw_items) < API_PAGE_SIZE:
            break

        page += 1
        if page > 20:
            break

    return collected


def fetch_bids(days_back: int = 3) -> list[dict]:
    """
    최근 N일간 입찰공고를 API에서 가져옵니다.
    용역 전용 + 전체 통합 엔드포인트를 모두 수집하여 중복 제거합니다.

    Args:
        days_back: 몇 일 이전부터 조회할지 (기본 3일)

    Returns:
        정규화된 입찰공고 목록 (중복 제거)
    """
    start_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y%m%d%H%M%S")
    end_date = datetime.now().strftime("%Y%m%d%H%M%S")

    seen_ids: set[str] = set()
    all_bids: list[dict] = []

    for url in PROCUREMENT_API_URLS:
        endpoint_name = url.split("/")[-1]
        print(f"[FETCH] {endpoint_name} 조회 중...")
        bids = _fetch_from_url(url, start_date, end_date)

        for bid in bids:
            uid = bid.get("bid_id") or str(bid.get("_raw", {}))
            if uid not in seen_ids:
                seen_ids.add(uid)
                all_bids.append(bid)

        print(f"        → {len(bids)}건 수집 (누적 {len(all_bids)}건)")

    print(f"[INFO] 최종 {len(all_bids)}건 공고 수집 ({start_date[:8]} ~ {end_date[:8]})")
    return all_bids
