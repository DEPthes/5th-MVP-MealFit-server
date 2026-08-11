# MealFit 데이터 적재 파이프라인 (Python)

네이버 지도에서 명지대 인문캠퍼스 주변 식당·메뉴를 수집해, 식약처 공식 영양 DB와 짝지어 MySQL에 적재합니다.

**서버(Spring)와 같은 DB(`mealfit_test`)를 씁니다.** 역할이 명확히 나뉘어 있습니다.

| | 이 프로젝트 (Python) | 서버 (Spring) |
|---|---|---|
| `restaurant` / `menu` | **쓰기** | 읽기 전용 (`@Immutable`) |
| `official_food` / `menu_alias` | **쓰기** | `official_food`만 읽음 |
| `member` / `inbody` | 건드리지 않음 | 쓰기 |

---

## 🚀 목적별 시작점

무엇을 하려는지에 따라 필요한 준비물이 완전히 다릅니다.

| 하려는 것 | 필요한 것 | 안내 |
|---|---|---|
| **API 기능 테스트** | MySQL만 | [`sql/README.md`](sql/README.md) — 정제 완료 데이터를 넣고 바로 테스트 |
| **파이프라인 로직 검증** | MySQL + Python | [아래 §4](#4-llm-없이-파이프라인-검증하기) — LLM 없이, DB 쓰기 없이 |
| **단위 테스트** | Python만 | [아래 §5](#5-단위-테스트) — DB조차 불필요 |
| **실제 수집·적재** | 전부 | [아래 §6](#6-전체-파이프라인-실행) |

**코드 리뷰만 하신다면 첫 번째 줄로 충분합니다.** 크롤링·LLM을 돌릴 필요가 없습니다.

---

## 1. 설치

Python 3.10 이상이 필요합니다 (dataclass slots, `X | None` 문법 사용).

```bash
py -3.13 -m venv .venv && .venv/Scripts/activate && pip install -r requirements.txt
```

크롤링까지 하려면 브라우저 바이너리를 추가로 받습니다 (pip과 별도).

```bash
playwright install chromium
```

---

## 2. 환경 변수

`.env.example`을 `.env`로 복사해 값을 채웁니다. **`.env`는 커밋하지 않습니다.**

```bash
cp .env.example .env
```

| 변수 | 필요한 경우 | 없으면 |
|---|---|---|
| `MEALFIT_DB_PASSWORD` | 항상 | 접속 실패 |
| `MEALFIT_KAKAO_REST_API_KEY` | 새 식당 좌표 확보 | 지오코딩을 건너뛰고 좌표를 비움 |
| `MEALFIT_GEMINI_API_KEY` | `llm-match`를 Gemini로 돌릴 때 | 로컬 Ollama가 기본이라 불필요 |

정문·후문 좌표는 `app/settings.py`에 기본값이 있습니다 — **서버 `ReferencePoint.java`와 같은 값**이라 보통 건드릴 일이 없습니다.

---

## 3. 스키마 준비

서버의 `ddl-auto=update`가 만드는 것은 **Java 엔티티에 매핑된 것뿐**입니다. 크롤러만 쓰는 컬럼·인덱스는 별도 관리합니다.

```bash
mysql -u root -p mealfit_test < sql/schema_additions.sql
```

무엇이 왜 들어 있는지는 파일 안 주석에 적혀 있습니다. **빈 DB에서는 이걸 건너뛰면 적재가 깨집니다.**

---

## 4. LLM 없이 파이프라인 검증하기

로컬 LLM(Ollama)이나 Gemini 키가 없어도 **LLM 단계만 빼고 전부 돌려볼 수 있습니다.**
그리고 `--apply`를 주지 않는 한 **DB에 아무것도 쓰지 않습니다** — 집계 리포트만 출력합니다.

```bash
python -m app.main load --dry-run --input crawl_results/<파일>.json
```

```bash
python -m app.main match
```

```bash
python -m app.main tag
```

각 단계가 하는 일과 안전성:

| 명령 | 기본 동작 | DB 쓰기 | LLM |
|---|---|---|---|
| `load --dry-run` | JSON을 읽어 정규화하고 몇 건이 적재될지 리포트 | ❌ 없음 | ❌ |
| `match` | 규칙 기반으로 메뉴↔식약처 식품 매칭률 집계 | ❌ `--apply` 시에만 | ❌ |
| `tag` | 키워드로 음식종류 태그를 붙여 집계 | ❌ `--apply` 시에만 | ❌ |
| `llm-match` | LLM에 애매한 메뉴를 물어봄 | ⚠️ `--apply` 없어도 `menu_alias`에 기록 | ✅ |

> **`match`와 `tag`는 DB를 읽습니다.** 쓰지 않을 뿐입니다. 그래서 `menu`·`official_food`에
> 데이터가 있어야 의미 있는 숫자가 나옵니다 — `sql/seed_test_data.sql`을 넣어 두면 됩니다.

> **`llm-match`만 예외입니다.** `--apply`가 없어도 판정 결과를 `menu_alias`에 남깁니다
> (같은 질문을 두 번 하지 않기 위한 캐시). LLM을 건너뛰려면 이 명령을 아예 실행하지 마세요.
> seed 데이터에 `menu_alias` 448건이 이미 들어 있어, 나중에 돌리더라도 대부분 캐시에서 해결됩니다.

---

## 5. 단위 테스트

DB·네트워크·LLM 전부 불필요합니다.

```bash
pytest
```

| 파일 | 대상 |
|---|---|
| `tests/test_parsers.py` | 가격·메뉴명 파싱, 중복 제거 |
| `tests/test_writer_distance.py` | 거리 계산 — **서버 `ReferencePoint`와 좌표가 일치하는지 포함** |
| `tests/test_writer_integration.py` | DB 적재 경로 (아래 참고) |

`test_writer_integration.py`는 **실제 MySQL이 필요해서 기본적으로 건너뜁니다.** 돌리려면 전용 DB를 지정합니다.

```bash
MEALFIT_TEST_DB_URL="mysql+pymysql://root:비번@localhost:3306/mealfit_it?charset=utf8mb4" pytest -m integration
```

⚠️ 이 테스트는 테이블에 쓰고 지웁니다. **`mealfit_test`를 가리키면 실행을 거부**하도록 안전장치를 넣어 뒀습니다.

---

## 6. 전체 파이프라인 실행

실제로 수집부터 적재까지 하는 경우입니다. 위 준비물이 전부 필요합니다.

```bash
python -m app.main crawl --source naver --area "명지대 인문캠퍼스" --keyword 맛집 --max-count 50
```

```bash
python -m app.main load --input crawl_results/<생성된파일>.json
```

```bash
python -m app.main load-official-food --input "<식약처 영양정보 xlsx 경로>"
```

```bash
python -m app.main match --apply
```

```bash
python -m app.main llm-match --apply
```

```bash
python -m app.main tag --apply
```

> **식약처 xlsx는 저장소에 없습니다.** 공공데이터포털에서 받은 파일을 따로 준비해야 합니다
> (현재 데이터는 19,495행 중 16,910건을 적재한 것으로, 음료 2,585건은 100ml 기준이라 제외됩니다).

실행 로그는 매번 `logs/`에 타임스탬프로 남습니다 (커밋 대상 아님).

---

## 7. 명령어 전체

| 명령 | 설명 |
|---|---|
| `crawl` | 네이버 지도에서 식당·메뉴 수집 → JSON |
| `load` | JSON → `restaurant` / `menu` 적재 |
| `load-official-food` | 식약처 xlsx → `official_food` |
| `match` | 규칙 기반 매칭 (Step 3~5) |
| `llm-match` / `llm-validate` / `llm-models` | LLM 보조 매칭 |
| `tag` | 메뉴에 음식종류(FoodType) 부여 — 검색의 전제조건 |
| `seed-synonyms` | 동의어 사전을 DB에 반영 |
| `find-food` | 식약처 식품 검색 (디버깅용) |
| `export-labels` / `score-labels` | 매칭 품질 라벨링·채점 |
| `export-branches` / `export-foodtype-map` | 점검용 내보내기 |

`--help`로 각 명령의 옵션을 볼 수 있습니다.

```bash
python -m app.main match --help
```

---

## 8. 구조

```
app/
├── main.py          CLI 진입점 — 위 명령들의 디스패치
├── settings.py      .env → 환경변수 → 기본값 (pydantic-settings)
├── db.py            SQLAlchemy 엔진·세션. 테이블은 만들지 않는다
├── crawler/         Playwright 기반 수집 (네이버 지도)
├── model/raw.py     수집 ↔ 정제 사이의 계약(불변 dataclass)
└── pipeline/
    ├── normalizer.py    상호·메뉴명 정규화, cuisine 매핑
    ├── geocoder.py      카카오 주소→좌표
    ├── distance.py      Haversine 거리 (서버가 이 결과를 읽는다)
    ├── official_food.py 식약처 DB 적재
    ├── matcher.py       규칙 기반 매칭
    ├── llm_matcher.py   LLM 보조 매칭 + 판정 캐시
    ├── tagger.py        음식종류 태깅
    └── writer.py        restaurant/menu 쓰기 — 이 테이블의 주인
data/                손으로 만든 정규화 사전 (CSV) — 없으면 오동작
sql/                 스키마 추가분 + 테스트 데이터
```

`data/`의 CSV는 **생성물이 아니라 입력**입니다. 커밋 대상이며, 없으면 정규화가 잘못 동작합니다.
