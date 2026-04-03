"""
Claude API 기반 입찰공고 관련성 분석기
1단계: 키워드 사전 필터링 (빠름)
2단계: Claude AI 정밀 분류 (정확함)
"""

import anthropic
import json
from .config import ANTHROPIC_API_KEY, CLAUDE_MODEL, SEARCH_DOMAINS


def _keyword_prefilter(bids: list[dict]) -> dict[str, list[dict]]:
    """
    1단계: 키워드 기반 빠른 사전 필터링.
    각 도메인별로 후보 공고를 추려냅니다.
    """
    candidates: dict[str, list[dict]] = {domain: [] for domain in SEARCH_DOMAINS}

    for bid in bids:
        search_text = (
            (bid.get("title") or "") + " " +
            (bid.get("org") or "") + " " +
            " ".join(str(v) for v in bid.get("_raw", {}).values())
        ).lower()

        for domain, cfg in SEARCH_DOMAINS.items():
            for kw in cfg["keywords"]:
                if kw.lower() in search_text:
                    candidates[domain].append(bid)
                    break  # 한 도메인에 중복 추가 방지

    for domain, lst in candidates.items():
        print(f"[FILTER] {domain}: 키워드 매칭 {len(lst)}건")

    return candidates


def _claude_classify(bids: list[dict], domain: str, domain_cfg: dict) -> list[dict]:
    """
    2단계: Claude로 후보 공고의 실제 관련성을 정밀 분류합니다.
    배치로 처리하여 API 호출 횟수를 최소화합니다.
    """
    if not bids:
        return []

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    # 배치 크기: 한 번에 최대 20건
    BATCH_SIZE = 20
    relevant = []

    for i in range(0, len(bids), BATCH_SIZE):
        batch = bids[i:i + BATCH_SIZE]

        # 배치를 JSON으로 직렬화하여 Claude에게 전달
        bid_list_text = json.dumps(
            [
                {
                    "index": j,
                    "title": b.get("title", ""),
                    "org": b.get("org", ""),
                    "budget": b.get("budget", ""),
                }
                for j, b in enumerate(batch)
            ],
            ensure_ascii=False,
            indent=2,
        )

        prompt = f"""다음은 정부조달 입찰공고 목록입니다.
각 공고가 아래 기준에 해당하는지 판단하세요:

[분류 기준]
{domain_cfg['claude_prompt']}

[입찰공고 목록]
{bid_list_text}

판단 기준:
- "관련있음": 공고 제목이나 기관명을 보아 해당 분야와 직접 관련된 경우
- "관련없음": 관련이 없거나 불명확한 경우

반드시 JSON 배열로만 응답하세요. 다른 설명은 하지 마세요.
형식: [{{"index": 숫자, "relevant": true/false, "reason": "한 줄 이유"}}]
"""

        try:
            response = client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=2000,
                thinking={"type": "adaptive"},
                messages=[{"role": "user", "content": prompt}],
            )

            # 응답에서 JSON 추출
            text = next(
                (b.text for b in response.content if b.type == "text"), ""
            )

            # JSON 블록 추출 (마크다운 코드블록 제거)
            text = text.strip()
            if "```" in text:
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]

            results = json.loads(text.strip())
            for r in results:
                if r.get("relevant"):
                    bid_item = batch[r["index"]].copy()
                    bid_item["_reason"] = r.get("reason", "")
                    bid_item["_domain"] = domain
                    relevant.append(bid_item)

        except (json.JSONDecodeError, IndexError, KeyError, anthropic.APIError) as e:
            print(f"[WARN] Claude 분류 오류 ({domain}, batch {i//BATCH_SIZE+1}): {e}")
            # 오류 시 키워드 매칭된 항목 그대로 포함
            for bid in batch:
                bid_copy = bid.copy()
                bid_copy["_reason"] = "키워드 매칭 (Claude 분류 실패)"
                bid_copy["_domain"] = domain
                relevant.append(bid_copy)

    print(f"[CLASSIFY] {domain}: {len(relevant)}건 최종 선별")
    return relevant


def analyze_bids(bids: list[dict]) -> dict[str, list[dict]]:
    """
    전체 입찰공고를 3개 분야로 분류합니다.

    Returns:
        {도메인명: [관련 입찰공고 목록]} 딕셔너리
    """
    # 1단계: 키워드 필터
    candidates = _keyword_prefilter(bids)

    # 2단계: Claude 정밀 분류
    results: dict[str, list[dict]] = {}
    for domain, domain_cfg in SEARCH_DOMAINS.items():
        results[domain] = _claude_classify(candidates[domain], domain, domain_cfg)

    total = sum(len(v) for v in results.values())
    print(f"[ANALYZE] 최종 관련 공고: 총 {total}건")
    return results
