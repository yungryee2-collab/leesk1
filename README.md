# 법률 딜 자동화 에이전트 시스템

> **Multi-Domain Legal Transaction Automation Agent**  
> Term Sheet부터 계약 체결 전 단계까지의 법률 업무를 자동화하는 AI 기반 에이전트 시스템

---

## 🎯 프로젝트 개요

이 프로젝트는 **법률 딜 거래(deal)**의 핵심 단계들을 자동화하여 클라이언트에게 직접 발송 가능한 수준의 전문적인 법률 산출물을 생성합니다.

### 주요 목표
- 📄 **Term Sheet 작성 & 협상 전략** 자동화
- 🔍 **실사(Due Diligence) 분석** 자동화
- ✏️ **계약 수정안(레드라인)** 자동 생성
- 📋 **협상 메모 & 법률의견서** 자동 작성
- ⚖️ **다관할 법률** 통합 지원

---

## 💼 주요 기능

| 기능 | 설명 | 산출물 |
|------|------|--------|
| **Term Sheet Agent** | Term Sheet 작성 및 협상 포지션 수립 | 3단계 협상안(Aggressive/Balanced/Conservative) |
| **DD Agent** | 실사 자료 분석 및 이슈 식별 | DD 리포트 + 이슈 우선순위화 |
| **Contract Negotiation Agent** | 계약 조항 분석 및 수정안 작성 | 레드라인 + 협상 전략 메모 |
| **QA Reviewer Agent** | 최종 산출물 품질 검증 | 품질 점수 + 최종 검수 |

---

## 🌍 지원 범위

### 지원 섹터
- **에너지 · PF**: PPA, 대출약정, EPC, O&M
- **M&A**: SPA, SHA, NDA
- **인프라**: 양허협약, 공사계약, 운영협약
- **부동산**: 매매계약, 임대차, 분양계약

### 지원 관할
- 🇰🇷 **대한민국** (한국법)
- 🌏 **동남아**: 베트남, 인도네시아, 필리핀
- 🇪🇺 **유럽**: 영국, 독일, 폴란드
- 🇺🇸 **미국**: 델라웨어, 뉴욕
- 🌐 **다관할 중재**: ICC, SIAC, KCAB

### 거래 단계
```
Term Sheet → LOI/MOU → 실사(DD) → 계약협상 → 최종 검토
(서명 이후는 범위 제외)
```

---

## 📁 프로젝트 구조

```
leesk1/
├── README.md                           # 이 파일 (프로젝트 개요)
├── legal-agent-design.md               # 시스템 설계 문서 (상세 명세)
│
├── .claude/                            # Claude Code 설정 디렉토리
│   ├── /skills/                        # 에이전트 스킬 정의
│   │   ├── term-sheet.md
│   │   ├── contract-review.md
│   │   ├── due-diligence.md
│   │   ├── negotiation.md
│   │   ├── strategic-analysis.md
│   │   ├── regulatory.md
│   │   ├── deal-structure.md
│   │   ├── qa-reviewer.md
│   │   └── legal-translation.md
│   │
│   ├── /agents/                        # 에이전트 구현 파일
│   │   ├── term-sheet-agent.md
│   │   ├── dd-agent.md
│   │   ├── contract-negotiation-agent.md
│   │   └── qa-reviewer-agent.md
│   │
│   ├── /scripts/                       # 유틸리티 스크립트
│   │   ├── parse_document.py           # PDF/DOCX 파싱
│   │   ├── index_clauses.py            # 계약 조항 색인
│   │   ├── format_redline.py           # 레드라인 포맷
│   │   └── ...
│   │
│   ├── /references/                    # 참조 자료
│   │   ├── /precedents/                # 섹터별 계약 선례
│   │   ├── /market-practice/           # 관할별 시장관행
│   │   └── /jurisdiction/              # 관할법 참고 자료
│   │
│   └── settings.json                   # Claude Code 설정
│
├── /output/                            # 산출물 저장 디렉토리
│   ├── /drafts/                        # Term Sheet, 계약수정안
│   ├── /reports/                       # DD 리포트, 협상 메모, 법률의견서
│   └── /logs/                          # 단계별 로그 (JSON)
│
├── /docs/                              # 입력 문서 (임시 저장)
│   └── (클라이언트 제공 문서)
│
└── CLAUDE.md                           # 오케스트레이터 지침 (향후 작성)
```

