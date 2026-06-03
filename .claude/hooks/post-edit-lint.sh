#!/bin/bash
# PostToolUse Hook: Python 린트/포맷 자동 실행
# Claude가 Edit/Write로 파일 수정 시 자동 실행 (jq 방식 - 공식 문서 권장)

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

# 파일 경로 없으면 종료
[ -z "$FILE_PATH" ] && exit 0

# 파일 존재 여부 확인
[ ! -f "$FILE_PATH" ] && exit 0

# Python 파일만 처리
case "$FILE_PATH" in
  *.py) ;;
  *) exit 0 ;;
esac

# ruff: 린트 + 자동 수정 (있으면 실행, 없으면 건너뜀)
if command -v ruff >/dev/null 2>&1; then
  ruff check --fix --quiet "$FILE_PATH" 2>/dev/null || true
  ruff format --quiet "$FILE_PATH" 2>/dev/null || true
elif command -v black >/dev/null 2>&1; then
  # ruff 없으면 black으로 폴백
  black --quiet "$FILE_PATH" 2>/dev/null || true
fi
