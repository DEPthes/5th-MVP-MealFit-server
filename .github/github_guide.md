# 🤝 GitHub 협업 가이드

## 📌 브랜치 전략

기능 구현 전 반드시 이슈를 생성한 후 브랜치를 생성합니다.

### 브랜치 이름 규칙

```text
feature/기능명
fix/기능명
refactor/기능명
```

### 예시

```text
feature/login-api
feature/user-signup
feature/restaurant-api

fix/jwt-error
fix/login-error

refactor/user-service
```

---

## 📌 협업 순서

1. Issue 생성
2. 브랜치 생성
3. 기능 구현
4. Commit & Push
5. Pull Request 생성
6. Code Review
7. Approve
8. Merge
9. Issue 종료(Closed)

---

## 📌 Commit Convention

| Type | 설명 |
|------|------|
| feat | 새로운 기능 추가 |
| fix | 버그 수정 |
| refactor | 코드 리팩토링 |
| docs | 문서 수정 |
| test | 테스트 코드 |
| chore | 설정 및 기타 작업 |

### 예시

```text
feat: 회원가입 API 구현
fix: JWT 인증 오류 수정
refactor: UserService 리팩토링
docs: README 수정
```

---

## 📌 Issue 작성 규칙

- 기능 구현 시 **Feature Issue**를 생성합니다.
- 버그 수정 시 **Bug Issue**를 생성합니다.
- 담당자를 지정합니다.
- 작업 완료 후 PR과 연결합니다.

---

## 📌 Pull Request 작성 규칙

PR 생성 시 다음 내용을 작성합니다.

- 작업 내용
- 변경 사항
- 관련 이슈 (`Close #번호`)
- 테스트 결과
- 체크리스트

---

## 📌 Merge 규칙

- 최소 1명 이상의 코드 리뷰(Approve) 후 Merge합니다.
- Merge 후 브랜치는 삭제(Delete Branch)합니다.
- 관련 Issue는 `Close #번호`를 통해 자동 종료합니다.

---

## 📌 기타 규칙

- `develop` 브랜치에 직접 Commit 하지 않습니다.
- `main` 브랜치에 직접 Push 하지 않습니다.
- 모든 기능은 Issue 생성 후 작업합니다.
- 코드 리뷰 의견은 반영 후 다시 Push합니다.