"""Phase 4 — 메뉴에 FoodType을 붙인다 (검색의 전제조건, D-9).

**이게 없으면 검색이 구조적으로 동작하지 않는다.** Spring의
`RestaurantService.searchMenus()`는 검색어를 `SynonymResolver`로 `FoodType`으로
바꿔 필터링하는데, 정작 `menu_food_type`에 쓰는 주체가 아무도 없다 — Python에는
태거가 없었고, Spring 엔티티는 전부 `@Immutable`이라 쓰기가 불가능하다.

태그의 근거는 두 가지이고, **합집합**으로 붙인다(D-9 — 임베딩 없이).

1. **식약처 대분류** (`밥류` → RICE, `국 및 탕류` → SOUP)
   매칭에 성공한 메뉴만 쓸 수 있다. 사람이 분류해 둔 값이라 가장 믿을 만하다.
2. **메뉴명 키워드** (`돈까스` → FRIED, `삼겹살` → MEAT)
   **매칭에 실패한 메뉴도 반드시 태깅해야 한다.** 영양정보가 NULL이어도
   검색·필터에는 걸려야 하기 때문이다. 지금 미매칭이 180건 넘는데 이게 빠지면
   검색 결과가 통째로 비어 보인다.

키워드는 **긴 것이 이긴다**. `탕수육`에 `탕`(SOUP)과 `탕수육`(FRIED)이 동시에
걸리는데, 짧은 쪽을 그대로 두면 탕수육이 국물 요리로 검색된다. 그래서 다른
키워드에 포함되는 키워드는 버린다. 반면 `새우튀김`의 `새우`(SEAFOOD)와
`튀김`(FRIED)은 서로 포함 관계가 아니므로 **둘 다 남긴다** — 이건 실제로
해산물이면서 튀김이 맞다.

카페(CAFE_DESSERT)는 태깅하지 않는다. 서비스에서 카페 식당을 노출하지 않기로
했기 때문이다(2026-08-06 결정). 이 결정이 바뀌면 `--include-cafe`로 되돌릴 수 있다.
"""

from __future__ import annotations

import csv
import logging
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

#: Spring `restaurant.domain.FoodType`과 **정확히** 같아야 한다. 여기에 없는
#: 값을 쓰면 Hibernate가 조회 시 IllegalArgumentException으로 터진다.
FOOD_TYPES: tuple[str, ...] = (
    "MEAT",
    "NOODLE",
    "RICE",
    "SOUP",
    "SNACK",
    "SALAD",
    "SEAFOOD",
    "FRIED",
    "DESSERT",
    "PIZZA",
    "SANDWICH",
)

_CAFE_CUISINE = "CAFE_DESSERT"

DEFAULT_MAP_PATH = Path("data/foodtype_map.csv")
DEFAULT_KEYWORD_PATH = Path("data/foodtype_keyword.csv")
DEFAULT_SYNONYM_PATH = Path("data/foodtype_synonym.csv")

#: `export-foodtype-map`이 대분류 이름을 보고 FoodType을 제안할 때 쓰는 규칙.
#: 위에서부터 검사해 처음 걸리는 것을 제안한다 — `국 및 탕류`가 `탕`보다 먼저
#: `국`에 걸려도 결과는 같지만, `면 및 만두류`처럼 두 종류가 섞인 이름은 앞에
#: 둔 쪽이 이긴다. **어디까지나 초안이고 사람이 검토한다.**
_CATEGORY_HINTS: tuple[tuple[str, str], ...] = (
    ("밥", "RICE"),
    ("죽", "RICE"),
    ("면", "NOODLE"),
    ("만두", "SNACK"),
    ("국", "SOUP"),
    ("탕", "SOUP"),
    ("찌개", "SOUP"),
    ("전골", "SOUP"),
    ("튀김", "FRIED"),
    ("구이", "MEAT"),
    ("육류", "MEAT"),
    ("생채", "SALAD"),
    ("무침", "SALAD"),
    ("샐러드", "SALAD"),
    ("젓갈", "SEAFOOD"),
    ("빵", "DESSERT"),
    ("과자", "DESSERT"),
    ("빙과", "DESSERT"),
    ("유제품", "DESSERT"),
)


class TaggerError(RuntimeError):
    """설정 파일이 잘못돼 태깅을 시작할 수 없는 경우."""


