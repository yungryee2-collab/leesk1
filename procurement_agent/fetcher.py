"""
조달청 입찰공고 API 호출 모듈
API 응답 형식(XML/JSON)은 사용하는 API 종류에 따라 자동 감지합니다.
"""

import requests
import json
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Any
from .config import PROCUREMENT_API_KEY, PROCUREMENT_API_URL, API_PAGE_SIZE


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
    """다양한 API 응답 필드명을 표준 필드로 정규화"""
    # 나라장터 API 필드명 매핑 (API마다 다를 수 있으므로 여러 후보 지원)
    field_map = {
        "bid_id": ["bidNtceNo", "공고번호", "ntceNo", "bid_id"],
        "title": ["bidNtceNm", "공고명", "ntceNm", "title", "공고제목"],
        "org": ["ntceInsttNm", "발주기관", "orgnztNm", "org", "기관명"],
        "budget": ["presmptPrce", "추정가격", "budget", "예산"],
        "deadline": ["bidClseDt", "입찰마감일시", "deadline", "마감일"],
        "notice_date": ["bidNtceDt", "공고일시", "ntceDt", "notice_date", "공고일"],
        "method": ["bidMethdNm", "입찰방식", "method"],
        "type": ["cntrctCnclsMthdNm", "계약방법", "type"],
        "url": ["detailUrl", "linkUrl", "url"],
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


def fetch_bids(days_back: int = 3) -> list[dict]:
    """
    최근 N일간 입찰공고를 API에서 가져옵니다.

    Args:
        days_back: 몇 일 이전부터 조회할지 (기본 3일)

    Returns:
        정규화된 입찰공고 목록
    """
    start_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y%m%d%H%M%S")
    end_date = datetime.now().strftime("%Y%m%d%H%M%S")

    params = {
        "serviceKey": PROCUREMENT_API_KEY,
        "numOfRows": str(API_PAGE_SIZE),
        "pageNo": "1",
        "inqryDiv": "1",          # 입찰공고 구분
        "inqryBgnDt": start_date,
        "inqryEndDt": end_date,
        "type": "json",
    }

    all_bids = []
    page = 1

    while True:
        params["pageNo"] = str(page)

        try:
            response = requests.get(
                PROCUREMENT_API_URL,
                params=params,
                timeout=30,
                headers={"Accept": "application/json, application/xml"},
            )
            response.raise_for_status()
        except requests.RequestException as e:
            print(f"[ERROR] API 호출 실패 (page {page}): {e}")
            break

        content_type = response.headers.get("Content-Type", "")
        raw_items: list[dict] = []

        if "xml" in content_type or response.text.strip().startswith("<"):
            raw_items = _parse_xml_response(response.text)
        else:
            try:
                data: Any = response.json()
                raw_items = _parse_json_response(data)
            except json.JSONDecodeError:
                print(f"[ERROR] 응답 파싱 실패: {response.text[:200]}")
                break

        if not raw_items:
            break

        all_bids.extend([_normalize_bid(item) for item in raw_items])

        # 마지막 페이지 확인
        if len(raw_items) < API_PAGE_SIZE:
            break

        page += 1
        if page > 20:  # 무한루프 방지 (최대 2000건)
            break

    print(f"[INFO] 총 {len(all_bids)}건 공고 수집 ({start_date[:8]} ~ {end_date[:8]})")
    return all_bids
