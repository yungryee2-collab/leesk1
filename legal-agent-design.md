# 법률 딜 자동화 에이전트 시스템 설계서
**워크플로우명**: Multi-Domain Legal Transaction Automation Agent
**문서 버전**: v1.0 | 작성일: 2026-03-24

---

## 1. 작업 컨텍스트 문서

### 1.1 딜 배경·목적·범위

**목적**: Term Sheet 협상부터 계약 서명 전 단계까지의 법률 업무를 Claude Code 기반 에이전트로 자동화하여, 파트너가 클라이언트에게 직접 발송 가능한 품질(Client-Ready)의 산출물 생성.

**범위**:
- **포함**: Term Sheet 작성·검토, DD 체크리스트·이슈 분석, 계약수정안(레드라인), 협상전략 메모, 법률의견서
- **제외**: 서명 후 계약 이행 모니터링, 소송·분쟁 절차, 세무신고

### 1.2 입출력 정의

**입력**:

| 구분 | 내용 | 형식 |
|------|------|------|
| 필수 | 딜 파라미터 지시서 (섹터/관할/단계/포지션/상대방) | 텍스트 (YAML 또는 자연어) |
| 필수 | 대상 문서 (Term Sheet / DD 자료 / 계약서) | PDF, DOCX, TXT |
| 선택 | 참조 선례·시장관행 자료 | PDF, DOCX |
| 선택 | 이전 단계 산출물 (체이닝 시) | JSON (step_*.json) |

**출력**:

| 산출물 | 형식 | 저장 위치 |
|--------|------|---------|
| 법률의견서 | MD | `/output/reports/` |
| 계약수정안 (레드라인) | MD | `/output/drafts/` |
| 협상전략 메모 | MD | `/output/reports/` |
| DD 리포트 | MD | `/output/reports/` |
| Term Sheet 초안 | MD | `/output/drafts/` |
| 단계별 중간 산출물 | JSON | `/output/logs/step_*.json` |
| 판단 근거·가정사항 로그 | JSON | `/output/logs/assumptions_*.json` |

### 1.3 관할·섹터·거래 단계

**지원 섹터**:

| 섹터 | 주요 계약 유형 | 스킬 우선순위 |
|------|------------|-------------|
| 에너지·PF | PPA, 대출약정, EPC, O&M | due-diligence → regulatory → contract-review → deal-structure |
| M&A | SPA, SHA, NDA | due-diligence → contract-review → negotiation → deal-structure |
| 인프라 | 양허협약, 공사계약, 운영협약 | regulatory → due-diligence → contract-review → negotiation |
| 부동산 | 매매계약, 임대차, 분양계약 | contract-review → term-sheet → negotiation |

**지원 관할**: 대한민국, 동남아(베트남·인도네시아·필리핀), 유럽(영국·독일·폴란드), 미국(델라웨어·뉴욕), 다관할 혼합(ICC·SIAC·KCAB)

**거래 단계 범위**: Term Sheet 협상 → LOI/MOU → DD → 계약협상 → 최종안 검토 (서명 이후 제외)

### 1.4 용어 정의

| 용어 | 정의 |
|------|------|
| 매도인/매수인 | Seller/Buyer (혼용 금지) |
| 대주단 | Lender Group / Syndicated Lenders |
| 발주처 | Offtaker / Procuring Entity |
| 사업주 | Project Company / SPV |
| 전력 | Power/Electricity (전기 혼용 금지) |
| 변경 | Amendment/Modification (수정 대신) |
| 3단계 포지셔닝 | Aggressive / Balanced / Conservative 협상안 |
| Client-Ready | 파트너 검토 없이 클라이언트 직발송 가능 수준 |

---

## 2. 워크플로우 정의

### 2.1 전체 흐름도

