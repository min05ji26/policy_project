# 작업 진행 현황

## 완료된 작업

### 프로젝트 기반 세팅
- [x] React + Vite 프로젝트 초기 구성
- [x] `index.css` import 경로 오류 수정 (`src/components/` 안에 있던 파일 연결)
- [x] `App.jsx` Vite 기본 템플릿 제거 → 커스텀 페이지로 교체
- [x] JSX 파일(`src/pages/`)과 CSS 파일(`src/components/`) 간 import 경로 불일치 전체 수정
- [x] `Navbar`, `Sidebar` import 경로 오류 수정

### 페이지 구현
- [x] **홈페이지** (`Homepage.jsx`) — 히어로 섹션 + 정책 카드 그리드 + 탭 필터
- [x] **챗봇 페이지** (`ChatPage.jsx`) — AI 대화 UI + 진행 바 + 사이드바
- [x] **결과 페이지** (`ResultPage.jsx`) — 정책별 수혜 확률 + 역설 케이스 표시
- [x] **로그인 페이지** (`LoginPage.jsx`) — 카카오 로그인 버튼 + 이메일 폼
- [x] **회원가입 페이지** (`SignupPage.jsx`) — 닉네임/이메일/비밀번호 폼 + 가입 완료 화면

### 네비게이션
- [x] `App.jsx` 상태 기반 페이지 전환 (home → chat → result, login → signup)
- [x] **모든 페이지** 네비게이션 바 로고 클릭 시 홈으로 이동
- [x] 챗봇 페이지에서 홈 이동 시 진행 중 상담 있으면 확인 다이얼로그 표시
- [x] `App.jsx` import 경로 대소문자 불일치 수정 (`./pages/HomePage` → `./pages/Homepage`)

### 스타일
- [x] 반응형 디자인 적용 (모든 CSS 파일에 media query 추가)
  - 홈 정책 그리드: 3열 → 1024px 이하 2열 → 640px 이하 1열
  - 챗봇: 768px 이하 사이드바 숨김
  - 결과 페이지: 768px 이하 상단 섹션 세로 정렬
- [x] `index.css` 고정 너비(1126px) 제거 → 전체 화면 너비 사용

---

## 앞으로 해야 할 작업

### 인증
- [ ] **카카오 로그인 실제 연동** — 카카오 SDK 연결, OAuth 토큰 처리
  - 카카오 JavaScript Key 필요
  - 리다이렉트 URI 설정 필요 (카카오 디벨로퍼스)
- [ ] 로그인 상태 유지 (localStorage 토큰 저장/복원)
- [ ] 로그아웃 기능
- [ ] 마이페이지 구현

### 정책 데이터
- [ ] **공공데이터포털 정책 API 연동** — 실제 API 호출로 정책 목록 불러오기
  - API 키 환경변수 설정 (`.env`)
  - 카테고리별 필터링 (전체 / 청년 / 주거 / 취업지원 / 저소득)
- [ ] **정책 카드 hover 시 요약 툴팁 표시** — AI 또는 API 응답으로 2-3줄 요약 생성
  - 마우스 올리면 요약 표시, 벗어나면 사라짐

### 백엔드 연동
- [ ] `/chat` API 실제 연결 (현재 `http://localhost:8000/chat`)
- [ ] `/predict` API 실제 연결 (현재 `http://localhost:8000/predict`)
- [ ] `/auth/login`, `/auth/signup` API 연결 (현재 mock 처리)

### 기타
- [ ] 결과 저장 기능 (로그인 후 분석 결과 저장)
- [ ] 마이페이지에서 저장된 결과 조회
