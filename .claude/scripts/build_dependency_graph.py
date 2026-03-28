#!/usr/bin/env python3
"""
build_dependency_graph.py
계약서 조항 의존관계 그래프 구축 스크립트.

입력: /output/logs/clauses_[딜명].json  (parse_document.py 출력)
출력: /output/logs/dependency_graph_[딜명].json

탐지 방식:
  1. 명시적 교차참조 (정규식)
  2. 정의 용어 사용 매핑 (문자열 검색)
  (논리적 의존은 LLM이 contract-dependency 스킬에서 처리)
"""

import json
import re
import sys
from pathlib import Path
from datetime import datetime, timezone


# ──────────────────────────────────────────────
# 1. 교차참조 탐지 패턴 (한국어 + 영문 계약서 공통)
# ──────────────────────────────────────────────
CROSS_REF_PATTERNS = [
    # "제N조", "제N조 제M항", "제N조(제목)", "동조", "전조"
    r"제\s*(\d+)\s*조(?:\s*제\s*(\d+)\s*항)?(?:\s*[가-힣\w]+)?",
    # "Article N", "Section N.M", "Clause N"
    r"(?:Article|Section|Clause)\s+(\d+(?:\.\d+)*)",
    # "(가)항, (나)항 등 — 단독 항 참조
    r"제\s*(\d+)\s*항",
    # "본조", "전항", "다음 조"
    r"(본조|전조|전항|다음\s*조|다음\s*항)",
]

COMPILED_PATTERNS = [re.compile(p) for p in CROSS_REF_PATTERNS]


def extract_article_number(article_str: str) -> str:
    """
    "제6조" → "6", "Article 12" → "12", "제3조 제2항" → "3"
    조항 식별자를 숫자 문자열로 정규화.
    """
    m = re.search(r"(\d+)", article_str)
    return m.group(1) if m else article_str


def detect_cross_references(clause: dict, all_clauses: list[dict]) -> list[dict]:
    """
    단일 조항의 본문에서 명시적 교차참조를 탐지한다.
    Returns list of edge dicts.
    """
    edges = []
    raw_text = clause.get("raw_text", "")
    from_id = clause["id"]
    from_num = extract_article_number(clause.get("article", ""))

    # 조항 번호 → id 매핑
    num_to_id = {
        extract_article_number(c.get("article", "")): c["id"]
        for c in all_clauses
    }

    seen_targets = set()

    for pattern in COMPILED_PATTERNS:
        for match in pattern.finditer(raw_text):
            ref_num = match.group(1) if match.lastindex and match.group(1) else None
            if ref_num is None:
                continue
            if ref_num == from_num:
                continue  # 자기참조 제외
            target_id = num_to_id.get(ref_num)
            if target_id and target_id not in seen_targets:
                seen_targets.add(target_id)
                edges.append({
                    "from": from_id,
                    "to": target_id,
                    "type": "CROSS_REF",
                    "strength": "STRONG",
                    "description": f"'{clause.get('article')}' 본문에서 '{_id_to_article(target_id, all_clauses)}' 명시적 참조",
                    "bidirectional": False,
                    "detected_by": "regex",
                })

    return edges


def _id_to_article(clause_id: str, all_clauses: list[dict]) -> str:
    for c in all_clauses:
        if c["id"] == clause_id:
            return c.get("article", clause_id)
    return clause_id


