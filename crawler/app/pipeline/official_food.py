"""식약처 음식DB(xlsx) → 로컬 official_food 테이블 적재.

이 테이블은 Spring이 모르는 순수 Python 전용 테이블이다 — Restaurant/Menu처럼
ALTER로 얹는 게 아니라 이 모듈이 직접 CREATE TABLE 한다.

원본 파일은 "음식(조리된 요리)" 데이터만 담고 있고(데이터구분코드=D),
영양성분함량기준량은 100g 또는 100ml 두 종류다.

⚠ 과거에 "100ml=음료류"로 가정하고 전부 제외했으나, 원본 데이터를 직접 확인한
결과 틀린 가정이었다. 100ml 5,740건 중 실제 음료(식품대분류=`음료 및 차류`)는
2,585건뿐이고, 나머지 3,155건은 국·탕·볶음·밥·찌개·면 등 **일반 조리요리**다
(예: `짜장면`은 100g 쪽엔 없고 100ml 쪽에만 있다 — 100g엔 `자장면`이라는
표준어 표기로만 존재). 그래서 100ml 중 음료가 아닌 행은 포함한다. 음료
2,585건은 여전히 제외한다 — 매칭 대상은 "요리"이기 때문이다(카페 메뉴는
D-8 범위 밖, 미해결 ⑫).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

import openpyxl
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.pipeline.normalizer import normalize_menu_name

logger = logging.getLogger(__name__)

# 원본 컬럼 위치 (0-based). 160개 컬럼 중 실제로 쓰는 것만 뽑는다.
_COL_FOOD_CODE = 0        # 식품코드
_COL_FOOD_NAME = 1        # 식품명
_COL_ORIGIN = 5           # 식품기원명 (F열) — 외식/가정식 등 "이 수치가 어디서 온 값인가"
_COL_MAJOR_CATEGORY = 7   # 식품대분류명
_COL_BASIS = 16           # 영양성분함량기준량
_COL_CALORIES = 17        # 에너지(kcal)
_COL_PROTEIN = 19         # 단백질(g)
_COL_FAT = 20             # 지방(g)
_COL_CARBOHYDRATE = 22    # 탄수화물(g)
_COL_SODIUM = 29          # 나트륨(mg)
_COL_SERVING_WEIGHT = 154 # 식품중량 (예: "900g" — 지금은 파싱 없이 원문 그대로 보관)
_COL_COMPANY = 155        # 업체명 (프랜차이즈 배제 판단용 — 이름 문자열 추측 대신 원본 데이터로 판단)
_COL_REPRESENTATIVE_CODE = 8   # 대표식품코드 (I열) — food_code보다 세밀도가 낮은 중간 분류
_COL_REPRESENTATIVE_NAME = 9   # 대표식품명   (J열) — 예: "국밥_돼지머리"/"국밥_순대국밥" → "국밥"

_BASIS_100G = "100g"
_BASIS_100ML = "100ml"
#: 이 대분류만 100ml 쪽에서 제외한다. 나머지 100ml 행(국·탕·볶음·밥 등)은
#: 요리이므로 포함한다.
_DRINK_CATEGORY = "음료 및 차류"

_CREATE_TABLE = text("""
    CREATE TABLE IF NOT EXISTS official_food (
        food_code          VARCHAR(30) NOT NULL,
        food_name          VARCHAR(255) NOT NULL,
        normalized_name    VARCHAR(255) COLLATE utf8mb4_bin NOT NULL,
        origin             VARCHAR(50) NULL,
        major_category     VARCHAR(100) NULL,
        calories           INT NULL,
        carbohydrate       DECIMAL(8,2) NULL,
        protein            DECIMAL(8,2) NULL,
        fat                DECIMAL(8,2) NULL,
        sodium             DECIMAL(8,2) NULL,
        serving_weight_raw VARCHAR(50) NULL,
        company_name       VARCHAR(100) NULL,
        serving_basis      VARCHAR(10) NULL,
        representative_code VARCHAR(20) NULL,
        representative_name VARCHAR(255) NULL,
        PRIMARY KEY (food_code),
        INDEX idx_normalized (normalized_name)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
""")

#: 이미 라이브로 존재하는 테이블에 새 컬럼을 얹기 위한 ALTER들.
#: `_CREATE_TABLE`은 신규 설치(테스트 DB를 새로 만들 때)에만 실제로 컬럼을
#: 만들고, 지금처럼 테이블이 이미 있는 경우엔 이 ALTER들이 실제로 컬럼을
#: 추가한다. 이미 컬럼이 있으면 MySQL 에러 1060(Duplicate column)이 나는데,
#: 재실행 시 정상 상황이라 무시한다.
_ALTER_ADD_COMPANY = text("ALTER TABLE official_food ADD COLUMN company_name VARCHAR(100) NULL")
#: '100g'/'100ml' 원본 기준량. 같은 이름이 양쪽에 다 있을 때(예: 갈비탕) 매칭
#: 단계에서 100g을 우선하기 위해 필요하다(D-8 — 전부 100g 기준이라는 계약).
_ALTER_ADD_SERVING_BASIS = text("ALTER TABLE official_food ADD COLUMN serving_basis VARCHAR(10) NULL")
#: 식품기원명(외식/가정식 등). 같은 요리가 여러 기원으로 중복 수록돼 있고,
#: 식당 메뉴에 붙일 값은 **외식** 쪽이다 — 라벨링에서 사람이 그 기준으로
#: 정답을 골랐다(`족발`·`골뱅이무침_소면` 사례). 이름만으로는 구분이 안 되므로
#: 컬럼으로 들고 있어야 후보 정렬과 LLM 프롬프트 양쪽에서 쓸 수 있다.
_ALTER_ADD_ORIGIN = text("ALTER TABLE official_food ADD COLUMN origin VARCHAR(50) NULL")
#: 대표식품명(J열). FoodType(11종)보다 세밀한 음식 종류 중간 계층 — 검색 시
#: "짜장면"으로 검색하면 대표식품명이 같은 "간짜장"·"마라짜장"도 함께 찾히게 한다.
_ALTER_ADD_REPRESENTATIVE_CODE = text(
    "ALTER TABLE official_food ADD COLUMN representative_code VARCHAR(20) NULL"
)
_ALTER_ADD_REPRESENTATIVE_NAME = text(
    "ALTER TABLE official_food ADD COLUMN representative_name VARCHAR(255) NULL"
)
_MYSQL_ERR_DUPLICATE_COLUMN = 1060

_UPSERT = text("""
    INSERT INTO official_food
        (food_code, food_name, normalized_name, origin, major_category,
         calories, carbohydrate, protein, fat, sodium, serving_weight_raw,
         company_name, serving_basis, representative_code, representative_name)
    VALUES
        (:food_code, :food_name, :normalized_name, :origin, :major_category,
         :calories, :carbohydrate, :protein, :fat, :sodium, :serving_weight_raw,
         :company_name, :serving_basis, :representative_code, :representative_name)
    AS new
    ON DUPLICATE KEY UPDATE
        food_name = new.food_name,
        normalized_name = new.normalized_name,
        origin = new.origin,
        major_category = new.major_category,
        calories = new.calories,
        carbohydrate = new.carbohydrate,
        protein = new.protein,
        fat = new.fat,
        sodium = new.sodium,
        serving_weight_raw = new.serving_weight_raw,
        company_name = new.company_name,
        serving_basis = new.serving_basis,
        representative_code = new.representative_code,
        representative_name = new.representative_name
""")


@dataclass
class OfficialFoodLoadReport:
    total_rows: int = 0
    loaded_100g: int = 0
    loaded_100ml: int = 0
    skipped_drink: int = 0
    skipped_other_basis: int = 0
    skipped_missing_name: int = 0

    @property
    def loaded(self) -> int:
        return self.loaded_100g + self.loaded_100ml

    def summary(self) -> str:
        return (
            f"전체 {self.total_rows}행 중 {self.loaded}건 적재 "
            f"(100g {self.loaded_100g}건 + 100ml 요리 {self.loaded_100ml}건) — "
            f"음료(100ml) {self.skipped_drink}건 제외, "
            f"기준량 불명 {self.skipped_other_basis}건 제외, "
            f"식품명 없음 {self.skipped_missing_name}건 제외"
        )


def _to_int(value: object) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None


def _to_decimal(value: object) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _add_column_if_missing(session: Session, alter: text) -> None:
    try:
        session.execute(alter)
    except OperationalError as e:
        if getattr(e.orig, "args", [None])[0] != _MYSQL_ERR_DUPLICATE_COLUMN:
            raise
        session.rollback()


def load_official_food(
    xlsx_path: str,
    session: Session,
    menu_variants: dict[str, str] | None = None,
) -> OfficialFoodLoadReport:
    """식약처 xlsx를 읽어 100g 전체 + 100ml 요리(음료 제외)를 official_food에 upsert한다.

    menu_variants는 menu 쪽과 동일한 사전을 넘겨야 한다 — normalize_menu_name이
    양쪽에서 같은 표기(예: "차돌백이"→"차돌박이")로 수렴해야 매칭이 성립한다.
    """
    session.execute(_CREATE_TABLE)
    _add_column_if_missing(session, _ALTER_ADD_COMPANY)
    _add_column_if_missing(session, _ALTER_ADD_SERVING_BASIS)
    _add_column_if_missing(session, _ALTER_ADD_ORIGIN)
    _add_column_if_missing(session, _ALTER_ADD_REPRESENTATIVE_CODE)
    _add_column_if_missing(session, _ALTER_ADD_REPRESENTATIVE_NAME)

    wb = openpyxl.load_workbook(xlsx_path, read_only=True, data_only=True)
    ws = wb.active

    report = OfficialFoodLoadReport()

    for row in ws.iter_rows(min_row=2, values_only=True):
        report.total_rows += 1

        food_code = row[_COL_FOOD_CODE]
        food_name = row[_COL_FOOD_NAME]

        if not food_code or not food_name:
            report.skipped_missing_name += 1
            continue

        basis = str(row[_COL_BASIS]).strip().lower()
        if basis == _BASIS_100G:
            pass
        elif basis == _BASIS_100ML:
            if str(row[_COL_MAJOR_CATEGORY]).strip() == _DRINK_CATEGORY:
                report.skipped_drink += 1
                continue
        else:
            report.skipped_other_basis += 1
            continue

        food_name = str(food_name).strip()
        session.execute(
            _UPSERT,
            {
                "food_code": str(food_code).strip(),
                "food_name": food_name,
                "normalized_name": normalize_menu_name(food_name, menu_variants),
                "origin": row[_COL_ORIGIN],
                "major_category": row[_COL_MAJOR_CATEGORY],
                "calories": _to_int(row[_COL_CALORIES]),
                "carbohydrate": _to_decimal(row[_COL_CARBOHYDRATE]),
                "protein": _to_decimal(row[_COL_PROTEIN]),
                "fat": _to_decimal(row[_COL_FAT]),
                "sodium": _to_decimal(row[_COL_SODIUM]),
                "serving_weight_raw": row[_COL_SERVING_WEIGHT],
                "company_name": row[_COL_COMPANY],
                "serving_basis": basis,
                "representative_code": row[_COL_REPRESENTATIVE_CODE],
                "representative_name": row[_COL_REPRESENTATIVE_NAME],
            },
        )
        if basis == _BASIS_100G:
            report.loaded_100g += 1
        else:
            report.loaded_100ml += 1

    return report
