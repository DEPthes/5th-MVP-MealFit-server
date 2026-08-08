"""메뉴명 ↔ 식약처 official_food 매칭 캐스케이드 (Step 3~5).

AI는 쓰지 않는다. 규칙 기반 4단계만으로 어디까지 잡히는지 먼저 실측하고,
남는 것을 LLM(D-2)에 넘기는 것이 다음 단계다.

식약처 `식품명`은 "버거_더블 한우불고기 버거"처럼 밑줄로 분류를 이어붙인
계층형이라, 실제 요리명은 대부분 **마지막 세그먼트**에 있다. 그래서 후보
문자열을 "전체명"과 "마지막 세그먼트" 두 가지로 만들어 둘 다 비교한다 —
크롤링 메뉴명("더블 한우불고기")은 전체명과는 절대 안 맞고 마지막
세그먼트하고만 맞기 때문이다.

캐스케이드 순서는 D-3의 confidence 내림차순이다. 먼저 잡힌 쪽이 이긴다.
"""

from __future__ import annotations

import csv
import datetime as dt
import logging
import random
import re
import shutil
from collections import defaultdict
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

#: 브랜드 배제 목록. 프랜차이즈 제품은 이름이 일반 요리와 겹치는데
#: (롯데리아 "불고기버거" vs 동네 고깃집 "불고기") 영양 수치는 전혀 달라서,
#: 후보에 남겨두면 오매칭만 늘린다. 파일로 뺀 이유는 실데이터를 보며
#: 계속 추가될 목록이기 때문이다.
DEFAULT_EXCLUDED_BRANDS_PATH = Path("data/excluded_brands.csv")

#: D-3 — 매칭 방법별 고정 confidence. 방법이 정해지면 값도 정해진다
#: (유사도 점수를 그대로 confidence로 쓰지 않는다).
#: LLM(0.80)은 규칙 4단계가 전부 실패한 메뉴에만 적용된다(llm_matcher.py) —
#: 캐스케이드에 끼어드는 5번째 단계가 아니라 그 뒤에 붙는 별도 패스다.
CONFIDENCE: dict[str, float] = {
    "EXACT": 1.00,
    "BRAND_EXACT": 1.00,
    "EDIT": 0.95,
    "BRAND_EDIT": 0.95,
    "BRAND_STRUCT": 0.90,
    "STRUCT": 0.85,
    "NGRAM": 0.70,
    "LLM": 0.80,
}

#: 브랜드 전용 매칭의 방법 이름. 후보 풀이 그 브랜드 제품으로만 좁혀져 있어서
#: 같은 방법이라도 일반 매칭보다 확실하다 — 롯데리아 매장의 `불고기버거`가
#: **롯데리아 항목 안에서** 포함매칭된 것과, 4만여 후보 전체에서 포함매칭된
#: 것은 신뢰도가 다르다. 그래서 STRUCT만 0.85 → 0.90으로 올려 잡는다.
_BRAND_METHOD = {
    "EXACT": "BRAND_EXACT",
    "EDIT": "BRAND_EDIT",
    "STRUCT": "BRAND_STRUCT",
}

#: 편집거리 단계 통과 기준. difflib 유사도(0~1). 공백을 지운 뒤 비교한다 —
#: 한국어 메뉴는 띄어쓰기가 제각각이라(`유부 초밥`/`유부초밥`) 공백을 그대로
#: 두면 같은 요리가 낮은 점수를 받고, 그걸 보정하려 기준을 낮추면 이번엔
#: `짜장면 → 짜장라면` 같은 한 글자 차이 오매칭이 통과한다.
#: 포함 관계(`왕갈비탕` ⊃ `갈비탕`)는 이 단계에서 떨어져도 다음 구조매칭
#: 단계가 제대로 잡아준다.
_EDIT_THRESHOLD = 0.90

#: n-gram 단계 통과 기준. 2-gram 자카드 유사도(0~1).
#: 0.50에서 시작했으나 `플랫화이트 → 커피_바닐라 플랫 화이트` 같은 오매칭이
#: 절반 가까이 섞여 0.65로 올렸다.
_NGRAM_THRESHOLD = 0.65

#: 퍼지 단계에 넘길 후보 수. 13,755건 전체와 편집거리를 재면 너무 느려서,
#: 2-gram 역색인으로 "글자를 하나라도 공유하는" 후보만 추려 상위 N건만 본다.
_SHORTLIST_SIZE = 50

#: 부분 포함(구조매칭)을 인정할 최소 길이·길이비. "밥"이 "제육덮밥"에
#: 포함된다고 매칭시키면 안 되므로 짧은 쪽이 너무 짧으면 배제한다.
_MIN_CONTAIN_LEN = 2
_MIN_CONTAIN_RATIO = 0.5


@dataclass(frozen=True)
class Candidate:
    """비교 단위 하나. 식약처 1행이 전체명·마지막 세그먼트 2개의 Candidate가 된다."""

    food_code: str
    food_name: str
    key: str                    # 실제로 메뉴명과 비교할 문자열
    flat: str                   # key에서 공백을 지운 것 (편집거리 비교용)
    tokens: frozenset[str]      # 공백 기준 토큰
    grams: frozenset[str]       # 공백 제거 후 2-gram
    #: 포함관계(구조매칭·n-gram)에 써도 되는 키인지. 재료명 조각은 False —
    #: 글자만 겹칠 뿐 같은 요리가 아니기 때문(`깐쇼새우` vs `볶음밥_새우`).
    allow_contain: bool = True
    #: '100g' 또는 '100ml'. 같은 이름이 양쪽에 다 있는 경우(예: 갈비탕 629건)
    #: 100g을 우선시키기 위해 필요하다 — D-8이 "전부 100g 기준"을 계약으로
    #: 정했으므로, 두 후보 중 하나를 고를 때는 그쪽을 우선한다.
    serving_basis: str = "100g"
    #: 식약처 식품대분류("밥류", "국 및 탕류" 등). 규칙 매칭은 쓰지 않지만
    #: LLM에게 후보를 보여줄 때 함께 준다 — 이름만으로는 `차돌박이`(고기)와
    #: `차돌박이구이_소고기`(구이)의 차이를 판단할 근거가 부족하기 때문.
    major_category: str = ""
    #: 식품기원명("외식", "가정식" 등). 같은 요리가 기원별로 중복 수록돼 있는데,
    #: 식당 메뉴에 붙일 값은 외식 쪽이다(라벨링 기준). 이름이 같은 후보들 사이
    #: 우선순위를 가르는 데 쓴다.
    origin: str = ""


@dataclass
class MatchResult:
    menu_id: int
    menu_name: str
    normalized_name: str
    food_code: str | None = None
    food_name: str | None = None
    matched_by: str | None = None
    confidence: float | None = None

    @property
    def matched(self) -> bool:
        return self.food_code is not None