```
INPUT: 딜 파라미터 지시서 + 대상 문서 + (선택) 이전 단계 JSON
  │
  ▼
ORCHESTRATOR (CLAUDE.md)
  딜 파라미터 파싱 → 워크플로우 라우팅 → 서브에이전트 순차 호출
  │
  ├─→ [Term Sheet 단계] Term Sheet Agent
  │     term-sheet → strategic-analysis → negotiation
  │
  ├─→ [DD 단계] DD Agent
  │     due-diligence → regulatory → strategic-analysis
  │
  └─→ [계약협상 단계] Contract Negotiation Agent
        contract-review → negotiation → deal-structure
  │
  ▼
QA Reviewer Agent
  qa-reviewer → (필요 시) legal-translation
  │
  ├─→ PASS: 최종 산출물 /output/ 저장
  └─→ FAIL: 재시도(최대 2회) → 파트너 에스컬레이션
```

### 2.2 단계별 흐름 및 성공 기준

#### Phase 0: 오케스트레이터 — 딜 파싱 및 라우팅

**처리**:
1. 딜 파라미터 추출: 섹터, 관할, 거래 단계, 클라이언트 포지션, 상대방
2. 누락 파라미터 → 합리적 기본값 적용 + 가정사항 JSON 저장
3. 단계 라우팅 및 체이닝 여부 확인

**분기 조건**:

| 조건 | 라우팅 |
|------|--------|
| 입력 문서: Term Sheet / LOI | Term Sheet Agent |
| 입력 문서: DD 자료 / 체크리스트 요청 | DD Agent |
| 입력 문서: 계약서 초안 / 계약수정안 | Contract Negotiation Agent |
| 이전 단계 JSON 존재 + 다음 단계 지시 | 해당 에이전트 + 컨텍스트 주입 |
| 복수 계약서 + 병렬 처리 지시 | 병렬 서브에이전트 분기 |

**성공 기준**: 5개 딜 파라미터 중 최소 3개 확정, 가정사항 명시
**검증**: 스키마 검증 (파라미터 JSON 구조)
**실패 처리**: 합리적 기본값 적용 후 에스컬레이션 로그 기록

---

#### Phase 1: Term Sheet Agent

**스킬 체인**: `term-sheet` → `strategic-analysis` → `negotiation`

**LLM 판단 영역**: 상업조건 시장 합리성 판단, 3개 대안 구조 비교·권고, 협상 레드라인·BATNA 설정
**코드 처리 영역**: 문서 파싱·텍스트 추출, 조건 매핑 테이블 생성, JSON 저장

**산출물**:
- `/output/drafts/termsheet_[딜명]_v[N].md`
- `/output/logs/step_termsheet_[딜명].json`

**성공 기준**: 핵심 조건 전항목 커버 + 3단계 포지션 완비 + Executive Summary 포함
**검증**: 스키마 검증 + LLM 자기검증
**실패 처리**: 자동 재시도 최대 2회 → QA-Reviewer 호출 → 파트너 에스컬레이션

---

#### Phase 2: DD Agent

**스킬 체인**: `due-diligence` → `regulatory` → `strategic-analysis`

**LLM 판단 영역**: 이슈 중요도 분류, 규제 리스크 해석·딜브레이커 식별, 이슈별 완화 전략 권고
**코드 처리 영역**: DD 자료 파싱·색인, 체크리스트 항목 집계, 규제 DB API 호출

**산출물**:
- `/output/reports/dd_report_[딜명].md` (스코어카드 포함)
- `/output/logs/step_dd_[딜명].json` (협상전략 체이닝용)

**성공 기준**: 섹터별 필수 이슈 100% 포함 + 심각도 3단계 분류(Critical/Major/Minor) 완비
**검증**: 규칙 기반 (항목 수·필수 이슈 포함 여부) + LLM 자기검증
**실패 처리**: 자동 재시도 최대 2회 → QA-Reviewer 호출 → 파트너 에스컬레이션

---

#### Phase 3: Contract Negotiation Agent

