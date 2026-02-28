# Phase 1 개발 설정 문서

> **대상 독자**: 프로젝트에 합류하는 개발자, 코드 리뷰어
> **작성일**: 2026-02-28
> **상태**: Phase 1 완료

---

## 1. 변경 요약 (Change Summary)

### 모노레포 통합
- `frontend/.git` 제거 — 단일 커밋 히스토리로 통합
- 루트 `english-inspector/` 가 단일 git 저장소

### Bun 마이그레이션
- 프론트엔드 패키지 매니저를 npm → bun으로 전환
- `frontend/bun.lock` 을 커밋 대상으로 설정
- `package-lock.json` 제거 예정

### AGENTS.md 추가
- 에이전트 협업 규칙 및 프로젝트 컨벤션 문서화
- 패키지 매니저 정책 (Python: uv, Frontend: bun) 명시
- 테스트 정책, 린트 설정 포함

### 누락 의존성 추가
- `python-jose[cryptography]` — JWT 토큰 생성/검증
- `bcrypt>=4.0.0` — 비밀번호 해싱 (passlib 대체: bcrypt 5.x 호환성 문제로 직접 사용)
- `email-validator` — Pydantic EmailStr 지원
- `greenlet` — SQLAlchemy async 필수 의존성

### Auth API 계약 수정
- 기존: `POST /api/auth/login` → `{token: string}` (user 정보 별도 요청 필요)
- 변경: `POST /api/auth/login` → `{token: string, user: {id, email, name, role}}`
- 이점: 로그인 시 단일 요청으로 토큰 + 사용자 정보 취득 (round trip 감소)
- 동일 구조: `POST /api/auth/register`도 동일 응답 형식

### Lint 도구 설정
- **Python**: ruff (line-length=100, target=py312) — `backend/pyproject.toml` 에 설정
- **TypeScript/JS**: biome 2.4.4 — `frontend/biome.json` 에 설정
  - indentStyle: space (2칸), lineWidth: 100, quoteStyle: double
  - 대상: `src/**` (CSS 파일 제외)
- **Pre-commit hook**: `.githooks/pre-commit` (git hooks 디렉토리 분리)
  - `uv run --extra dev ruff check app/` — Python lint
  - `bunx biome check src/` — TypeScript/JS lint
  - `bun run build` — Next.js 빌드 검증
  - 활성화: `git config core.hooksPath .githooks`

### 백엔드 단위 테스트 추가
- **`tests/conftest.py`**: 공통 픽스처 — 인메모리 SQLite, `AsyncClient`, `auth_headers`
- **`tests/test_auth.py`**: Auth 엔드포인트 9개 테스트
  - 회원가입 성공/중복/유효성 검사, 로그인 성공/실패, `/me` 인증 검증
- **`tests/test_exam_routes.py`**: ExamSet CRUD 12개 테스트
  - 생성/조회/삭제 인증 필수, 사용자 격리 (다른 사용자 시험지 조회 불가), 소유자 외 삭제 403
- **`tests/test_quality_filter.py`**: 품질 필터 단위 테스트 (LLM 불필요)
  - `DuplicateDetector`: Jaccard 유사도 기반 중복 감지 7개 테스트
  - `FormatValidator`: 객관식/빈칸/독해 형식 검증 9개 테스트
  - `DifficultyCalibrator`: 난이도별 문항 길이 검증 4개 테스트
  - `QualityFilter` 통합: 전체 파이프라인 6개 테스트
- 실행: `cd backend && uv run pytest -v` — **46개 전체 통과** ✅

### 프론트엔드 버그 수정
- `QuestionCard.tsx`: `showAnswer` prop 변경 시 로컬 상태 동기화 버그 수정
  - 수정 전: `useState(showAnswer)` 초기화 후 prop 변경 무시
  - 수정 후: `useEffect(() => setLocalShowAnswer(showAnswer), [showAnswer])` 추가
- `types/auth.ts`: `AuthResponse = {token, user}` — 이미 올바른 형식 확인
- `lib/auth.ts`: `saveAuth(data.token, data.user)` — 이미 올바르게 구현됨

---

## 2. 아키텍처 결정 사항 (Architecture Decisions)

### 왜 모노레포인가?
- **단일 커밋 히스토리**: 프론트/백엔드 변경을 하나의 PR로 원자적으로 추적
- **단순한 CI**: 하나의 파이프라인으로 전체 스택 빌드/테스트
- **의존성 명확성**: 타입 공유, API 계약 변경이 동일 diff에서 보임

### 왜 Bun인가?
- npm 대비 설치 속도 3-5배 빠름
- TypeScript 네이티브 지원 (별도 설정 불필요)
- Next.js 16과 완전 호환

### Auth 계약: 통합 응답
- 로그인/등록 시 `{token, user}` 를 함께 반환
- 클라이언트가 `/api/auth/me` 를 별도 호출할 필요 없음
- 로컬스토리지에 token + user 정보를 동시에 저장

### 테스트 전략: Mock LLM 우선
- LLM API 키 없이도 파이프라인 구조 검증 가능
- 결정론적 테스트: mock 응답으로 재현 가능한 테스트 케이스
- Phase 2에서 실제 API 통합 테스트로 확장 예정