@dataclass
class MatchReport:
    total_menus: int = 0
    total_candidates: int = 0
    excluded_rows: int = 0
    excluded_menus: int = 0
    excluded_cafe_menus: int = 0
    excluded_branch_menus: int = 0
    #: 브랜드 전용 매칭으로 처리한 메뉴 수 (프랜차이즈 매장 메뉴).
    brand_menus: int = 0
    #: 지점명으로 걸러낸 식당 이름 (중복 없이). 오탐 확인용으로 로그에 남긴다.
    excluded_branch_restaurants: list[str] = field(default_factory=list)
    by_method: dict[str, int] = field(default_factory=dict)
    #: 매칭 실패한 메뉴 전체 (건수 제한 없음). --sample은 매칭된 항목 예시
    #: 개수만 조절하고, 미매칭은 다음 단계(LLM)의 작업 목록 그 자체라
    #: 잘라내지 않는다.
    unmatched_names: list[str] = field(default_factory=list)
    #: 프랜차이즈 매장 메뉴 중 그 브랜드 항목에서 못 찾은 것. 위 목록과 섞지
    #: 않는다 — 해결 방법이 전혀 다르기 때문이다. 일반 미매칭은 정규화·LLM으로
    #: 풀지만, 이쪽은 "식약처에 그 브랜드의 그 메뉴가 없다"는 뜻이라 일반 요리
    #: 후보를 들이대면 안 된다(롯데리아 메뉴에 동네 불고기 수치를 붙이는 꼴).
    brand_unmatched_names: list[str] = field(default_factory=list)

    @property
    def matched(self) -> int:
        return sum(self.by_method.values())

    def summary(self) -> str:
        rate = (self.matched / self.total_menus * 100) if self.total_menus else 0.0
        lines = [
            f"후보 {self.total_candidates}건 (브랜드 배제로 {self.excluded_rows}행 제외)",
        ]
        if self.excluded_menus:
            lines.append(
                f"프랜차이즈 매장 메뉴 {self.excluded_menus}건은 집계에서 제외됨 "
                f"(--exclude-franchise)"
            )
        if self.excluded_cafe_menus:
            lines.append(
                f"카페(CAFE_DESSERT) 메뉴 {self.excluded_cafe_menus}건은 집계에서 제외됨 "
                f"(--exclude-cafe)"
            )
        if self.excluded_branch_menus:
            lines.append(
                f"지점명(~점) 식당 {len(self.excluded_branch_restaurants)}곳의 메뉴 "
                f"{self.excluded_branch_menus}건은 집계에서 제외됨 (--exclude-branch)"
            )
        lines.append(f"메뉴 {self.total_menus}건 중 {self.matched}건 매칭 ({rate:.1f}%)")

        # 프랜차이즈를 대상에 넣으면 분모가 통째로 달라져서, 전체 비율만 보면
        # 이전 측정치와 비교가 안 된다. 성격이 다른 두 집단이라 나눠서 찍는다.
        if self.brand_menus:
            brand_matched = sum(
                count for method, count in self.by_method.items()
                if method.startswith("BRAND_")
            )
            general_menus = self.total_menus - self.brand_menus
            general_matched = self.matched - brand_matched
            general_rate = (general_matched / general_menus * 100) if general_menus else 0.0
            brand_rate = brand_matched / self.brand_menus * 100
            lines.append(
                f"  · 일반 식당: {general_menus}건 중 {general_matched}건 ({general_rate:.1f}%)"
            )
            lines.append(
                f"  · 프랜차이즈: {self.brand_menus}건 중 {brand_matched}건 ({brand_rate:.1f}%) "
                f"— 같은 브랜드 항목 안에서만 매칭, 못 찾은 "
                f"{len(self.brand_unmatched_names)}건은 일반 미매칭과 분리 집계"
            )
        for method in CONFIDENCE:
            count = self.by_method.get(method, 0)
            if count:
                lines.append(f"  - {method} (confidence {CONFIDENCE[method]:.2f}): {count}건")
        unmatched = self.total_menus - self.matched
        lines.append(f"  - 미매칭: {unmatched}건")
        return "\n".join(lines)


def _bigrams(s: str) -> frozenset[str]:
    """공백을 지운 뒤 2글자씩 잘라낸다. 한국어 메뉴명은 띄어쓰기가 제각각이라
    (`순살 치킨` / `순살치킨`) 공백을 무시해야 비교가 성립한다."""
    t = s.replace(" ", "")
    if len(t) < 2:
        return frozenset([t]) if t else frozenset()
    return frozenset(t[i : i + 2] for i in range(len(t) - 1))


def _jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


#: 같은 이름의 후보가 여럿일 때 어느 기원을 먼저 쓸지. 위에 적힌 줄이 우선이고,
#: 한 줄 안의 키워드는 **전부** 포함돼야 그 순위로 인정한다.
#:
#: 키워드 부분일치로 판단하는 이유: 원본 표기가 "외식(재료량 기반 산출함량)"처럼
#: 길고 괄호·띄어쓰기가 섞여 있어서, 문자열을 통째로 적어두면 표기가 조금만
#: 달라져도 우선순위가 조용히 안 먹는다.
#:
#: 순서의 근거
#:   1. 외식 > 가정식 — 우리가 값을 붙이는 대상은 **식당에서 파는 음식**이다.
#:      라벨링에서도 사람이 같은 이름 중 외식 항목을 정답으로 골랐다
#:      (`족발`, `골뱅이무침_소면`).
#:   2. 분석함량 > 재료량 기반 산출함량 — 앞은 실제 시료를 측정한 값이고
#:      뒤는 레시피 재료량으로 계산한 추정값이다.
_ORIGIN_PRIORITY: tuple[tuple[str, ...], ...] = (
    ("외식", "분석"),   # 외식(분석함량)
    ("외식",),          # 외식(재료량 기반 산출함량) 등 나머지 외식
    ("분석",),          # 가정식(분석함량) 등 — 외식이 없을 때의 차선
)


def _origin_rank(origin: str) -> int:
    """기원 우선순위. 어느 줄에도 안 걸리면 맨 뒤로 보낸다."""
    text_lower = (origin or "").lower()
    for i, keywords in enumerate(_ORIGIN_PRIORITY):
        if all(k.lower() in text_lower for k in keywords):
            return i
    return len(_ORIGIN_PRIORITY)


