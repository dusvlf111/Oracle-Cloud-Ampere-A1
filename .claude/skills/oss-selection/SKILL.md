---
name: oss-selection
description: |
  새 오픈소스 라이브러리/패키지 도입 판단. "X 라이브러리 써도 돼?", "이거 npm/pip로 가져올까?", "Y 직접 짤까 OSS 쓸까", "라이브러리 추천", "deps 추가" 등에서 트리거.
  본 프로젝트는 self-host 전용이라 GPL/AGPL 포함 모든 라이선스 허용. 자체 구현보다 검증된 OSS 우선.
---

# OSS Selection — 라이브러리 도입 판단

자체 구현 전에 **검증된 OSS 가 있는지 먼저 확인**이 본 프로젝트 기본 동작.

## 핵심 원칙

1. **재발명 금지** — 비슷한 기능이 mainstream 으로 존재하면 그것을 먼저 평가
2. **활성 유지보수 우선** — 최근 6개월 내 커밋 없는 패키지는 위험 신호
3. **번들 크기 / 의존성 깊이 고려** (웹) — 큰 dep 트리는 빌드 시간 + 보안 부담
4. **ARM64 호환 확인** — Oracle Cloud A1 은 aarch64. native binding 있으면 휠 존재 여부 확인

## 도입 체크리스트

도입 전 다음 모두 통과해야 함:

- [ ] **활성도**: 최근 6개월 내 커밋, 또는 안정화돼서 변경 없음이 자연스러운가
- [ ] **인기**: Python 월 100k+ 다운로드 또는 npm 주 50k+ 또는 GitHub 5k★+ (도메인 작으면 완화)
- [ ] **라이선스**: 본 프로젝트는 모두 OK (기록만)
- [ ] **CVE 이력**: `pip-audit` / `npm audit` / Snyk 검색 — Critical/High 없음
- [ ] **유지보수자**: 1명 의존 OK 하지만 bus factor 낮으면 fork 가능성 고려
- [ ] **ARM64 휠 존재** (네이티브 의존성 있는 경우): PyPI `*-aarch64-*.whl` 또는 sdist 빌드 가능
- [ ] **타입 정의** (TS): `@types/*` 또는 자체 `.d.ts` 존재
- [ ] **대안과 비교**: 후보 2~3개 비교표 (기능/번들/유지보수/문서)

## 자동 분석 명령

```bash
# Python
pip index versions {pkg}                          # 사용 가능한 버전
python -c "import {pkg}; print({pkg}.__version__)" # 설치 확인
pip-audit                                          # 보안 검사

# npm (pnpm)
pnpm view {pkg}                                    # 메타데이터
pnpm view {pkg} dist-tags                          # 안정/베타
npm audit --audit-level=high                       # 보안 검사
pnpm why {pkg}                                     # 누가 의존하는지

# GitHub 활성도
gh repo view {owner}/{repo} --json updatedAt,pushedAt,stargazerCount,openIssuesCount
```

## 도입 후 기록

- `README.md` 의 "OSS Dependencies" 표에 추가:
  | 패키지 | 버전 | 라이선스 | 용도 | 대안 |
- PR description 에 "왜 이걸 선택했는가" 한 줄
- `package.json` / `pyproject.toml` 에서 핀 (정확 버전 또는 마이너 핀 `~`)

## PRD §4 핵심 OSS 매트릭스 우선

PRD §4 "핵심 OSS 매트릭스" 에 이미 채택된 라이브러리 있음. 같은 영역의 신규 도입은 그 표를 먼저 확인.

## 안티패턴

- 별 1k 미만 + 마지막 커밋 2년 전 → 위험
- 비슷한 기능 라이브러리 2개 동시 사용 (예: dayjs + date-fns) → 하나로 통일
- 거대한 의존성 (예: lodash 통째 import) → 필요한 함수만 직접 / es-toolkit 같은 경량 대안 검토
- 베타/RC 버전을 프로덕션에 사용 (의도가 명확하지 않으면)

## 신규 라이브러리 도입 절차

1. 후보 검색 (awesome-* 리포지토리, 인기 키워드)
2. 후보 2~3개 비교 (위 체크리스트 적용)
3. 사용자에 추천 + 근거 1~2줄 (대안 X 이유 포함)
4. 승인 후 추가, README "OSS Dependencies" 업데이트