**체이닝**: `step_dd_[딜명].json` 존재 시 DD 이슈·전략 컨텍스트 주입
**스킬 체인**: `contract-review` → `negotiation` → `deal-structure`

**처리 흐름**:
```
계약서 파싱 (스크립트)
→ 3단계 누적 계약 분석 (contract-review)
   ├── [1단계] 문서 분류·딜 파라미터 추론
   ├── [2단계] 취약점 분석 (참조자료 대조)
   └── [3단계] 조항별 수정안 (3단계 포지셔닝)
→ 협상전략 수립 (negotiation: BATNA·레드라인)
→ 딜 구조 최적화 (deal-structure: SPC·세무·금융스택)
→ 계약수정안 + 협상 메모 생성
```

**LLM 판단 영역**: 조항별 위험 분류·우선순위, 협상 레드라인·BATNA, 거래구조 최적화 추론, 법률의견 초안
**코드 처리 영역**: 계약서 조항 파싱·색인, 레드라인 형식 변환, 환율·금융 데이터 API

**산출물**:
- `/output/drafts/redline_[딜명]_v[N].md`
- `/output/reports/negotiation_memo_[딜명].md`
- `/output/logs/step_contract_[딜명].json`

**성공 기준**: 전 조항 커버(누락 0개) + 3단계 포지션 완비 + 협상 우선순위 Top 5 + BATNA·레드라인 정의
**검증**: 스키마 검증 + LLM 자기검증
**실패 처리**: 자동 재시도 최대 2회 → QA-Reviewer 호출 → 파트너 에스컬레이션

---

#### Phase 4: QA Reviewer Agent

**스킬 체인**: `qa-reviewer` → (필요 시) `legal-translation`

**처리**:
```
산출물 수신
→ [1단계] 전체 문서 구조·완결성 검토 (VERDICT-first, 100점 스코어카드)
→ [2단계] 섹션별 정밀 검토 (치명적 결함 탐지)
→ PASS/FAIL 판정
→ FAIL: 재시도 지시 또는 에스컬레이션
→ 번역 필요 시: legal-translation 호출
```

**성공 기준**: QA 스코어 85점 이상 + Critical Issue 0개 + 결론 우선 구조 + 용어 일관성
**검증**: LLM 자기검증 (qa-reviewer 내부 로직)
**실패 처리**: 재시도 최대 2회 → 2회 실패 시 `/output/logs/escalation_[딜명].json` 생성 + 파트너 에스컬레이션

---

### 2.3 체이닝 흐름

```
Phase 2 완료 → step_dd_[딜명].json 저장
  [포함: 이슈 목록, 심각도, 딜브레이커, 규제 리스크]
    │
    ▼
Phase 3 시작 시 step_dd JSON 로드
  → DD 이슈 → 계약 조항 위험 매핑
  → DD 딜브레이커 → 협상 레드라인 자동 반영
  → 조항별 수정 우선순위에 DD 이슈 가중치 적용
```

### 2.4 병렬 처리 (복수 계약서, 선택적)

```
오케스트레이터
  ├─→ [Sub-Agent A] SPA 검토
  ├─→ [Sub-Agent B] SHA 검토
  └─→ [Sub-Agent C] PPA 검토
       ↓ (각각 독립 실행)
오케스트레이터: 개별 step_*.json 수집 → 통합 크로스리뷰
  └─→ QA Reviewer: 계약 간 일관성 검증 (정의 충돌·조건 상충 탐지)
```

---

## 3. 구현 스펙

### 3.1 폴더 구조