def _basis_priority_key(c: "Candidate") -> tuple[int, int, str]:
    """동점 후보를 고를 때 100g·외식을 우선시키는 정렬 키.

    100g/100ml 양쪽에 같은 이름이 존재하는 629건(D-8 참고)에서, 여러 정렬
    지점(완전일치 사전 구성, 유사도 동점, 구조매칭 후보)이 전부 이 키로
    100g을 우선하도록 통일한다 — 흩어져 있으면 한 곳만 고치고 다른 곳을
    빠뜨리기 쉽다.

    같은 기준량 안에서는 **식품기원**이 다음 기준이다. 식약처 DB는 같은
    요리를 기원별로 중복 수록하는데, 이름만 봐서는 구분할 수 없어 예전에는
    사실상 food_code 순서(= 무작위)로 골랐다. 식당 메뉴에 붙일 값은 외식이다.
    """
    return (0 if c.serving_basis == "100g" else 1, _origin_rank(c.origin), c.food_code)


def load_excluded_brands(path: str | Path = DEFAULT_EXCLUDED_BRANDS_PATH) -> list[str]:
    """배제할 브랜드명 목록. 파일이 없으면 배제 없이 진행한다."""
    p = Path(path)
    if not p.exists():
        logger.warning("브랜드 배제 목록 없음 (%s) — 배제 없이 진행한다.", p)
        return []
    brands: list[str] = []
    with open(p, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            brand = (row.get("brand") or "").strip()
            if brand:
                brands.append(brand.lower())
    return brands


def _contains_brand(text_lower: str, brands: list[str]) -> bool:
    return any(b in text_lower for b in brands)


def _candidate_keys(normalized_name: str) -> list[tuple[str, bool]]:
    """(비교문자열, 포함매칭 허용여부) 목록.

    식약처 "A_B"는 "B라는 이름의 A"라는 뜻이다 — `볶음밥_새우`는 새우 요리가
    아니라 **새우볶음밥**이고, `김밥_소고기`는 소고기김밥이다. 마지막 조각만
    떼어 쓰면 재료명("새우", "소고기")이 요리명 행세를 하게 되고, 실제로
    `깐쇼새우`·`크림새우`가 전부 `볶음밥_새우`로 몰리는 오매칭이 났다.

    그래서 세 가지를 만든다:
      - 전체명 그대로
      - **B+A 결합형** (`볶음밥_새우` → `새우볶음밥`) — 이게 진짜 요리명
      - 마지막 조각 단독. 단 `냉면_물냉면`처럼 그 자체로 완전한 이름일 때만
        포함매칭에 쓰고, `볶음밥_새우`의 "새우"처럼 조각에 불과하면
        완전일치·편집거리에서만 쓰도록 막는다(두 번째 값 False).
    """
    if "_" not in normalized_name:
        return [(normalized_name, True)]

    parts = [p.strip() for p in normalized_name.split("_") if p.strip()]
    if len(parts) < 2:
        return [(normalized_name, True)]

    head, last = parts[0], parts[-1]
    keys: list[tuple[str, bool]] = [(normalized_name, True)]

    combined = f"{last}{head}"
    if combined != last:
        keys.append((combined, True))

    # 마지막 조각이 상위 분류를 이미 품고 있으면(물냉면 ⊃ 냉면) 완전한 요리명이다.
    keys.append((last, head in last))
    return keys


class Matcher:
    """official_food 전체를 메모리에 올려두고 메뉴명을 하나씩 매칭한다.

    후보가 1만여 건이라 통째로 올려도 부담이 없고, 메뉴 1,100건을 도는 동안
    DB를 반복 조회하지 않아도 된다.
    """

    def __init__(self, candidates: list[Candidate], excluded_rows: int = 0):
        self._candidates = candidates
        self.excluded_rows = excluded_rows

        # 완전일치용 사전. 같은 key에 여러 식품이 걸리면 100g 기준을 우선한다
        # (D-8 — 전부 100g 기준이라는 계약. 100g/100ml 양쪽에 같은 이름이
        # 있는 경우가 629건 있다 — 예: 갈비탕). 그다음은 food_code로 고정해
        # 실행할 때마다 결과가 바뀌지 않게 한다.
        self._exact: dict[str, Candidate] = {}
        for c in sorted(candidates, key=_basis_priority_key):
            self._exact.setdefault(c.key, c)

        # 2-gram 역색인. 퍼지 단계에서 비교 대상을 줄이는 용도.
        self._index: dict[str, list[int]] = defaultdict(list)
        for i, c in enumerate(candidates):
            for g in c.grams:
                self._index[g].append(i)

    @property
    def candidate_count(self) -> int:
        return len(self._candidates)

    def _shortlist(self, grams: frozenset[str]) -> list[tuple[float, Candidate]]:
        """2-gram을 하나라도 공유하는 후보만 모아 유사도 상위 N건을 돌려준다."""
        hit_counts: dict[int, int] = defaultdict(int)
        for g in grams:
            for i in self._index.get(g, ()):
                hit_counts[i] += 1

        scored: list[tuple[float, Candidate]] = []
        for i, _ in hit_counts.items():
            c = self._candidates[i]
            scored.append((_jaccard(grams, c.grams), c))

        scored.sort(key=lambda t: (-t[0], *_basis_priority_key(t[1])))
        return scored[:_SHORTLIST_SIZE]

    @staticmethod
    def _is_structural(menu_key: str, menu_tokens: frozenset[str], c: Candidate) -> bool:
        """**메뉴명이 식약처 이름을 품고 있을 때만** 같은 요리로 본다.

        방향을 한쪽으로 고정한 것이 핵심이다. 메뉴판 이름에는 수식어가 흔히
        붙지만 요리는 그대로다 — `왕갈비탕`·`화룡 양장피`·`대게살유산슬`은
        각각 갈비탕·양장피·유산슬이 맞다.

        반대로 식약처 쪽이 더 구체적이면 대개 **다른 요리**다. 양방향을
        허용했더니 `깐쇼새우 → 피자_깐쇼새우피자`, `칠리새우 → 버거_칠리새우
        버거`, `새우튀김 → 새우튀김롤`처럼 요리 형태가 통째로 바뀌는 오매칭이
        났다. 그런 건 여기서 떨어뜨리고 미매칭으로 두는 편이 낫다.
        """
        if (
            len(c.key) >= _MIN_CONTAIN_LEN
            and c.key in menu_key
            and len(c.key) / len(menu_key) >= _MIN_CONTAIN_RATIO
        ):
            return True
        if menu_tokens and c.tokens and c.tokens < menu_tokens:
            return True
        return False

    def top_candidates(self, normalized_name: str, limit: int = 10) -> list[Candidate]:
        """검색된 상위 후보를 판정 없이 그대로 돌려준다 (정답 라벨링·진단용).

        한 식품이 전체명·결합형·마지막조각 등 여러 key로 후보에 오르므로
        food_code 기준으로 중복을 없앤다 — 사람이 볼 목록에 같은 식품이
        세 번씩 나오면 고르기만 어려워진다.
        """
        if not normalized_name:
            return []

        seen: set[str] = set()
        out: list[Candidate] = []
        for _, c in self._shortlist(_bigrams(normalized_name)):
            if c.food_code in seen:
                continue
            seen.add(c.food_code)
            out.append(c)
            if len(out) >= limit:
                break
        return out

    def match(
        self, normalized_name: str, allow_ngram: bool = True
    ) -> tuple[Candidate, str] | None:
        """캐스케이드 1회 실행. (후보, 매칭방법) 또는 None.

        allow_ngram=False면 마지막 n-gram 단계를 건너뛴다. 브랜드 전용 매칭처럼
        후보가 수십 건뿐일 때 쓴다 — 풀이 작으면 글자만 겹치는 아무 항목이나
        상대적으로 높은 자카드 점수를 받아서, 없는 메뉴가 억지로 매칭된다.
        """
        if not normalized_name:
            return None

        # 1) 완전일치
        hit = self._exact.get(normalized_name)
        if hit is not None:
            return hit, "EXACT"

        grams = _bigrams(normalized_name)
        tokens = frozenset(t for t in normalized_name.split() if t)
        shortlist = self._shortlist(grams)
        if not shortlist:
            return None

        # 2) 편집거리 — 띄어쓰기·오타 수준의 미세한 불일치
        flat_name = normalized_name.replace(" ", "")
        best_edit: tuple[float, Candidate] | None = None
        for _, c in shortlist:
            ratio = SequenceMatcher(None, flat_name, c.flat).ratio()
            if ratio >= _EDIT_THRESHOLD and (best_edit is None or ratio > best_edit[0]):
                best_edit = (ratio, c)
        if best_edit is not None:
            return best_edit[1], "EDIT"

        # 3) 구조매칭 — 포함 관계. 여러 개면 가장 짧은(= 군더더기 적은) 쪽
        structural = [
            c
            for _, c in shortlist
            if c.allow_contain and self._is_structural(normalized_name, tokens, c)
        ]
        if structural:
            structural.sort(key=lambda c: (len(c.key), *_basis_priority_key(c)))
            return structural[0], "STRUCT"

        # 4) n-gram — 위 세 단계가 다 놓친 것 중 글자 겹침이 충분한 1건
        if not allow_ngram:
            return None
        for score, candidate in shortlist:
            if score < _NGRAM_THRESHOLD:
                break
            if candidate.allow_contain:
                return candidate, "NGRAM"

        return None


_SELECT_OFFICIAL_FOOD = text(
    "SELECT food_code, food_name, normalized_name, company_name, serving_basis, "
    "major_category, origin FROM official_food"
)


def _to_candidates(
    food_code, food_name, normalized_name, serving_basis, major_category, origin
) -> list[Candidate]:
    """식약처 1행 → 비교용 Candidate 여러 개. 일반 풀과 브랜드 풀이 공유한다."""
    return [
        Candidate(
            food_code=str(food_code),
            food_name=str(food_name),
            key=key,
            flat=key.replace(" ", ""),
            tokens=frozenset(t for t in key.split() if t),
            grams=_bigrams(key),
            allow_contain=allow_contain,
            serving_basis=str(serving_basis) if serving_basis else "100g",
            major_category=str(major_category) if major_category else "",
            origin=str(origin) if origin else "",
        )
        for key, allow_contain in _candidate_keys(normalized_name)
    ]


def detect_brand(restaurant_name: str, brands: list[str]) -> str | None:
    """식당 이름에 들어 있는 브랜드를 찾는다. 여러 개 걸리면 가장 긴 것.

    짧은 쪽을 고르면 엉뚱한 브랜드의 메뉴판으로 매칭하게 된다 — 목록에
    `버거킹`과 `버거`가 함께 있으면 "버거킹 가재울점"이 `버거`로 잡히는 식이다.
    """
    lowered = restaurant_name.lower()
    hits = [b for b in brands if b and b in lowered]
    return max(hits, key=len) if hits else None


def build_brand_matchers(
    session: Session,
    brands: list[str],
    wanted: set[str] | None = None,
) -> dict[str, Matcher]:
    """브랜드별 전용 Matcher. 후보를 **그 브랜드 제품으로만** 좁힌다.

    프랜차이즈는 식약처 데이터가 가장 정확한 영역이다(문서 §8). 그런데 일반
    후보 풀에서는 이 항목들이 통째로 배제돼 있어서(브랜드 제품이 동네 식당
    메뉴에 잘못 붙는 걸 막기 위함), 프랜차이즈 매장 메뉴는 그대로 두면 오히려
    엉뚱한 일반 요리에 붙는다. 그래서 "같은 브랜드끼리만" 보는 풀을 따로 만든다.

    wanted를 주면 그 브랜드만 만든다 — 우리 식당에 없는 브랜드까지 매처를
    만들 이유가 없다.
    """
    targets = [b for b in brands if b and (wanted is None or b in wanted)]
    if not targets:
        return {}

    buckets: dict[str, list[Candidate]] = {b: [] for b in targets}
    for (
        food_code,
        food_name,
        normalized_name,
        company_name,
        serving_basis,
        major_category,
        origin,
    ) in session.execute(_SELECT_OFFICIAL_FOOD).all():
        if not normalized_name or not company_name:
            continue
        company_lower = str(company_name).lower()
        for brand in targets:
            if brand in company_lower:
                buckets[brand].extend(
                    _to_candidates(
                        food_code, food_name, normalized_name,
                        serving_basis, major_category, origin,
                    )
                )

    matchers = {b: Matcher(c) for b, c in buckets.items() if c}
    for brand in targets:
        if brand not in matchers:
            logger.info("브랜드 '%s'는 식약처에 항목이 없다 — 일반 매칭도 하지 않는다", brand)
    logger.info(
        "브랜드 전용 매처 %d개 생성 (후보 %d건)",
        len(matchers), sum(m.candidate_count for m in matchers.values()),
    )
    return matchers


@dataclass
class MatcherSet:
    """식당 종류에 따라 일반 풀/브랜드 풀로 갈라 보내는 매처 묶음.

    이 분기가 여러 곳(집계·라벨링·LLM)에 흩어지면, 한 곳만 고쳤을 때 "규칙이
    매칭했다고 보는 메뉴"의 정의가 서로 달라진다. 그러면 LLM이 이미 매칭된
    프랜차이즈 메뉴를 다시 물어보고 덮어쓰는 사고가 난다. 그래서 판단을
    여기 한 곳에 모은다.
    """

    general: Matcher
    brand_matchers: dict[str, Matcher]
    brands: list[str]

    def brand_of(self, restaurant_name: str) -> str | None:
        return detect_brand(str(restaurant_name), self.brands) if self.brands else None

    def match(
        self, normalized_name: str, restaurant_name: str
    ) -> tuple[Candidate, str] | None:
        """식당이 프랜차이즈면 그 브랜드 항목 안에서만, 아니면 일반 풀에서 찾는다."""
        brand = self.brand_of(restaurant_name)
        if brand is None:
            return self.general.match(normalized_name)

        matcher = self.brand_matchers.get(brand)
        if matcher is None:
            return None
        # n-gram은 끈다 — 후보가 수십 건뿐이라 글자만 겹쳐도 점수가 높게 나온다.
        hit = matcher.match(normalized_name, allow_ngram=False)
        return (hit[0], _BRAND_METHOD[hit[1]]) if hit is not None else None

    def top_candidates(
        self, normalized_name: str, restaurant_name: str, limit: int = 10
    ) -> list[Candidate]:
        """사람·LLM에게 보여줄 후보. 매칭과 같은 풀에서 뽑아야 판단이 일치한다."""
        brand = self.brand_of(restaurant_name)
        if brand is None:
            return self.general.top_candidates(normalized_name, limit=limit)
        matcher = self.brand_matchers.get(brand)
        return matcher.top_candidates(normalized_name, limit=limit) if matcher else []


def build_matcher_set(
    session: Session,
    brands: list[str],
    restaurant_names: list[str],
) -> MatcherSet:
    """일반 매처 + (우리 식당에 실제로 있는) 브랜드 매처를 한 번에 만든다."""
    general = build_matcher(session, excluded_brands=brands)
    wanted = {
        brand
        for name in restaurant_names
        if (brand := detect_brand(str(name), brands)) is not None
    } if brands else set()
    return MatcherSet(
        general=general,
        brand_matchers=build_brand_matchers(session, brands, wanted),
        brands=brands,
    )


def build_matcher(
    session: Session,
    excluded_brands: list[str] | None = None,
) -> Matcher:
    """official_food를 읽어 Matcher를 만든다.

    브랜드(프랜차이즈) 배제는 `excluded_brands.csv`에 명시된 브랜드만 대상으로
    한다. `company_name`이 채워진 항목 전체(13,755건 중 93%)를 배제하는
    방식도 시도했으나, 의도한 범위(스타벅스·롯데리아 등 명시적으로 지정한
    브랜드)를 훨씬 넘어서서 정상적인 매칭까지 대량으로 걷어냈다 — 되돌림.
    """
    brands = excluded_brands if excluded_brands is not None else load_excluded_brands()

    rows = session.execute(_SELECT_OFFICIAL_FOOD).all()

    candidates: list[Candidate] = []
    excluded_rows = 0
    for (
        food_code,
        food_name,
        normalized_name,
        company_name,
        serving_basis,
        major_category,
        origin,
    ) in rows:
        if not normalized_name:
            continue
        # 브랜드는 food_name 문자열 추측이 아니라 원본 업체명 컬럼으로
        # 판단한다 — "커피_바닐라 라떼 (Tall)"처럼 이름만 봐선 어느 브랜드인지
        # 알 수 없는 항목이 많아서, 이름 기반 배제는 초기에 8행밖에 못 걸렀었다.
        if brands and company_name and _contains_brand(str(company_name).lower(), brands):
            excluded_rows += 1
            continue
        candidates.extend(
            _to_candidates(
                food_code, food_name, normalized_name,
                serving_basis, major_category, origin,
            )
        )

    logger.info(
        "official_food %d행 → 후보 %d건 (브랜드 배제 %d행)",
        len(rows), len(candidates), excluded_rows,
    )
    return Matcher(candidates, excluded_rows=excluded_rows)


#: 식당명·cuisine까지 같이 읽는다 — 프랜차이즈(exclude_franchise)는 식당
#: 이름으로, 카페(exclude_cafe)는 cuisine으로 판단하기 때문.
_SELECT_MENUS = text("""
    SELECT m.id, m.name, m.normalized_name, r.name AS restaurant_name, r.cuisine
    FROM menu m
    JOIN restaurant r ON r.id = m.restaurant_id
    ORDER BY m.id
""")

#: D-8 범위상 음료(100ml 기준)는 official_food에 없어(Step2에서 제외)
#: 카페 메뉴는 애초에 매칭될 수가 없다. 매칭률 집계에서 이 사실이 숫자를
#: 깎아먹는 걸 분리해서 보고 싶을 때 쓰는 분석용 옵션.
_CAFE_CUISINE = "CAFE_DESSERT"

#: "○○ 명지대점"처럼 지점명으로 끝나는 식당. 한국 프랜차이즈의 지점 작명
#: 관례라, 브랜드를 하나씩 등록하는 excluded_brands.csv보다 훨씬 넓게 잡힌다.
#: 다만 "본점"을 쓰는 개인 식당도 걸리므로, 제외된 식당 목록을 로그에 남겨
#: 사람이 오탐을 확인할 수 있게 한다.
_BRANCH_SUFFIX = re.compile(r"점\s*$")

#: 매칭 결과를 menu에 반영한다. 영양 수치는 전부 official_food의 100g당 값을
#: 그대로 복사한다(D-8 — 1인분 환산 없음). nutrition_source는 식약처 원본이라
#: 항상 OFFICIAL.
_UPDATE_MENU = text("""
    UPDATE menu m
    JOIN official_food f ON f.food_code = :food_code
    SET m.nutrition_calories     = f.calories,
        m.nutrition_carbohydrate = f.carbohydrate,
        m.nutrition_protein      = f.protein,
        m.nutrition_fat          = f.fat,
        m.nutrition_sodium       = f.sodium,
        m.official_food_code     = f.food_code,
        m.matched_by             = :matched_by,
        m.nutrition_confidence   = :confidence,
        m.nutrition_source       = 'OFFICIAL'
    WHERE m.id = :menu_id
""")


def run_match(
    session: Session,
    apply: bool = False,
    sample_size: int = 20,
    exclude_franchise: bool = False,
    exclude_cafe: bool = False,
    exclude_branch: bool = False,
) -> tuple[MatchReport, list[MatchResult]]:
    """전체 메뉴에 캐스케이드를 돌린다.

    apply=False면 DB를 건드리지 않고 집계만 한다 (Step 3 실측용).

    exclude_franchise=True면 `excluded_brands.csv`의 브랜드가 이름에 들어간
    **식당**의 메뉴를 통째로 건너뛴다. 매칭 품질을 눈으로 확인할 때 프랜차이즈
    메뉴가 결과를 뒤덮는 걸 막는 분석용 옵션이며, 실제 서비스에서 프랜차이즈를
    뺄지는 별개의 제품 결정이다.

    exclude_cafe=True면 cuisine이 CAFE_DESSERT인 식당의 메뉴를 통째로
    건너뛴다. official_food는 음료(100ml 기준)를 애초에 안 담고 있어서(D-8),
    카페 메뉴는 정규화·매칭을 아무리 잘 짜도 구조적으로 매칭될 수 없다 —
    이걸 섞어서 보면 "일반 식당 메뉴 매칭이 잘 되는지"가 안 보인다.

    exclude_branch=True면 이름이 "~점"으로 끝나는 식당을 건너뛴다. 프랜차이즈
    지점 작명 관례를 이용한 것이라 브랜드 목록보다 넓게 잡힌다.
    """
    brands = load_excluded_brands()
    menu_rows = session.execute(_SELECT_MENUS).all()

    # 프랜차이즈를 통째로 빼는 분석 모드에서는 브랜드 매처를 만들 이유가 없다.
    matcher_set = build_matcher_set(
        session,
        brands,
        [] if exclude_franchise else [str(r[3]) for r in menu_rows],
    )

    report = MatchReport(
        total_candidates=matcher_set.general.candidate_count,
        excluded_rows=matcher_set.general.excluded_rows,
    )
    results: list[MatchResult] = []
    branch_names: set[str] = set()

    for menu_id, name, normalized_name, restaurant_name, cuisine in menu_rows:
        if exclude_franchise and brands and _contains_brand(str(restaurant_name).lower(), brands):
            report.excluded_menus += 1
            continue
        if exclude_branch and _BRANCH_SUFFIX.search(str(restaurant_name)):
            report.excluded_branch_menus += 1
            branch_names.add(str(restaurant_name))
            continue
        if exclude_cafe and cuisine == _CAFE_CUISINE:
            report.excluded_cafe_menus += 1
            continue

        report.total_menus += 1
        result = MatchResult(
            menu_id=menu_id, menu_name=name, normalized_name=normalized_name or ""
        )

        is_brand_menu = matcher_set.brand_of(restaurant_name) is not None
        if is_brand_menu:
            report.brand_menus += 1
        hit = matcher_set.match(result.normalized_name, str(restaurant_name))

        if hit is None:
            if is_brand_menu:
                report.brand_unmatched_names.append(result.normalized_name)
            else:
                report.unmatched_names.append(result.normalized_name)
        else:
            candidate, method = hit
            result.food_code = candidate.food_code
            result.food_name = candidate.food_name
            result.matched_by = method
            result.confidence = CONFIDENCE[method]
            report.by_method[method] = report.by_method.get(method, 0) + 1

            if apply:
                session.execute(
                    _UPDATE_MENU,
                    {
                        "food_code": candidate.food_code,
                        "matched_by": method,
                        "confidence": CONFIDENCE[method],
                        "menu_id": menu_id,
                    },
                )

        results.append(result)

    report.excluded_branch_restaurants = sorted(branch_names)
    return report, results


_SELECT_RESTAURANTS = text("""
    SELECT r.name, r.cuisine, COUNT(m.id) AS menu_count
    FROM restaurant r
    LEFT JOIN menu m ON m.restaurant_id = r.id
    GROUP BY r.id, r.name, r.cuisine
    ORDER BY r.name
""")


def _guess_brand(restaurant_name: str) -> str:
    """"롯데리아 명지대점" → "롯데리아". 지점 표기를 떼어 브랜드만 남긴다.

    띄어쓰기가 없으면("스타벅스명지대점") 어디까지가 브랜드인지 알 수 없어
    빈 값을 돌려준다 — 잘못 추정해서 채워두면 사람이 그대로 승인해버릴
    위험이 있으므로, 모르면 비워두고 직접 적게 한다.
    """
    parts = restaurant_name.split()
    if len(parts) >= 2 and _BRANCH_SUFFIX.search(parts[-1]):
        return " ".join(parts[:-1])
    return ""


def export_branch_restaurants(session: Session, output_path: str | Path) -> int:
    """이름이 "~점"으로 끝나는 식당을 검토용 CSV로 내보낸다.

    `~점` 규칙은 프랜차이즈를 넓게 잡아주지만 "본점"을 쓰는 개인 식당도 걸린다.
    그래서 이 목록을 그대로 배제에 쓰지 않고, 사람이 확인한 브랜드만
    excluded_brands.csv로 옮겨 쓰기 위한 중간 산출물이다.
    """
    rows = [
        (name, cuisine, menu_count)
        for name, cuisine, menu_count in session.execute(_SELECT_RESTAURANTS).all()
        if _BRANCH_SUFFIX.search(str(name))
    ]

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["식당명", "cuisine", "메뉴수", "브랜드(추정)", "프랜차이즈여부"])
        for name, cuisine, menu_count in rows:
            writer.writerow([name, cuisine, menu_count, _guess_brand(str(name)), ""])

    logger.info("지점명(~점) 식당 %d곳을 검토용으로 내보냄: %s", len(rows), out)
    return len(rows)