def detect_term_usage(clause: dict, definition_clauses: list[dict]) -> list[dict]:
    """
    DEFINITION 조항에서 정의된 용어가 다른 조항 본문에서 사용되는지 탐지한다.
    Returns list of edge dicts.
    """
    edges = []
    raw_text = clause.get("raw_text", "")
    from_id = clause["id"]

    for def_clause in definition_clauses:
        if def_clause["id"] == from_id:
            continue  # 정의 조항 자기참조 제외

        for term in def_clause.get("defined_terms", []):
            if len(term) < 2:
                continue  # 너무 짧은 용어 제외 (노이즈)
            # 용어가 본문에 등장하는지 확인 (단어 경계는 한국어에서 불필요)
            if term in raw_text:
                edges.append({
                    "from": def_clause["id"],
                    "to": from_id,
                    "type": "TERM_USAGE",
                    "strength": "STRONG",
                    "description": f"정의 용어 '{term}'이 '{clause.get('article')}' 본문에서 사용됨",
                    "bidirectional": False,
                    "detected_by": "term_match",
                    "term": term,
                })
                break  # 같은 정의 조항과의 엣지는 하나만 생성 (대표 용어)

    return edges


def deduplicate_edges(edges: list[dict]) -> list[dict]:
    """(from, to, type) 기준 중복 제거."""
    seen = set()
    result = []
    for e in edges:
        key = (e["from"], e["to"], e["type"])
        if key not in seen:
            seen.add(key)
            result.append(e)
    return result


def compute_hub_clauses(clauses: list[dict], edges: list[dict]) -> list[dict]:
    """연결 수(degree) 기준으로 허브 조항을 계산한다."""
    degree: dict[str, int] = {c["id"]: 0 for c in clauses}
    for e in edges:
        degree[e["from"]] = degree.get(e["from"], 0) + 1
        degree[e["to"]] = degree.get(e["to"], 0) + 1

    hub_list = []
    for c in clauses:
        cid = c["id"]
        hub_list.append({
            "clause_id": cid,
            "article": c.get("article", ""),
            "title": c.get("title", ""),
            "type": c.get("type", ""),
            "degree": degree.get(cid, 0),
        })

    hub_list.sort(key=lambda x: x["degree"], reverse=True)
    return hub_list


def build_graph(clauses_json_path: Path, output_path: Path, deal_id: str) -> dict:
    """
    메인 함수: clauses JSON을 읽어 의존관계 그래프를 생성하고 저장한다.
    """
    with open(clauses_json_path, encoding="utf-8") as f:
        data = json.load(f)

    clauses: list[dict] = data.get("clauses", [])
    definition_clauses = [c for c in clauses if c.get("type") == "DEFINITION"]

    all_edges: list[dict] = []

    for clause in clauses:
        # 1. 교차참조 탐지
        all_edges.extend(detect_cross_references(clause, clauses))
        # 2. 정의 용어 사용 탐지 (DEFINITION 조항이 아닌 경우만)
        if clause.get("type") != "DEFINITION":
            all_edges.extend(detect_term_usage(clause, definition_clauses))

    all_edges = deduplicate_edges(all_edges)
    hub_clauses = compute_hub_clauses(clauses, all_edges)

    graph = {
        "deal_id": deal_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "clause_count": len(clauses),
        "edge_count": len(all_edges),
        "clauses": clauses,
        "edges": all_edges,
        "hub_clauses": hub_clauses,
        "note": (
            "명시적 교차참조(CROSS_REF)와 정의 용어 사용(TERM_USAGE)만 포함. "
            "논리적 의존(LOGICAL_DEP)은 contract-dependency 스킬(LLM)에서 추가됨."
        ),
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(graph, f, ensure_ascii=False, indent=2)

    print(f"[build_dependency_graph] 완료: {output_path}")
    print(f"  조항 수: {len(clauses)}, 엣지 수: {len(all_edges)}")
    print(f"  허브 상위 3: {[h['article'] + '(' + str(h['degree']) + ')' for h in hub_clauses[:3]]}")

    return graph


# ──────────────────────────────────────────────
# CLI 진입점
# ──────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("사용법: python build_dependency_graph.py <clauses_json_path> <deal_id>")
        print("예시:  python build_dependency_graph.py output/logs/clauses_acme.json acme")
        sys.exit(1)

    clauses_path = Path(sys.argv[1])
    deal_name = sys.argv[2]
    out_path = Path(f"output/logs/dependency_graph_{deal_name}.json")

    build_graph(clauses_path, out_path, deal_name)