```
/project-root
  ├── CLAUDE.md                              # 오케스트레이터 지침
  ├── /.claude
  │   ├── /skills/
  │   │   ├── contract-review.md
  │   │   ├── qa-reviewer.md
  │   │   ├── legal-translation.md
  │   │   ├── strategic-analysis.md
  │   │   ├── negotiation.md
  │   │   ├── due-diligence.md
  │   │   ├── regulatory.md
  │   │   ├── term-sheet.md
  │   │   └── deal-structure.md
  │   ├── /scripts/
  │   │   ├── parse_document.py              # PDF/DOCX 파싱·텍스트 추출
  │   │   ├── index_clauses.py               # 계약 조항 색인·검색
  │   │   ├── format_redline.py              # 레드라인 형식 변환
  │   │   ├── fetch_fx_rates.py              # 환율 API 호출
  │   │   ├── fetch_regulatory.py            # 규제 DB API 호출 (플레이스홀더)
  │   │   └── aggregate_checklist.py         # DD 체크리스트 집계
  │   ├── /references/
  │   │   ├── /precedents/                   # 섹터별 계약 선례
  │   │   ├── /market-practice/              # 관할별 시장관행
  │   │   └── /jurisdiction/                 # 관할법 참조 자료
  │   └── /agents/
  │       ├── term-sheet-agent.md
  │       ├── dd-agent.md
  │       ├── contract-negotiation-agent.md
  │       └── qa-reviewer-agent.md
  ├── /output
  │   ├── /drafts/                           # Term Sheet 초안·계약수정안
  │   ├── /reports/                          # DD 리포트·법률의견서·협상 메모
  │   └── /logs/                             # step_*.json·assumptions_*.json·escalation_*.json
  └── /docs/                                 # 입력 문서 업로드 위치
```

### 3.2 CLAUDE.md 핵심 섹션 목록

1. **역할 정의**: 오케스트레이터 — 딜 파싱, 라우팅, 서브에이전트 순차 호출
2. **딜 파라미터 파싱 규칙**: 5개 항목 추출, 미확인 시 기본값 + 가정사항 명시
3. **Zero-Question 원칙**: 추가 질문 금지, 합리적 가정 적용
4. **결론 우선 원칙**: 결론 → 근거 → 대안 구조 강제
5. **라우팅 규칙**: 문서 유형·단계별 서브에이전트 호출 순서
6. **체이닝 규칙**: 이전 단계 JSON 경로 전달 방식
7. **에스컬레이션 규칙**: 재시도 2회 초과 시 파트너 플래그
8. **출력 언어·용어 규칙**: 한국어 우선, 지정 용어 사용

### 3.3 에이전트 구조

**구조 유형**: 오케스트레이터 + 4개 서브에이전트 (선형 기본 / 병렬 옵션)

| 에이전트 | 파일 | 역할 | 입력 | 출력 |
|---------|------|------|------|------|
| Orchestrator | CLAUDE.md | 딜 파싱·라우팅·진행 관리 | 딜 지시서 + 문서 | 라우팅 지시 + step JSON 경로 |
| Term Sheet Agent | term-sheet-agent.md | Term Sheet 작성·협상안 | 원본 TS + step JSON (선택) | termsheet_*.md + step JSON |
| DD Agent | dd-agent.md | DD 체크리스트·이슈 분석 | DD 자료 | dd_report_*.md + step JSON |
| Contract Negotiation Agent | contract-negotiation-agent.md | 계약수정안·협상전략 | 계약서 + step_dd JSON | redline_*.md + memo + step JSON |
| QA Reviewer Agent | qa-reviewer-agent.md | 품질 검증·언어 최종화 | 모든 산출물 | PASS/FAIL + 최종본 |

**원칙**: 서브에이전트 간 직접 호출 금지. 모든 흐름은 CLAUDE.md 경유.

### 3.4 스킬 활용 선택 및 트리거 조건