def _labelled_food_name(c: "Candidate") -> str:
    """사람·LLM에게 보여줄 후보 표기. 이름만으로 구분되지 않는 정보를 덧붙인다."""
    parts = [p for p in (c.origin, c.major_category) if p]
    return f"{c.food_name} [{' · '.join(parts)}]" if parts else c.food_name


def load_previous_answers(path: str | Path) -> dict[str, str]:
    """이전 라벨링 CSV의 '정답'을 **정규화명 → 안정적 표현**으로 읽는다.

    번호(1~10)를 그대로 옮기면 안 된다. 후보 목록은 정규화 규칙이나 데이터가
    바뀌면 순서가 통째로 달라져서, `3`이 어제와 다른 음식을 가리키게 된다.
    그래서 번호는 **그 번호가 가리키던 food_code로 바꿔서** 들고 있는다.
    이렇게 해두면 새 시트에서 그 음식이 몇 번이 되든 정확히 다시 찾아낼 수 있다.

    반환값은 `"0"`(정답 없음), `"제외"`, 또는 food_code 셋 중 하나다.
    """
    p = Path(path)
    if not p.exists():
        return {}

    answers: dict[str, str] = {}
    with open(p, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            raw = (row.get("정답") or "").strip()
            key = (row.get("정규화명") or "").strip()
            if not raw or not key:
                continue

            if raw in _EXCLUDE_TOKENS:
                answers[key] = "제외"
            elif raw == "0" or _FOOD_CODE_PATTERN.match(raw):
                # 0(DB에 없음)과 food_code는 후보 순서와 무관하게 의미가 유지된다.
                answers[key] = "0" if raw == "0" else raw
            elif raw.isdigit():
                code = (row.get(f"코드{int(raw)}") or "").strip()
                if code:
                    answers[key] = code
    return answers


def _backup_label_sheet(path: Path) -> Path | None:
    """덮어쓰기 전에 사본을 남긴다.

    실제로 라벨링 50건이 재실행 한 번에 통째로 날아간 적이 있다. 병합
    로직이 있어도, 사람 손이 들어간 파일을 되돌릴 수 없게 지우는 일은
    없어야 한다.
    """
    if not path.exists():
        return None
    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = path.with_name(f"{path.stem}_backup_{timestamp}{path.suffix}")
    shutil.copy2(path, backup)
    return backup


def export_label_sheet(
    session: Session,
    output_path: str | Path,
    sample_size: int = 50,
    candidate_count: int = 10,
    exclude_franchise: bool = False,
    exclude_cafe: bool = False,
    exclude_branch: bool = False,
    seed: int = 42,
    keep_answers: bool = True,
) -> int:
    """규칙 단계에서 못 잡은 메뉴 중 표본을 뽑아 정답 라벨링용 CSV로 내보낸다.

    사람이 채워야 할 칸은 `정답` 하나뿐이다. 후보를 미리 붙여두는 이유는
    식약처 DB 1만여 건에서 직접 찾게 하면 라벨링이 끝나지 않기 때문이다.

    표본은 seed 고정 난수로 뽑는다 — 같은 데이터·같은 seed면 항상 같은 50건이
    나와야 모델을 바꿔가며 비교할 때 조건이 유지된다.

    keep_answers=True(기본)면 **기존 파일의 라벨을 이어받는다.** 사람이 채운
    칸은 이 파이프라인에서 가장 비싼 자산이라, 재실행 한 번으로 날아가면 안
    된다. 덮어쓰기 전 사본도 함께 남긴다.
    """
    brands = load_excluded_brands()
    menu_rows = session.execute(_SELECT_MENUS).all()
    matcher_set = build_matcher_set(
        session,
        brands,
        [] if exclude_franchise else [str(r[3]) for r in menu_rows],
    )

    unmatched: list[tuple[str, str, str]] = []  # (원본명, 정규화명, 식당명)
    for _, name, normalized_name, restaurant_name, cuisine in menu_rows:
        if exclude_franchise and brands and _contains_brand(str(restaurant_name).lower(), brands):
            continue
        if exclude_branch and _BRANCH_SUFFIX.search(str(restaurant_name)):
            continue
        if exclude_cafe and cuisine == _CAFE_CUISINE:
            continue
        if not normalized_name:
            continue
        # 프랜차이즈 매장 메뉴는 라벨링 표본에 넣지 않는다. 이 시트의 목적은
        # "일반 요리 매칭을 어디까지 개선할 수 있나"를 재는 것인데, 브랜드
        # 메뉴는 그 브랜드 항목 유무만으로 결론이 나서 섞이면 비율만 흐려진다.
        if matcher_set.brand_of(restaurant_name) is not None:
            continue
        if matcher_set.match(normalized_name, str(restaurant_name)) is None:
            unmatched.append((name, normalized_name, restaurant_name))

    rng = random.Random(seed)
    sample = rng.sample(unmatched, min(sample_size, len(unmatched)))

    header = ["번호", "메뉴명", "정규화명", "식당명", "정답"]
    header += [f"후보{i}" for i in range(1, candidate_count + 1)]
    header += [f"코드{i}" for i in range(1, candidate_count + 1)]

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    previous = load_previous_answers(out) if keep_answers else {}
    backup = _backup_label_sheet(out)
    if backup is not None:
        logger.info("기존 파일 사본 저장: %s", backup)

    carried = 0
    # utf-8-sig — Excel이 BOM 없는 UTF-8 CSV를 열면 한글이 깨진다.
    with open(out, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        for i, (name, normalized_name, restaurant_name) in enumerate(sample, start=1):
            candidates = matcher_set.top_candidates(
                normalized_name, str(restaurant_name), limit=candidate_count
            )
            # 기원(외식/가정식)을 이름 옆에 붙인다. 같은 요리가 기원별로 중복
            # 수록돼 있어, 이게 없으면 사람이 후보 1번과 2번의 차이를 알 수 없다.
            names = [_labelled_food_name(c) for c in candidates]
            codes = [c.food_code for c in candidates]

            answer = ""
            saved = previous.get(normalized_name)
            if saved:
                carried += 1
                if saved in ("0", "제외"):
                    answer = saved
                elif saved in codes:
                    # 그 음식이 이번 후보 목록에서 몇 번인지 다시 계산한다.
                    answer = str(codes.index(saved) + 1)
                else:
                    # 후보 밖으로 밀려났다 — food_code 그대로 두면 채점이
                    # "검색 recall 실패"로 정확히 집계한다.
                    answer = saved

            # 후보가 candidate_count보다 적을 수 있어 빈칸으로 채운다.
            names += [""] * (candidate_count - len(names))
            codes += [""] * (candidate_count - len(codes))
            writer.writerow(
                [i, name, normalized_name, restaurant_name, answer] + names + codes
            )

    logger.info("미매칭 %d건 중 %d건을 라벨링용으로 내보냄: %s", len(unmatched), len(sample), out)
    if previous:
        logger.info(
            "이전 라벨 %d건 중 %d건을 이어받음 (나머지는 이번 표본에 없는 메뉴)",
            len(previous), carried,
        )
    return len(sample)


_SELECT_OFFICIAL_FOOD_LIKE = text("""
    SELECT food_code, food_name, normalized_name, company_name, serving_basis, origin
    FROM official_food
    WHERE normalized_name LIKE :pattern OR food_name LIKE :pattern
    ORDER BY normalized_name
    LIMIT :limit
""")


def find_food(
    session: Session, keyword: str, limit: int = 30
) -> list[tuple[str, str, str, str, str, str]]:
    """official_food를 이름 부분일치로 조회한다.

    라벨링 중 "이 요리가 식약처에 진짜 없는지"를 확인하는 용도다 — 정답 후보
    10개 밖에 있는 것과 애초에 존재하지 않는 것을 구분해야 recall을 믿을 수
    있다. normalized_name과 food_name(밑줄 포함 원본) 양쪽을 다 뒤진다 —
    "짜장"을 찾을 때 정규화 전 표기(`라면_짜장라면`)까지 걸리게 하기 위함.
    serving_basis도 같이 보여준다 — 100ml 요리 포함(Phase 0) 이후로 같은
    이름이 100g/100ml 양쪽에 있을 수 있어, 어느 쪽이 매칭에 쓰이는지(100g
    우선) 확인할 수 있어야 한다. 식품기원(외식/가정식)도 함께 보여준다 —
    같은 이름이 기원별로 중복 수록돼 있어, 이걸 안 보면 사람이 라벨링할 때
    어느 쪽을 골라야 하는지 알 수 없다.
    """
    pattern = f"%{keyword}%"
    rows = session.execute(
        _SELECT_OFFICIAL_FOOD_LIKE, {"pattern": pattern, "limit": limit}
    ).all()
    return [
        (
            str(a), str(b), str(c),
            str(d) if d else "", str(e) if e else "", str(f) if f else "",
        )
        for a, b, c, d, e, f in rows
    ]


#: '정답' 칸에 이 값들 중 하나를 쓰면 "애초에 매칭 대상이 아님"으로 처리한다.
#: `0`(식약처에 정답이 없음 — 매칭 시도는 유효했지만 실패)과는 다른 의미다.
#: 콤보/세트 메뉴("짬뽕+군만두"), 주류("참이슬 후레쉬"), 깨진 문자열처럼
#: "이 행 자체가 애초에 요리 매칭 문제가 아닌" 경우를 표시한다. 이런 항목이
#: 채점 분모에 섞이면 매칭 성능(정답 있음/해당없음 비율)이 실제보다 낮아
#: 보이게 된다.
_EXCLUDE_TOKENS = {"제외", "x", "X"}

#: '정답' 칸에 food_code를 직접 적으면 "DB엔 있는데 후보 10개 안에 없었다"는
#: 뜻이다. `find_food`로 찾아낸 경우가 이 케이스다 — `0`(DB에 아예 없음)과
#: 전혀 다른 신호로, 검색(2-gram 후보 추리기)의 recall 실패를 보여준다.
#: 식약처 food_code는 전부 "문자+숫자-숫자-..." 형태라 하이픈 유무로 숫자
#: 1~10과 구분한다.
_FOOD_CODE_PATTERN = re.compile(r"^[A-Za-z]\d+(-\d+)+$")


@dataclass
class LabelScore:
    total_rows: int = 0
    unlabeled: int = 0
    invalid: list[tuple[int, str]] = field(default_factory=list)  # (번호, 잘못된 값)
    excluded: list[tuple[int, str]] = field(default_factory=list)  # (번호, 메뉴명)
    recall_miss: list[tuple[int, str]] = field(default_factory=list)  # (번호, food_code)
    no_match: int = 0          # 정답 = 0
    rank1: int = 0             # 정답이 후보 1번
    rank_le3: int = 0          # 정답이 후보 1~3번
    rank_le10: int = 0         # 정답이 후보 1~10번 (= 라벨링된 것 중 매칭 있음 전체)

    @property
    def labeled(self) -> int:
        """실제 매칭 성능 채점에 들어가는 건수. 제외 표시된 행은 빼야 비율이
        왜곡되지 않는다 — 애초에 요리가 아닌 걸 '해당없음'에 섞으면 실제
        매칭 성능보다 나빠 보인다."""
        return self.total_rows - self.unlabeled - len(self.invalid) - len(self.excluded)

    @property
    def exists_in_db(self) -> int:
        """DB에 정답이 실제로 존재하는 건수 (후보 안에 있었든 밖에 있었든).
        이게 매칭률의 이론적 상한이다."""
        return self.rank_le10 + len(self.recall_miss)

    def summary(self, candidate_count: int) -> str:
        if self.labeled == 0:
            return "라벨링된 행이 없다 ('정답' 칸이 전부 비어있음)."

        exists_rate = self.exists_in_db / self.labeled * 100
        no_match_rate = self.no_match / self.labeled * 100
        recall_at_n = (self.rank_le10 / self.exists_in_db * 100) if self.exists_in_db else 0.0
        lines = [
            f"라벨링 {self.labeled}건 (전체 {self.total_rows}건 중 미기입 {self.unlabeled}건"
            + (f", 제외 {len(self.excluded)}건" if self.excluded else "")
            + (f", 잘못된 값 {len(self.invalid)}건" if self.invalid else "")
            + ")",
            f"DB에 정답 존재(이론적 상한): {self.exists_in_db}건 ({exists_rate:.1f}%)",
            f"  - 후보 {candidate_count}개 안에서 찾음(recall@{candidate_count}): "
            f"{self.rank_le10}건 ({recall_at_n:.1f}%)",
            f"      1위: {self.rank1}건 / 상위 3위 이내: {self.rank_le3}건",
            f"  - 후보 밖에 있었음(검색 recall 실패): {len(self.recall_miss)}건",
            f"해당없음(0 — official_food에 정답 없음): {self.no_match}건 ({no_match_rate:.1f}%)",
        ]
        if self.recall_miss:
            lines.append("후보 밖에서 찾은 정답 (검색 개선 필요 신호):")
            for i, code in self.recall_miss:
                lines.append(f"    번호 {i}: {code}")
        if self.excluded:
            lines.append("제외 표시된 항목 (매칭 대상 자체가 아님 — 채점에서 뺌):")
            for i, name in self.excluded:
                lines.append(f"    번호 {i}: {name}")
        if self.invalid:
            lines.append("잘못된 '정답' 값 (숫자도 food_code 형태도 아님):")
            for i, value in self.invalid:
                lines.append(f"    번호 {i}: {value!r}")
        return "\n".join(lines)


def score_label_sheet(input_path: str | Path, candidate_count: int = 10) -> LabelScore:
    """`export_label_sheet`로 만든 CSV에 사람이 채운 '정답' 칸을 채점한다.

    '정답' 칸에 넣을 수 있는 값:
      - `1`~`candidate_count`: 후보 안에 정답이 있음 (recall 성공)
      - `0`: `find_food`로 찾아봐도 official_food에 정답이 없음 (DB 커버리지 한계)
      - food_code (예: `D101-018430000-0001`): `find_food`로 이름 검색해 찾아낸,
        **후보 10개 밖**의 정답. `0`과 전혀 다른 신호다 — DB엔 있는데 후보
        추리기(2-gram 검색)가 놓친 것이라, 검색 알고리즘 개선이 필요하다는 뜻
      - `제외`/`x`: 콤보 메뉴·주류처럼 애초에 매칭 대상이 아닌 행 (채점 분모에서 제외)
    """
    score = LabelScore()
    with open(input_path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            score.total_rows += 1
            raw = (row.get("정답") or "").strip()
            if not raw:
                score.unlabeled += 1
                continue

            if raw in _EXCLUDE_TOKENS:
                score.excluded.append((int(row["번호"]), row.get("메뉴명", "")))
                continue

            try:
                answer = int(raw)
            except ValueError:
                # 숫자가 아니면 food_code("D101-...")를 직접 적은 것으로 본다.
                # find-food로 이름 검색해 찾아낸, 후보 10개 밖의 정답이다.
                if _FOOD_CODE_PATTERN.match(raw):
                    score.recall_miss.append((int(row["번호"]), raw))
                else:
                    score.invalid.append((int(row["번호"]), raw))
                continue

            if answer == 0:
                score.no_match += 1
            elif 1 <= answer <= candidate_count:
                score.rank_le10 += 1
                if answer <= 3:
                    score.rank_le3 += 1
                if answer == 1:
                    score.rank1 += 1
            else:
                score.invalid.append((int(row["번호"]), raw))

    return score
