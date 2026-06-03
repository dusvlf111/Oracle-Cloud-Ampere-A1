---
name: skill-creator
description: 새 스킬을 생성하거나 기존 스킬을 개선합니다. 사용자가 "스킬 만들어줘", "skill 생성", "이 패턴을 스킬로", "트리거 설명 개선" 등을 요청할 때 사용합니다. 본 프로젝트(Oracle-Cloud-Ampere-A1)는 새 도메인 패턴이 안정화되면 즉시 스킬로 추출하는 정책.
---

# Skill Creator

스킬을 만들거나 개선하기 위한 가이드. 본 프로젝트에서는 **도메인 패턴이 2회 이상 반복되면 스킬화**가 기본 정책.

---

## 1. 스킬 = 단일 SKILL.md (+ 선택적 참조 자료)

```
.claude/skills/{name}/
├── SKILL.md            (필수)
├── references/         (선택) — 상세 문서, 길면 분리
└── assets/             (선택) — 템플릿, 스니펫
```

### 프로그레시브 로딩
1. **frontmatter** (name + description) — 항상 컨텍스트 (~100단어)
2. **SKILL.md 본문** — 트리거 시 로딩 (~500줄 이하 권장)
3. **references/assets** — 필요할 때만 명시적 Read

---

## 2. SKILL.md 작성

### Frontmatter

```yaml
---
name: skill-name                 # kebab-case
description: |
  무엇을 하는지 + 언제 트리거되는지.
  사용자 표현 예시 (한국어) 다양하게 포함.
  본 프로젝트 맥락 명시 (해당 시).
disable-model-invocation: false  # 옵션: 모델 자동 호출 금지
allowed-tools: Read, Write, Edit  # 옵션: 허용 도구 제한
argument-hint: "[arg]"            # 옵션: /skill arg
---
```

**description 작성 팁** (트리거 정확도 향상):
- "이 스킬을 사용하세요" 같이 약간 push 톤
- 사용자가 쓸 법한 표현 다양하게 (한국어/영어 모두)
- 트리거 컨텍스트 명시 ("FastAPI 엔드포인트 추가", "FSD slice 생성" 등)

### 본문 구조

```markdown
# {스킬 제목}

한 줄 요약 — 이 스킬이 정확히 무엇을 하는지.

## 언제 사용

- 트리거 조건 1
- 트리거 조건 2

## 핵심 원칙

(이 도메인의 의사결정 기준)

## 패턴 / 절차

(구체적 단계 또는 코드 패턴)

## 안티패턴

(피해야 할 것 + 이유)

## 참조

- @references/foo.md (긴 코드 예시)
```

---

## 3. 본 프로젝트 스킬 카탈로그 (참고)

| 스킬 | 트리거 |
|---|---|
| `fsd-architecture` | FSD slice 생성, 레이어 위치 결정 |
| `fastapi-patterns` | FastAPI 라우터/SQLModel/Alembic |
| `python-testing` | pytest 테스트 작성 |
| `web-testing` | vitest + RTL + MSW |
| `oss-selection` | 라이브러리 도입 판단 |
| `oci-sdk` | OCI Python SDK 호출 |
| `notification-channels` | Discord/Slack/Telegram/ntfy 발송 |
| `task-maker`, `task-runner`, `task-cleaner` | 작업 관리 |

---

## 4. 작성 절차

1. **의도 파악**: 무엇을 하는 스킬? 언제 트리거? 출력 형식? — 불명확하면 질문
2. **기존 패턴 확인**: 이미 비슷한 스킬이 있는지 `ls .claude/skills/` 확인 (있으면 개선)
3. **초안 작성**: 위 frontmatter + 본문 템플릿
4. **참조 분리**: 코드 예시가 100줄 넘으면 `references/{topic}.md` 로 빼고 `@references/...` 로 링크
5. **트리거 표현 풍부화**: 사용자가 다양한 방식으로 부를 수 있도록 description 보강
6. **동작 확인**: 다음 작업 때 자동 트리거되는지 확인, 안 되면 description 수정

---

## 5. 좋은 스킬 vs 나쁜 스킬

| 좋은 | 나쁜 |
|---|---|
| 단일 도메인/패턴에 집중 | 여러 무관 주제 묶음 |
| 의사결정 기준 명확 | "이렇게 하세요" 만 나열 |
| 안티패턴 + 이유 포함 | 예시만 줄줄이 |
| 트리거 표현 다양 | 영어 한 줄만 |
| 500줄 이하, references 분리 | 단일 파일 1000줄+ |

---

## 6. 본 프로젝트 정책

- **반복 감지 즉시 스킬화**: 같은 의사결정/패턴이 2번 등장하면 스킬 후보
- **에이전트 참조**: 작성한 스킬은 `agents/server-worker.md` 또는 `web-worker.md` 의 `skills:` 항목에 추가
- **카탈로그 동기화**: 새 스킬 만들면 본 SKILL.md 의 §3 카탈로그 표 업데이트
- **삭제 결정**: 30일 이상 트리거 안 되거나 PRD 에서 의미가 사라지면 제거 후보
