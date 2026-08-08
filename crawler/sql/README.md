# 테스트 데이터로 API 확인하기

크롤링 → 정규화 → 식약처 매칭 → LLM 매칭 → 태깅이 **모두 끝난 상태의 데이터**를 SQL로 떠 뒀습니다.
이 폴더의 파일 두 개만 넣으면 **Playwright·Ollama·Gemini·식약처 xlsx 없이** API를 테스트할 수 있습니다.

| 파일 | 역할 |
|---|---|
| `schema_additions.sql` | 서버가 모르는(=Hibernate가 안 만드는) 컬럼·인덱스 |
| `seed_test_data.sql` | 정제 완료 데이터 (약 700KB) |

---

## 1. 준비

```bash
mysql -u root -p -e "CREATE DATABASE mealfit_test CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
```

**서버를 한 번 실행**해 테이블을 만듭니다 (`ddl-auto=update`가 엔티티 기준으로 생성). 뜬 것을 확인했으면 종료합니다.

```bash
./gradlew bootRun
```

그다음 두 파일을 순서대로 넣습니다. **순서가 중요합니다** — `schema_additions.sql`이 먼저입니다.

```bash
mysql -u root -p mealfit_test < crawler/sql/schema_additions.sql
```

```bash
mysql -u root -p mealfit_test < crawler/sql/seed_test_data.sql
```

### 적재 확인

```bash
mysql -u root -p mealfit_test -e "SELECT (SELECT COUNT(*) FROM restaurant) AS 식당, (SELECT COUNT(*) FROM menu) AS 메뉴, (SELECT COUNT(*) FROM menu WHERE nutrition_calories IS NOT NULL) AS 영양있음, (SELECT COUNT(*) FROM restaurant WHERE distance_to_main_gate IS NOT NULL) AS 거리있음;"
```

기대값 — **식당 97 / 메뉴 1006 / 영양있음 168 / 거리있음 97**

---

## 2. 데이터에 무엇이 들어 있나

명지대학교 인문캠퍼스 주변 식당입니다.

| 구분 | 수량 |
|---|---|
| 식당 | 97곳 (한식 35 · 카페디저트 32 · 양식 14 · 중식 8 · 일식 8) |
| 메뉴 | 1,006개 (가격 있음 994개) |
| 영양정보 있는 메뉴 | 168개 — 식약처 매칭 성공분. **매칭률 계산 대상** |
| 음식종류 태그 | 818개 (MEAT 202 · NOODLE 120 · SEAFOOD 112 · FRIED 87 …) |
| 거리 | 정문 64m ~ 1,457m |

포함하지 않은 것:
- **회원·인바디 등 개인정보 일체** — 회원가입은 직접 하셔야 합니다
- 좌표를 못 구한 식당 5곳 — 거리를 계산할 수 없어 제외

---

## 3. 테스트 준비 — 회원 만들기

대부분의 API가 JWT를 요구합니다.

```bash
curl -X POST http://localhost:8080/api/members/signup -H "Content-Type: application/json" -d '{"email":"test@test.com","password":"test1234!","nickname":"테스터"}'
```

```bash
curl -X POST http://localhost:8080/api/members/login -H "Content-Type: application/json" -d '{"email":"test@test.com","password":"test1234!"}'
```

응답의 토큰을 이후 요청에 `Authorization: Bearer <토큰>`으로 넣습니다.

> **매칭률(`matchRate`)을 보려면** `POST /api/targets`로 목표 영양치를 먼저 설정해야 합니다.
> 설정 안 하면 `matchRate`가 `null`로 내려오는데, **이것도 정상 동작**입니다 (목표 미설정 회원도 검색은 되어야 함).

---

## 4. 추천 API — 기대값

`GET /api/recommendations`. 아래 숫자는 이 seed 데이터 기준 **실측값**입니다.

> 추천 API는 **카페·디저트(CAFE_DESSERT) 32곳을 제외**합니다. 여기에 메뉴가 하나도 없는 일식당 1곳이 더 빠져(메뉴 기준 조회라 카드가 만들어지지 않음), 전체 97곳 중 **64곳**이 대상입니다.

### 기본 (검색어 없음 = 홈 화면)

| 확인 항목 | 기대값 |
|---|---|
| `totalElements` | **64** (식당 카드 수) |
| 대상 메뉴 총합 | 688개 |

### 검색어별 — `?keyword=`

| 검색어 | 식당 카드 | 메뉴 |
|---|---|---|
| `치킨` | 11곳 | 81개 |
| `피자` | 7곳 | 40개 |
| `짜장` | 4곳 | 16개 |
| `샐러드` | 3곳 | 13개 |
| `돈까스` | 3곳 | 3개 |
| `국밥` | 3곳 | 17개 |
| `라면` | 2곳 | 4개 |

### 음식 종류 — `?cuisine=`

