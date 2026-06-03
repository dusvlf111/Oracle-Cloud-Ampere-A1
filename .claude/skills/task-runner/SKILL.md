---
name: task-runner
description: "todo/ 폴더의 task 파일을 읽고 에이전트에 위임하여 자동 실행합니다. 사용자가 '작업 실행', '태스크 실행', '다음 작업', '작업 계속', '이어서 진행' 등을 요청할 때 사용합니다."
argument-hint: "[task-file-path]"
disable-model-invocation: true
allowed-tools: Read, Write, Bash, Glob, Task
---

# Task Runner — 오케스트레이터

`todo/` 의 task 파일을 읽고 `task-executor` 에이전트에 실행을 위임합니다.
실제 코드 작성/테스트/커밋은 task-executor가 담당합니다.

---

## 시작 절차

```bash
# 1. sentinel 파일 생성 (Stop 훅이 이걸 보고 중단 방지)
touch .claude/.task-running

# 2. done/ 디렉토리 확인
mkdir -p done
```

파일이 지정되지 않은 경우 `todo/` 의 `tasks-*.md` 목록을 보여주고 선택 요청
(이 경우에만 사용자에게 질문 허용 — 이후는 완전 자율)

---

## 단일 에이전트 실행

작업이 순차적이거나 단순할 때 (Python 자동화 스크립트의 일반적 경우):

```
task-executor 에이전트에 직접 위임
```

---

## 에이전트 위임 방법

### task-executor 위임 템플릿

```
task-executor 에이전트를 사용하여 다음 task 파일을 실행하세요:

파일: todo/tasks-[name]-push[N].md
내용: [파일 전체 내용]

지시사항:
- 모든 미완료([ ]) 작업을 순서대로 실행
- 각 하위 작업 완료 시 즉시 커밋
- 완료된 항목은 [x] 로 체크
- 오류 시 T3 수정 작업 추가 후 자동 해결
- git push 금지 (사용자에게 보고 후 대기)

참조 문서:
- `.claude/behavioral.md` — 행동 가이드라인
- `.claude/tasks/` — PRD 및 task 파일 (있는 경우)
```

---

## Push 파일 완료 처리

모든 항목이 [x] 된 후:

```bash
# 파일을 done/ 으로 이동
mv todo/tasks-[name]-pushN.md done/

# 결과보고서 생성 (done/result-[name]-pushN.md)
```

결과보고서 형식:
```markdown
# 결과보고서: [파일명]

> 완료일: [날짜]
> Push 범위: [기능 요약]

## 구현 요약

| 작업 | 상태 | 커밋 |
|---|---|---|
| 1.1 [작업명] | ✅ | `해시` |

## 생성/수정 파일

- `src/...` - [변경 내용]

## 테스트 결과

- 통과: N개 (pytest)

## 이슈 및 특이사항

- [발생한 오류 및 해결법]
```

---

## 종료 처리

```bash
# 모든 Push 완료 시 sentinel 삭제
rm -f .claude/.task-running
```

이후 Stop 훅이 중단을 허용하고, 최종 보고 후 종료.