#: 키워드 사전에서 "이 말이 나오면 그 안에 든 짧은 키워드를 무시하라"는 표시.
#: `중국식냉면`이 `국`에 걸려 국물 요리가 되는 걸 막으려면, `중국`을 더 긴
#: 키워드로 등록해 짧은 쪽을 밀어내야 한다. 그런데 `중국` 자체는 어떤
#: FoodType도 아니므로 태그는 붙이지 않는다.
BLOCKER = "-"


def _validate(food_type: str, source: str) -> str:
    value = food_type.strip().upper()
    if value == BLOCKER:
        return BLOCKER
    if value not in FOOD_TYPES:
        raise TaggerError(
            f"{source}: 알 수 없는 FoodType '{food_type}'. "
            f"쓸 수 있는 값은 {', '.join(FOOD_TYPES)} 뿐이다 (Spring FoodType과 일치해야 함)."
        )
    return value


def load_foodtype_map(path: str | Path = DEFAULT_MAP_PATH) -> dict[str, list[str]]:
    """식약처 대분류 → FoodType 목록. 비어 있는 행은 "분류 안 함"으로 둔다.

    한 대분류에 여러 FoodType을 줄 수 있다 (`면 및 만두류` → NOODLE, SNACK).
    구분자는 세미콜론이다 — 쉼표는 CSV 구분자와 충돌한다.
    """
    p = Path(path)
    if not p.exists():
        raise TaggerError(
            f"대분류 대응표가 없다: {p}\n"
            "먼저 `python -m app.main export-foodtype-map`으로 초안을 만들고 검토해라."
        )

    mapping: dict[str, list[str]] = {}
    with open(p, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            category = (row.get("major_category") or "").strip()
            raw = (row.get("food_types") or "").strip()
            if not category or not raw:
                continue
            mapping[category] = [
                _validate(v, f"{p}({category})") for v in raw.split(";") if v.strip()
            ]
    return mapping


def load_foodtype_keywords(
    path: str | Path = DEFAULT_KEYWORD_PATH,
) -> list[tuple[str, str]]:
    """(키워드, FoodType) 목록. 정규화된 메뉴명에 부분일치로 적용한다."""
    p = Path(path)
    if not p.exists():
        raise TaggerError(f"키워드 사전이 없다: {p}")

    out: list[tuple[str, str]] = []
    with open(p, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            keyword = (row.get("keyword") or "").strip().lower()
            food_type = (row.get("food_type") or "").strip()
            if keyword and food_type:
                out.append((keyword, _validate(food_type, f"{p}({keyword})")))
    return out


def tags_from_keywords(
    normalized_name: str, keywords: list[tuple[str, str]]
) -> set[str]:
    """메뉴명에서 FoodType을 뽑는다. **긴 키워드가 짧은 키워드를 밀어낸다.**

    `탕수육`에는 `탕`(SOUP)과 `탕수육`(FRIED)이 함께 걸리는데, 짧은 쪽을 두면
    탕수육이 국물 요리로 검색된다. 그래서 다른 매칭 키워드에 포함되는 키워드는
    버린다. `새우튀김`의 `새우`·`튀김`처럼 포함 관계가 아닌 것은 둘 다 남는다.

    `중국`처럼 그 자체는 음식 종류가 아니지만 짧은 키워드(`국`)를 밀어내야 하는
    말은 food_type을 `-`(BLOCKER)로 등록한다 — 밀어내는 역할만 하고 태그는
    남기지 않는다.
    """
    if not normalized_name:
        return set()

    name = normalized_name.lower()
    hits = [(k, t) for k, t in keywords if k in name]
    if not hits:
        return set()

    return {
        food_type
        for keyword, food_type in hits
        if food_type != BLOCKER
        and not any(keyword != other and keyword in other for other, _ in hits)
    }


#: Spring이 `@ElementCollection`으로 읽는 테이블. ddl-auto=update가 만들어줄
#: 수도 있지만, 파이프라인이 Spring보다 먼저 도는 경우가 있어 여기서도 만든다.
#: 컬럼 이름은 Hibernate의 기본 네이밍(snake_case)과 맞춰야 한다.
_CREATE_MENU_FOOD_TYPE = text("""
    CREATE TABLE IF NOT EXISTS menu_food_type (
        menu_id   BIGINT NOT NULL,
        food_type VARCHAR(30) NOT NULL,
        PRIMARY KEY (menu_id, food_type)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
""")

#: Hibernate(6.2+)는 `@Enumerated(STRING)` 컬럼을 MySQL **ENUM**으로 만든다.
#: 그러면 Java enum에 값을 추가할 때마다 DB 쪽 ENUM 목록이 뒤처져서, Python이
#: 새 값을 넣는 순간 `Data truncated for column 'food_type'`(에러 1265)로 죽는다.
#: 실제로 PIZZA를 추가하자마자 이 사고가 났다.
#:
#: 이 테이블을 실제로 쓰는 주체는 Python이고(Spring 엔티티는 전부 @Immutable),
#: `@Enumerated(STRING)`은 VARCHAR도 문제없이 읽는다. 그래서 ENUM을 VARCHAR로
#: 바꿔 **값이 늘어나도 스키마를 건드릴 일이 없게** 한다.
_SELECT_FOOD_TYPE_COLUMN = text("""
    SELECT COLUMN_TYPE
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = :table_name
      AND COLUMN_NAME = 'food_type'
""")

#: 테이블 이름은 바인드 파라미터로 못 넘긴다. 문자열을 조립해야 하므로
#: 여기 적힌 이름만 허용해 SQL 조립에 외부 입력이 섞이지 않게 한다.
_FOOD_TYPE_TABLES = ("menu_food_type", "food_type_synonym")


def _relax_food_type_column(session: Session, table_name: str) -> bool:
    """food_type이 ENUM이면 VARCHAR(30)으로 바꾼다. 바꿨으면 True."""
    if table_name not in _FOOD_TYPE_TABLES:
        raise TaggerError(f"허용되지 않은 테이블: {table_name}")

    row = session.execute(
        _SELECT_FOOD_TYPE_COLUMN, {"table_name": table_name}
    ).first()
    if row is None:
        return False  # 테이블이 아직 없다 — CREATE가 VARCHAR로 만든다

    column_type = str(row[0])
    if not column_type.lower().startswith("enum"):
        return False

    session.execute(text(f"ALTER TABLE {table_name} MODIFY food_type VARCHAR(30) NOT NULL"))
    logger.info(
        "%s.food_type을 ENUM → VARCHAR(30)으로 변경했다 "
        "(Hibernate가 만든 ENUM은 FoodType이 늘어날 때마다 적재를 깨뜨린다)",
        table_name,
    )
    return True


#: 메뉴를 지우고 다시 적재하면(정규화 규칙 변경 등) 태그만 남아 떠돈다.
#: 그 상태로 Spring이 조회하면 없는 메뉴의 태그를 읽으려다 조인에서 사라질 뿐
#: 눈에 띄지 않아, 원인 모를 검색 누락으로 이어진다.
_DELETE_ORPHAN_TAGS = text("""
    DELETE t FROM menu_food_type t
    LEFT JOIN menu m ON m.id = t.menu_id
    WHERE m.id IS NULL
""")

_DELETE_TAGS_FOR_MENU = text("DELETE FROM menu_food_type WHERE menu_id = :menu_id")

_INSERT_TAG = text(
    "INSERT INTO menu_food_type (menu_id, food_type) VALUES (:menu_id, :food_type)"
)

#: 매칭된 메뉴는 official_food의 대분류를 함께 읽는다. LEFT JOIN인 이유는
#: 미매칭 메뉴도 **반드시** 태깅 대상이기 때문이다.
_SELECT_MENUS_FOR_TAGGING = text("""
    SELECT m.id, m.name, m.normalized_name, r.cuisine, f.major_category
    FROM menu m
    JOIN restaurant r ON r.id = m.restaurant_id
    LEFT JOIN official_food f ON f.food_code = m.official_food_code
    ORDER BY m.id
""")


@dataclass
class TagReport:
    total_menus: int = 0
    skipped_cafe: int = 0
    tagged_menus: int = 0
    untagged_menus: int = 0
    from_category: int = 0      # 대분류가 근거가 된 메뉴 수
    from_keyword: int = 0       # 메뉴명 키워드가 근거가 된 메뉴 수
    orphan_deleted: int = 0
    by_type: Counter = field(default_factory=Counter)
    untagged_names: list[str] = field(default_factory=list)

    def summary(self, applied: bool) -> str:
        rate = (self.tagged_menus / self.total_menus * 100) if self.total_menus else 0.0
        lines = [
            ("" if applied else "[집계만 — DB 미반영] ")
            + f"메뉴 {self.total_menus}건 중 {self.tagged_menus}건 태깅 ({rate:.1f}%)"
            + (f", 카페 제외 {self.skipped_cafe}건" if self.skipped_cafe else ""),
            f"  근거: 식약처 대분류 {self.from_category}건 / 메뉴명 키워드 {self.from_keyword}건 (중복 포함)",
        ]
        for food_type in FOOD_TYPES:
            count = self.by_type.get(food_type, 0)
            if count:
                lines.append(f"  - {food_type}: {count}건")
        lines.append(
            f"태그 0개: {self.untagged_menus}건 "
            "— 이 메뉴들은 종류 필터 검색에 걸리지 않는다"
        )
        if self.orphan_deleted:
            lines.append(f"삭제된 메뉴의 태그 {self.orphan_deleted}건 정리함")
        return "\n".join(lines)


def run_tagging(
    session: Session,
    apply: bool = False,
    include_cafe: bool = False,
    map_path: str | Path = DEFAULT_MAP_PATH,
    keyword_path: str | Path = DEFAULT_KEYWORD_PATH,
) -> TagReport:
    """전체 메뉴에 FoodType을 붙인다.

    apply=False면 DB를 건드리지 않고 집계만 한다. 태그가 하나도 안 붙는 메뉴가
    몇 건인지 먼저 보고 키워드를 보강하는 용도다 — 그 메뉴들은 종류 필터
    검색에서 통째로 사라지기 때문에, 붙이기 전에 반드시 확인해야 한다.
    """
    category_map = load_foodtype_map(map_path)
    keywords = load_foodtype_keywords(keyword_path)
    logger.info(
        "대분류 대응표 %d종 / 메뉴명 키워드 %d개 로드", len(category_map), len(keywords)
    )

    report = TagReport()
    if apply:
        session.execute(_CREATE_MENU_FOOD_TYPE)
        _relax_food_type_column(session, "menu_food_type")
        report.orphan_deleted = session.execute(_DELETE_ORPHAN_TAGS).rowcount or 0

    for menu_id, name, normalized_name, cuisine, major_category in session.execute(
        _SELECT_MENUS_FOR_TAGGING
    ).all():
        if not include_cafe and cuisine == _CAFE_CUISINE:
            report.skipped_cafe += 1
            continue

        report.total_menus += 1

        category_tags = set(category_map.get(str(major_category).strip(), [])) if major_category else set()
        keyword_tags = tags_from_keywords(str(normalized_name or ""), keywords)
        if category_tags:
            report.from_category += 1
        if keyword_tags:
            report.from_keyword += 1

        tags = category_tags | keyword_tags
        if not tags:
            report.untagged_menus += 1
            report.untagged_names.append(str(name))
            continue

        report.tagged_menus += 1
        report.by_type.update(tags)

        if apply:
            # 지우고 다시 넣는다. 태그가 줄어드는 경우(키워드 수정)에도 옛 태그가
            # 남지 않아야 하고, 테이블에 유니크 제약이 없을 수도 있어서다.
            session.execute(_DELETE_TAGS_FOR_MENU, {"menu_id": menu_id})
            for food_type in sorted(tags):
                session.execute(
                    _INSERT_TAG, {"menu_id": menu_id, "food_type": food_type}
                )

    return report


# ─────────────────────────────────────────────────────────────
# 대분류 대응표 초안 만들기
# ─────────────────────────────────────────────────────────────

_SELECT_CATEGORIES = text("""
    SELECT major_category, COUNT(*) AS c
    FROM official_food
    WHERE major_category IS NOT NULL AND major_category <> ''
    GROUP BY major_category
    ORDER BY c DESC
""")


def _suggest(category: str) -> str:
    for keyword, food_type in _CATEGORY_HINTS:
        if keyword in category:
            return food_type
    return ""


def export_foodtype_map(
    session: Session, output_path: str | Path = DEFAULT_MAP_PATH
) -> tuple[int, int]:
    """DB의 대분류 목록을 읽어 대응표 초안을 만든다. (전체 종수, 제안된 종수)

    대분류 이름은 원본 데이터에 있는 문자열 그대로여야 한다 — 사람이 기억에
    의존해 적으면 `국 및 탕류`를 `국·탕류`로 쓰는 식으로 어긋나고, 그러면
    태깅이 조용히 0건이 된다. 그래서 손으로 적지 않고 DB에서 뽑는다.

    기존 파일이 있으면 **이미 정해둔 값을 이어받는다** — 재실행이 검토 결과를
    지우면 안 된다.
    """
    out = Path(output_path)
    previous: dict[str, str] = {}
    if out.exists():
        with open(out, encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                category = (row.get("major_category") or "").strip()
                if category:
                    previous[category] = (row.get("food_types") or "").strip()

    rows = session.execute(_SELECT_CATEGORIES).all()
    suggested = 0

    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["major_category", "food_types", "건수", "비고"])
        for category, count in rows:
            category = str(category)
            value = previous.get(category)
            note = "검토 완료" if value else ""
            if value is None:
                value = _suggest(category)
                note = "자동 제안 — 확인 필요" if value else "미분류 — 직접 채울 것"
            if value:
                suggested += 1
            writer.writerow([category, value, count, note])

    logger.info("대분류 %d종 중 %d종에 값이 채워짐: %s", len(rows), suggested, out)
    return len(rows), suggested


# ─────────────────────────────────────────────────────────────
# food_type_synonym 시딩 — 검색어를 FoodType으로 바꾸는 사전
# ─────────────────────────────────────────────────────────────

#: Spring이 읽는 테이블. `SynonymResolver.resolve()`가 `toLowerCase` + **공백
#: 전체 제거**로 정규화한 뒤 조회하므로(`SynonymResolver.java:25-27`),
#: 시드도 반드시 같은 형태로 넣어야 한다 — "돼지 고기"로 넣으면 영원히 안 걸린다.
_CREATE_SYNONYM_TABLE = text("""
    CREATE TABLE IF NOT EXISTS food_type_synonym (
        id        BIGINT NOT NULL AUTO_INCREMENT,
        term      VARCHAR(100) NOT NULL,
        food_type VARCHAR(30) NOT NULL,
        PRIMARY KEY (id),
        UNIQUE KEY uk_synonym_term (term)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
""")

_UPSERT_SYNONYM = text("""
    INSERT INTO food_type_synonym (term, food_type)
    VALUES (:term, :food_type) AS new
    ON DUPLICATE KEY UPDATE food_type = new.food_type
""")


def normalize_term(term: str) -> str:
    """Spring `SynonymResolver`와 같은 규칙. 이 함수가 그쪽과 어긋나면 검색이
    조용히 0건이 된다 — 예외도 로그도 없이 그냥 안 걸린다."""
    return "".join(term.lower().split())


def seed_synonyms(
    session: Session, path: str | Path = DEFAULT_SYNONYM_PATH, apply: bool = False
) -> tuple[int, list[tuple[str, str]]]:
    """검색어 동의어 사전을 DB에 넣는다. (건수, 목록)"""
    p = Path(path)
    if not p.exists():
        raise TaggerError(f"동의어 사전이 없다: {p}")

    seeds: list[tuple[str, str]] = []
    seen: set[str] = set()
    with open(p, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            term = normalize_term(row.get("term") or "")
            food_type = (row.get("food_type") or "").strip()
            if not term or not food_type:
                continue
            if term in seen:
                # 같은 검색어가 두 FoodType에 걸리면 term이 UNIQUE라 뒤엣것이
                # 앞엣것을 덮어쓴다. 조용히 덮이면 원인을 못 찾으므로 알린다.
                logger.warning("동의어 '%s' 중복 — 뒤에 나온 정의가 이깁니다", term)
            seen.add(term)
            seeds.append((term, _validate(food_type, str(p))))

    if apply:
        session.execute(_CREATE_SYNONYM_TABLE)
        _relax_food_type_column(session, "food_type_synonym")
        for term, food_type in seeds:
            session.execute(_UPSERT_SYNONYM, {"term": term, "food_type": food_type})

    return len(seeds), seeds