| 값 | 식당 |
|---|---|
| `KOREAN` | 35곳 |
| `WESTERN` | 14곳 |
| `CHINESE` | 8곳 |
| `JAPANESE` | 7곳 |

### 세부 종류 칩 — `?foodType=`

| 값 | 식당 | 메뉴 |
|---|---|---|
| `MEAT` | 46곳 | 202개 |
| `NOODLE` | 32곳 | 120개 |
| `SOUP` | 26곳 | 66개 |
| `RICE` | 25곳 | 69개 |
| `FRIED` | 21곳 | 87개 |
| `SALAD` | 13곳 | 26개 |
| `PIZZA` | 6곳 | 27개 |

### 가격대 — `?maxPrice=`

| 값 | 메뉴 |
|---|---|
| `10000` | 176개 |
| `15000` | 338개 |
| `20000` | 448개 |

### 거리 — `?referencePoint=`

가장 가까운 5곳입니다. 도보 시간은 분당 75m 기준입니다.

| 식당 | 정문 기준 | 후문 기준 |
|---|---|---|
| 동대문엽기떡볶이 명지대점 | 64m (1분) | 143m (2분) |
| 투썸플레이스 명지대점 | 78m (1분) | 133m (2분) |
| 60계치킨 서울명지대점 | 92m (1분) | 193m (3분) |
| 샹츠마라 명지대점 | 102m (1분) | 114m (2분) |
| 써브웨이 명지대점 | 107m (1분) | 298m (4분) |

`referencePoint`를 `MAIN_GATE`(기본) ↔ `BACK_GATE`로 바꾸면 **거리와 정렬 순서가 함께 바뀌어야** 합니다.
샹츠마라가 좋은 확인 지점입니다 — 정문 기준으로는 이 5곳 중 4번째(102m)지만, **후문 기준으로는 114m로 가장 가까워집니다.**
순서가 그대로면 `referencePoint` 파라미터가 먹지 않는 것입니다.

### 예시 요청

```bash
curl -H "Authorization: Bearer <토큰>" "http://localhost:8080/api/recommendations?keyword=치킨&size=5"
```

```bash
curl -H "Authorization: Bearer <토큰>" "http://localhost:8080/api/recommendations?foodType=PIZZA&maxPrice=20000&referencePoint=BACK_GATE"
```

---

## 5. 식당 검색 API — 기대값

`GET /api/restaurants`. 이쪽은 카페·디저트를 **제외하지 않습니다.**

| 검색어 | 기대값 | 비고 |
|---|---|---|
| `치킨` | **11곳** | 상호에 '치킨'이 든 곳은 4곳뿐. **나머지 7곳은 메뉴명으로 걸린 것** |
| `명지대` | 18곳 | 전부 상호 매칭 |

`치킨`의 11곳 vs 4곳 차이가 **메뉴명 매칭 기능이 동작하는지 보여주는 지점**입니다. 4곳만 나온다면 메뉴명 `EXISTS` 조건이 빠진 것입니다.

```bash
curl -H "Authorization: Bearer <토큰>" "http://localhost:8080/api/restaurants?keyword=치킨"
```

---

## 6. 영양 데이터 확인 포인트

영양정보는 **1,006개 중 168개**에만 있습니다. 나머지는 식약처 DB에서 짝을 못 찾은 메뉴입니다.

- 영양정보 없는 메뉴는 `matchRate`가 `null`이어야 하고, **500 에러가 나면 안 됩니다**
- 신뢰도 0.85 이상인 메뉴는 124개 — 대표식품명 검색이 이 기준으로 걸러집니다
- `nutrition_source`는 `OFFICIAL`(식약처) / `ESTIMATED`(AI 추정) 두 가지

샘플 (열량 상위):

| 메뉴 | 가격 | 열량 | 단백질 | 나트륨 | 신뢰도 |
|---|---|---|---|---|---|
| 크림치즈꽈배기 | 5,900원 | 350kcal | 4.19g | 432mg | 1.000 |
| 껍데기 200g | 11,000원 | 348kcal | 23.74g | 475mg | 0.800 |
| 양갈비구이 | 62,000원 | 330kcal | 20.03g | 459mg | 0.950 |

---

## 7. 데이터 되돌리기

테스트로 데이터가 망가졌으면 seed만 다시 넣으면 됩니다 (`INSERT IGNORE`라 중복 실행이 안전합니다).
완전히 초기화하려면:

```bash
mysql -u root -p -e "DROP DATABASE mealfit_test;" && mysql -u root -p -e "CREATE DATABASE mealfit_test CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
```

---

## 8. 실제 파이프라인을 돌려보고 싶다면

위 과정은 **결과 데이터를 넣는 것**입니다. 파이프라인 자체를 실행하려면 크롤러 README를 참고하세요.
Playwright(브라우저), 카카오 지오코딩 키, Ollama 또는 Gemini 키, 식약처 영양정보 xlsx가 추가로 필요합니다.