---

## 📖 주요 파일 설명

### `legal-agent-design.md` ⭐
**현재 레포지터리의 핵심 문서**
- 전체 시스템 아키텍처 설계
- 4개 에이전트의 역할 및 흐름도
- 산출물 형식 및 성공 기준
- 단계별 체이닝 규칙
- 파라미터 정의 및 기본값
- **읽기**: 시스템 전체 이해를 위해 먼저 읽어야 할 문서

### `CLAUDE.md` (향후 작성)
- 오케스트레이터 역할 지침
- 딜 파라미터 파싱 규칙
- 워크플로우 라우팅 로직
- Zero-Question 원칙
- 에스컬레이션 기준

### `.claude/agents/` 
- 각 에이전트의 구체적 역할 및 체크리스트
- 스킬 연계 규칙

### `.claude/skills/`
- 8개 스킬의 상세 정의
- 트리거 조건 및 활용 시나리오

---

## 🚀 시작하기

### 1. 현재 상태
- ✅ **완료**: 시스템 설계 문서 작성
- ⏳ **진행 중**: 에이전트 & 스킬 구현
- ⏳ **대기 중**: CLAUDE.md 작성

### 2. 기본 사용 흐름 (완성 후)

```bash
# 1. 딜 파라미터 & 문서 준비
# 예시: 한국 에너지 PPA 딜 - 매도인 입장

# 2. Claude Code 실행
# CLAUDE.md에 딜 정보 입력하면 자동으로:
#   - DD Agent → DD 리포트 생성
#   - Contract Agent → 레드라인 & 협상 메모 생성
#   - QA Agent → 품질 검증

# 3. 산출물 확인
# /output/reports/ 와 /output/drafts/ 확인
```

### 3. 입출력 포맷

**입력 (사용자 제공)**
- 딜 파라미터 지시서 (YAML 또는 자연어)
- 대상 문서 (PDF, DOCX, TXT)
- 참조 자료 (선택사항)

**출력 (자동 생성)**
```
/output/
├── /drafts/
│   └── termsheet_[딜명]_v1.md
│   └── redline_[딜명]_v1.md
├── /reports/
│   ├── dd_report_[딜명].md
│   ├── negotiation_memo_[딜명].md
│   └── legal_opinion_[딜명].md
└── /logs/
    ├── step_dd_[딜명].json
    ├── step_contract_[딜명].json
    └── assumptions_[딜명].json
```

---

## 📊 설계 하이라이트

### 3단계 포지셔닝 (3-Position Framework)
모든 산출물은 협상 입장별 3단계 안을 제시:
- 🔴 **Aggressive**: 최대 이익 추구 (높은 리스크)
- 🟡 **Balanced**: 균형잡힌 입장 (권장)
- 🟢 **Conservative**: 리스크 최소화 (보수적)

### 자동 체이닝
```
DD 이슈 → 계약 조항 위험 자동 매핑
  └─> 협상 레드라인 자동 반영
```

### Client-Ready 품질
- QA 점수 85점 이상
- Critical Issue 0개
- 파트너 승인 후 클라이언트 직발송 가능

---

## 🔧 기술 요구사항

- **Claude Code**: 최신 버전
- **스킬**: Term Sheet, Contract Review, Due Diligence 등 (총 8개)
- **스크립트**: Python (문서 파싱, 데이터 처리)
- **참고 자료**: 섹터별 선례, 관할법 자료

---

## 📝 향후 로드맵

| Phase | 항목 | 상태 |
|-------|------|------|
| Phase 1 | 시스템 설계 문서 | ✅ 완료 |
| Phase 2 | CLAUDE.md 작성 | ⏳ 예정 |
| Phase 3 | 에이전트 & 스킬 구현 | ⏳ 예정 |
| Phase 4 | 유틸리티 스크립트 | ⏳ 예정 |
| Phase 5 | 테스트 케이스 & 검증 | ⏳ 예정 |

---

## 📞 문의 사항

더 자세한 정보는 [`legal-agent-design.md`](./legal-agent-design.md)를 참고하세요.

---

**Last Updated**: 2026-05-14  
**Status**: Design Phase (구현 준비 중)