### Lint 전략
- **Python**: ruff — flake8/isort/pyupgrade를 단일 도구로 통합, 속도 빠름
- **TypeScript**: biome (또는 eslint-config-next) — 일관된 코드 스타일 강제
- **Pre-commit hooks**: 커밋 전 자동 lint, 깨진 코드가 저장소에 진입하지 않도록

---

## 3. 현재 상태 (Current State)

### 작동하는 기능
| 기능 | 상태 | 비고 |
|------|------|------|
| 사용자 인증 (회원가입/로그인) | ✅ 완료 | JWT + bcrypt |
| 시험지 CRUD | ✅ 완료 | 생성/조회/삭제 |
| 문항 생성 API | ✅ 완료 | DSPy 파이프라인 구조 |
| 품질 필터 | ✅ 완료 | DuplicateDetector, FormatValidator, DifficultyCalibrator |
| PDF 내보내기 | ✅ 완료 | jspdf + jspdf-autotable |
| 프론트엔드 빌드 | ✅ 통과 | TypeScript 오류 없음 |

### 미완료 항목
- **LLM 통합 테스트**: API 키 설정 후 실제 GPT-5.2 / Claude 4.6 연동 테스트 필요
- **MIPROv2 최적화**: 프롬프트 자동 최적화 파이프라인 미실행 상태
- **E2E 테스트**: Playwright 기반 전체 사용자 흐름 테스트 미설정

### 알려진 제한사항
- **Rate limiting 없음**: API 요청 횟수 제한 미구현
- **이메일 인증 없음**: 회원가입 시 이메일 확인 절차 없음
- **비밀번호 재설정 없음**: `/api/auth/reset-password` 미구현
- **CORS**: `localhost:3000` 만 허용 (프로덕션 배포 시 수정 필요)

---

## 4. 다음 단계 제안 (Next Steps)

### Phase 2: LLM 파이프라인 통합 테스트
1. `.env` 에 API 키 설정:
   ```
   OPENAI_API_KEY=...
   ANTHROPIC_API_KEY=...
   GEMINI_API_KEY=...
   ```
2. `backend/app/services/generator.py` 실 LLM 호출 테스트
3. Best-of-N 샘플링 (N=3) 품질 비교
4. DSPy 파이프라인 로깅/모니터링 설정

### Phase 3: E2E 테스트 (Playwright)
1. `frontend/` 에 Playwright 설정
2. 인증 플로우 (회원가입 → 로그인 → 시험지 생성) E2E 테스트
3. CI 파이프라인에 E2E 테스트 통합

### Phase 4: 성능 최적화 & 배포
1. Rate limiting 추가 (FastAPI `slowapi`)
2. 백엔드 Docker 이미지 빌드
3. 프론트엔드 Vercel/Netlify 배포
4. 프로덕션 CORS 설정 업데이트

---

## 5. 학습 포인트 (Learning Points)

### DSPy 3.x 파이프라인 구조

```python
# backend/app/services/dspy_modules.py
import dspy

class QuestionGenerator(dspy.Module):
    def __init__(self):
        self.generate = dspy.ChainOfThought("context, grade_level, topic -> question, choices, answer, explanation")

    def forward(self, **kwargs):
        return self.generate(**kwargs)
```

- **dspy.ChainOfThought**: LLM에게 단계별 추론 유도
- **dspy.context(lm=...)**: 특정 호출에만 다른 모델 사용
- **MIPROv2**: 프롬프트 자동 최적화 옵티마이저
- 패키지명: `dspy` (구버전 `dspy-ai` 아님)
- LiteLLM 내장 — 별도 import 불필요

### FastAPI Async 패턴

```python
# 비동기 DB 세션 사용
async def get_item(id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Item).where(Item.id == id))
    return result.scalar_one_or_none()
```

- `AsyncSession` + `aiosqlite` 조합으로 비동기 SQLite
- `Depends(get_db)` 패턴으로 세션 주입
- `lifespan` 컨텍스트 매니저로 앱 시작/종료 이벤트 처리

### Next.js 16 App Router 구조

```
frontend/src/app/
├── page.tsx          # 홈 (문항 생성)
├── exams/
│   └── page.tsx      # 시험지 목록
└── layout.tsx        # 공통 레이아웃
```

- `"use client"` 디렉티브: 클라이언트 컴포넌트 명시
- `useEffect`로 localStorage 접근 (SSR 안전 처리)
- `typeof window === "undefined"` 가드로 SSR/CSR 분기

### shadcn/ui 컴포넌트 패턴

```typescript
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
```

- Radix UI 기반 접근성 보장 컴포넌트
- Tailwind CSS 클래스로 스타일 오버라이드
- `variant` prop으로 스타일 변형: `"outline"`, `"secondary"`, `"ghost"` 등

---

## 6. 개발 환경 설정 (Dev Setup)

### 백엔드 실행
```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

### 프론트엔드 실행
```bash
cd frontend
bun install
bun run dev  # http://localhost:3000
```

### 환경 변수
```bash
# backend/.env
DATABASE_URL=sqlite+aiosqlite:///./english_inspector.db
SECRET_KEY=your-secret-key-here
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=...
```

### 테스트 실행
```bash
cd backend
uv run pytest -v
```
