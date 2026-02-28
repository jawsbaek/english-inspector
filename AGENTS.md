# AGENTS.md — English Inspector

## Project Overview

영어 시험지 자동 생성 및 검수 시스템. DSPy 3.x 기반 멀티모델 파이프라인으로 문제를 생성하고 검증한다.

## Tech Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| Runtime | Python | 3.12 |
| Backend Framework | FastAPI | >=0.115 |
| ASGI Server | Uvicorn | >=0.34 |
| ORM | SQLAlchemy (async) | >=2.0 |
| DB | SQLite (aiosqlite) | >=0.20 |
| AI Pipeline | DSPy | >=3.1 |
| Frontend Framework | Next.js | 16 |
| Language | TypeScript | 5.x (strict mode) |
| UI | Tailwind CSS 4 + shadcn/ui | latest |
| React | React | 19 |

## Package Managers

### Python — uv

- `uv`를 사용한다. pip, poetry, conda 사용 금지.
- 의존성 추가: `uv add <package>`
- 개발 의존성: `uv add --dev <package>`
- Lock file: `backend/uv.lock` (커밋 대상)
- 가상환경: `uv sync` 후 `.venv/` 자동 생성

### Frontend — bun

- `bun`을 패키지 매니저로 사용한다. npm, yarn, pnpm 사용 금지.
- 의존성 추가: `bun add <package>`
- 개발 의존성: `bun add -d <package>`
- 스크립트 실행: `bun run dev`, `bun run build`, `bun run lint`
- Lock file: `bun.lockb` (커밋 대상, 기존 `package-lock.json`은 제거 예정)

## Python 3.12

- 최소 요구 버전: Python 3.12
- 3.12+ 문법 적극 사용: `type` 문, `match` 문, f-string 개선, `typing` 내장 제네릭
- `from __future__ import annotations` 불필요 (3.12 네이티브 지원)
- Ruff target: `py312`

## TypeScript

- `strict: true` 모드 필수
- `any` 타입 사용 금지 — `unknown`으로 대체 후 타입 가드 적용
- 경로 alias: `@/*` → `./src/*`
- React 19 + Next.js 16 App Router 기반
- 컴포넌트: 함수형 컴포넌트 + React hooks만 사용

## FastAPI

- 비동기 핸들러 (`async def`) 기본 사용
- Pydantic v2 모델로 request/response 스키마 정의
- 라우터 분리: `backend/app/api/` 디렉토리 내 도메인별 라우터
- 설정 관리: `pydantic-settings` + `.env` 파일
- CORS, 에러 핸들러 등 미들웨어는 `backend/app/main.py`에서 설정

## Directory Structure

```
english-inspector/
├── backend/
│   ├── app/
│   │   ├── api/          # FastAPI 라우터
│   │   ├── core/         # 설정, 상수
│   │   ├── models/       # SQLAlchemy 모델
│   │   ├── schemas/      # Pydantic 스키마
│   │   ├── services/     # 비즈니스 로직 (DSPy 모듈 포함)
│   │   └── main.py       # FastAPI 앱 엔트리
│   ├── tests/            # pytest 테스트
│   ├── pyproject.toml
│   └── uv.lock
├── frontend/
│   ├── src/
│   │   ├── app/          # Next.js App Router 페이지
│   │   └── components/   # React 컴포넌트
│   ├── package.json
│   └── tsconfig.json
└── AGENTS.md
```

## Test Policy (테스트 정책)

### Backend (pytest)

- 테스트 프레임워크: `pytest` + `pytest-asyncio`
- 테스트 위치: `backend/tests/` 디렉토리
- 파일 네이밍: `test_<module>.py`
- 실행 명령: `cd backend && uv run pytest`
- 비동기 테스트: `@pytest.mark.asyncio` 데코레이터 사용
- 커버리지: 핵심 서비스 로직(services/) 우선 커버
- API 테스트: `httpx.AsyncClient` + FastAPI `TestClient` 사용
- 픽스처: `conftest.py`에 공통 픽스처 정의

### Frontend (추후 설정)

- 프레임워크: Vitest + React Testing Library (도입 예정)
- 실행 명령: `cd frontend && bun run test`
- 컴포넌트 테스트 중심, E2E는 Playwright 고려

### 공통 원칙

- PR 전 테스트 통과 필수
- 새 기능 추가 시 테스트 동반 작성
- DSPy 모듈 테스트: mock LM으로 파이프라인 검증
- CI에서 `pytest` + `lint`(ruff, eslint) 자동 실행

## Lint & Format

- Python: `ruff` (line-length=100, target=py312)
- TypeScript: `eslint` (eslint-config-next)
- 커밋 전 lint 통과 필수
