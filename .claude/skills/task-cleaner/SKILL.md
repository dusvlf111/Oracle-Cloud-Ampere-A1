---
name: task-cleaner
description: "완료된 task 파일과 관련 자료(PRD, 스크린샷 등)를 브랜치명 또는 기능명 폴더로 정리하여 done/에 아카이브합니다. 사용자가 'task 정리', '작업 정리', '태스크 정리', '파일 정리해줘', 'clean tasks' 등을 요청할 때 사용합니다."
argument-hint: "[branch-name or feature-name]"
disable-model-invocation: true
user-invocable: true
---

# Task Cleaner — 작업 파일 정리

완료된 task 파일, PRD, 스크린샷 등을 `done/` 하위의 **브랜치명 또는 기능명 폴더**로 정리합니다.

---

## 폴더 구조

```
.claude/tasks/
├── todo/                          ← 진행 중인 task 파일
├── done/                          ← 완료된 작업 아카이브
│   ├── {브랜치명 또는 기능명}/      ← 기능 단위 폴더
│   │   ├── prd.md
│   │   ├── tasks-push1.md
│   │   ├── result-push1.md
│   │   ├── screenshot1.png
│   │   └── fix-notes.md
│   └── {다른 기능}/
└── (루트에는 현재 진행 중인 파일만)
```

---

## 정리 프로세스

### 1. 폴더 이름 결정

우선순위:
1. **사용자가 인자로 지정한 이름** → 그대로 사용
2. **현재 Git 브랜치명** → `git branch --show-current`
   - 브랜치명에서 티켓 번호 prefix 제거 가능
   - 단, 사용자에게 확인 후 결정
3. **task/PRD 파일명에서 추출** → `prd-foo.md` → `foo`

### 2. 정리 대상 파일 식별

```bash
# tasks/ 루트에 있는 파일들 (디렉토리 제외)
ls -1 .claude/tasks/*.{md,png,jpg,csv,pdf} 2>/dev/null

# todo/ 안의 완료된 파일들 (모든 체크박스가 [x])
ls -1 .claude/tasks/todo/*.md 2>/dev/null
```

#### 정리 대상 판단 기준

| 파일 종류 | 정리 조건 |
|-----------|-----------|
| `tasks-*.md` (todo/) | 모든 체크박스가 `[x]`인 경우 |
| `prd*.md` | 관련 task 파일이 모두 완료된 경우 |
| `fix*.md` | 관련 작업이 완료된 경우 |
| `*.png`, `*.jpg` | 관련 task/PRD와 함께 이동 |
| `*.csv`, `*.pdf` | 관련 task/PRD와 함께 이동 |
| `result-*.md` | 이미 완료된 결과보고서 |

### 3. 파일 이동

```bash
mkdir -p .claude/tasks/done/{폴더명}
mv .claude/tasks/{대상파일} .claude/tasks/done/{폴더명}/
mv .claude/tasks/todo/{완료파일} .claude/tasks/done/{폴더명}/
```

### 4. 정리 보고

```
✅ 정리 완료: done/{폴더명}/

이동된 파일:
- prd.md
- fix-notes.md
- 스크린샷 3장
- tasks-push1.md (완료)
```

---

## 규칙

- `todo/`에 미완료 task(`[ ]`가 남은 파일)는 **이동하지 않음**
- `done/` 내 기존 폴더와 이름 충돌 시 사용자에게 확인
- 루트의 `todo/`, `done/` 디렉토리 자체는 삭제하지 않음
- PRD와 관련 스크린샷은 같은 폴더에 함께 이동
- `done/` 하위 폴더에 이미 같은 이름의 파일이 있으면 덮어쓰지 않고 사용자에게 확인
- 정리 후 `tasks/` 루트와 `todo/`가 비어있는지 확인하여 깔끔한 상태 유지