| 스킬 | 활용 에이전트 | 트리거 조건 |
|------|------------|-----------|
| `term-sheet` | Term Sheet Agent | Term Sheet / LOI 문서 입력 시 |
| `strategic-analysis` | Term Sheet Agent, DD Agent | 딜 전략 판단·대안 비교 필요 시 |
| `negotiation` | Term Sheet Agent, Contract Negotiation Agent | 협상 포지션 수립 시 |
| `due-diligence` | DD Agent | DD 단계 라우팅 시 |
| `regulatory` | DD Agent | 관할·인허가 리스크 분석 시 |
| `contract-review` | Contract Negotiation Agent | 계약서 파일 입력 시 |
| `deal-structure` | Contract Negotiation Agent | 거래구조 최적화 필요 시 |
| `qa-reviewer` | QA Reviewer Agent | 모든 단계 산출물 생성 완료 후 |
| `legal-translation` | QA Reviewer Agent | 영문↔한국어 변환 필요 시 |

### 3.5 주요 산출물 파일 형식

#### `/output/drafts/termsheet_[딜명]_v[N].md`
```
# Term Sheet — [딜명]
## Executive Summary
## 핵심 상업조건 요약
## 조건별 협상 포지션
| 조건 | Aggressive | Balanced | Conservative |
## 가정사항 및 미확인 사항
```

#### `/output/drafts/redline_[딜명]_v[N].md`
```
# 계약수정안 (레드라인) — [딜명]
## Executive Summary
## 협상 우선순위 Top 5
## 조항별 수정안
| 조항 | 원문 | Aggressive | Balanced | Conservative | 수정 근거 |
## 레드라인 (절대 양보 불가)
## BATNA
```

#### `/output/reports/dd_report_[딜명].md`
```
# DD 리포트 — [딜명]
## Executive Summary + 스코어카드
## 섹터별 체크리스트 결과
## 이슈 우선순위 (Critical / Major / Minor)
## 규제 리스크 분석
## 딜 전략 권고
## 가정사항
```

#### `/output/logs/step_[단계]_[딜명].json`
```json
{
  "deal_id": "...",
  "stage": "dd | termsheet | contract",
  "timestamp": "...",
  "deal_params": { "sector": "...", "jurisdiction": "...", "position": "..." },
  "key_issues": [],
  "dealbreakers": [],
  "assumptions": [],
  "output_path": "..."
}
```

#### `/output/logs/escalation_[딜명].json`
```json
{
  "deal_id": "...",
  "stage": "...",
  "reason": "QA 2회 실패 | 파라미터 미확인",
  "qa_score": 0,
  "critical_issues": [],
  "recommended_action": "파트너 검토 요청"
}
```

---

## 4. 구현 주의사항

### 4.1 자기검증 체크포인트

| 체크 항목 | 확인 방법 | 위험 수준 |
|---------|---------|---------|
| 3단계 포지션 누락 | 스키마 검증 | Critical |
| 관할법 오류 | LLM 자기검증 | Critical |
| DD 이슈↔계약수정안 불일치 | 체이닝 JSON 크로스체크 | Major |
| 레드라인 미정의 | 스키마 검증 | Critical |
| 가정사항 미명시 | LLM 자기검증 | Major |

### 4.2 파라미터 기본값

| 파라미터 | 기본값 |
|---------|--------|
| 섹터 | M&A (SPA + SHA) |
| 관할 | 대한민국 (한국법) |
| 중재기관 | KCAB |
| 클라이언트 포지션 | 매수인 |
| 품질 기준 | 파트너 검토 후 발송 수준 |

### 4.3 에스컬레이션 기준

| 조건 | 처리 |
|------|------|
| QA 스코어 85점 미만 + 재시도 2회 실패 | 파트너 에스컬레이션 |
| Critical Issue 탐지 (계약 무효화 리스크) | 즉시 파트너 에스컬레이션 |
| 관할법 불확실 (다관할 충돌) | 파트너 + 현지 법무법인 확인 요청 |
| 외부 발송 계약서·의견서 최종안 | 파트너 승인 전 발송 보류 |

---

*이 설계서는 구현 단계에서 CLAUDE.md, AGENT.md, 스킬 파일 작성 시 참조 기준으로 사용한다.*
*CLAUDE.md, AGENT.md, 스킬 파일의 상세 내용은 구현 시 별도 작성.*
