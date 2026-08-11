"""정규화 — AI 미사용, 규칙만으로 RawRestaurant를 다듬는다.

식당 1건 처리 실패는 그 식당만 건너뛰고 나머지는 계속 진행한다(격리 원칙).
"""

from __future__ import annotations

import csv
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from app.model.raw import RawMenu, RawRestaurant

#: menu 테이블 cuisine 컬럼이 NOT NULL 이라, 매핑 실패 시 그 식당은 반드시
#: 건너뛴다(ETC로 임의 대체하지 않는다 — 잘못된 분류가 조용히 섞이는 것을 막는다).
VALID_CUISINE = {
    "KOREAN", "CHINESE", "JAPANESE", "WESTERN",
    "ASIAN", "SNACK", "CAFE_DESSERT", "ETC",
}

#: 끝에 붙은 한자 사이즈 표기. 공백 없이도 붙는다 (예: "팔보채小").
_TRAILING_HANJA_SIZE = re.compile(r"(大|中|小)\s*$")

#: 끝에 별도 단어로 떨어진 한글 사이즈/접미 표기만 제거한다.
#: "대게살유산슬"처럼 단어 중간·시작에 낀 "대"는 절대 건드리지 않는다.
_TRAILING_KOREAN_MODIFIER = re.compile(
    r"\s*\(?\s*(대|중|소|곱빼기|곱배기|특대|왕|정식|세트|한상|특|스페셜)\s*\)?\s*$"
)

#: 끝에 붙은 중량·수량 표기 ("180g", "500g", "5p", "2인분" 등).
#: 식약처 DB가 100g 기준이라(D-8) 중량 자체는 매칭에 무의미한 잡음이다.
_TRAILING_QUANTITY = re.compile(
    r"\s*\d+\s*(g|kg|ml|l|p|개|인분|인)\s*$", re.IGNORECASE
)

#: 메뉴명 어디에 섞여 있든 지우는 한자. 한국 메뉴판의 한자는 거의 항상
#: 사이즈 표기(大/中/小 — _TRAILING_HANJA_SIZE가 이미 처리)나 홍보성 수식어
#: ("麻辣" 등)라 지워도 요리명이 훼손되지 않는다. 실제로 "마라麻辣짜장"처럼
#: 끝이 아니라 단어 중간에 낀 경우가 있어 위치 무관하게 지운다.
_HANJA = re.compile(r"[一-鿿]+")

#: 슬래시는 표기 변형 구분자로 쓰인다("알/곤이찜" = "알곤이찜"). 단어를
#: 나누는 의미가 아니라 지워도 뜻이 안 바뀌므로 공백이 아니라 완전히 없앤다.
_SLASH = re.compile(r"/")

#: 여는 괄호 없이 닫는 괄호만 남은 경우 등, 균형이 안 맞아 _BRACKET_CONTENT가
#: 못 지운 괄호 문자. 내용이 아니라 문자 자체만 제거한다(균형 잡힌 괄호는
#: 이미 내용째로 지워졌으므로 이 시점에 남은 괄호 문자는 전부 미스매치다).
_STRAY_BRACKET_CHARS = re.compile(r"[()\[\]【】《》〈〉]")

#: 파싱 실패로 원문에 섞여 들어온 개행·탭 등 제어문자
_CONTROL_CHARS = re.compile(r"[\r\n\t]+")
_MULTI_SPACE = re.compile(r"\s{2,}")

#: 메뉴명 양끝을 두른 장식 기호("++ 환타 오렌지 추가 ++", "**신메뉴**").
#: 이걸 안 지우면 이름이 `추가`가 아니라 `++`로 끝나서, 추가주문 항목을
#: 걸러내는 `_SET_OR_COURSE_LIKE`가 통과시켜 버린다 — 실제로 음료 추가
#: 항목들이 이 구멍으로 메뉴에 적재됐다.
_DECORATIVE_EDGE = re.compile(r"^[\s+*~=#\-·※]+|[\s+*~=#\-·※]+$")

#: 괄호(반각/전각)로 감싼 내용은 위치(시작·중간·끝) 무관하게 통째로 제거한다.
#: 한국 메뉴판에서 괄호는 거의 항상 부가설명("음료 추가", "2인분 기준", 홍보문구
#: 등)이지 요리명 자체가 아니다. "대게살유산슬"처럼 괄호 없이 단어 중간에 낀
#: 글자와 달리, 괄호 안 내용은 작성자가 스스로 "부가정보"라고 표시해둔 것이라
#: 지워도 요리명이 훼손되지 않는다. [[이중대괄호]]처럼 중첩된 경우를 위해
#: 변화가 없을 때까지 반복 적용한다.
_BRACKET_CONTENT = re.compile(
    r"\([^()]*\)"
    r"|\[[^\[\]]*\]"
    r"|【[^【】]*】"
    r"|《[^《》]*》"
    r"|〈[^〈〉]*〉"
)

#: 메뉴명이 아니라 식당 안내문(상차림비 안내 등)인 항목을 걸러내기 위한 신호.
#: 요리명은 문장으로 끝나지 않는다("...받지않습니다", "...포함되어 있습니다" 등).
_NOTICE_ENDING = re.compile(
    r"(습니다|합니다|됩니다|입니다|있습니다|없습니다|않습니다"
    r"|해요|돼요|예요|이에요|세요|주세요|바랍니다)\.?\s*$"
)

#: 요리 1개가 아니라 "세트/코스/추가주문" 같은 구성 단위인 항목.
#: 이런 건 식약처 DB의 개별 요리와 애초에 매칭 대상이 아니다 — "평일점심특선"은
#: 여러 요리를 묶은 상품명이지 요리 하나가 아니고, "냉면사리추가"·"상추 추가"는
#: 요리가 아니라 추가 주문이다. 뒤에 붙는 a/b/1 같은 옵션 구분자(같은 이름의
#: 특선 메뉴가 요일별로 여러 개인 경우)까지 흡수한다.
_SET_OR_COURSE_LIKE = re.compile(
    r"(특선|코스|추가)\s*[a-z0-9]?\s*$", re.IGNORECASE
)

#: 이모지 — 괄호 밖에 단독으로 붙는 경우도 있다 (예: "🐂한우모듬", "🐷제육볶음").
#: 주요 이모지 유니코드 블록을 포괄한다. 공백으로 치환해 옆 글자가 붙어버리는
#: 것을 막는다 (뒤에서 다중 공백을 한 칸으로 정리).
_EMOJI = re.compile(
    "["
    "\U0001F300-\U0001F5FF"  # 기타 기호·그림문자
    "\U0001F600-\U0001F64F"  # 이모티콘
    "\U0001F680-\U0001F6FF"  # 교통·지도 기호
    "\U0001F700-\U0001F77F"
    "\U0001F780-\U0001F7FF"
    "\U0001F800-\U0001F8FF"
    "\U0001F900-\U0001F9FF"  # 동물 등 (🐂🐷 포함)
    "\U0001FA00-\U0001FA6F"
    "\U0001FA70-\U0001FAFF"
    "\U00002600-\U000026FF"  # 기타 기호 (☀★ 등)
    "\U00002700-\U000027BF"  # 딩벳
    "\U00002300-\U000023FF"  # 기타 기술 기호 (⏰ 등)
    "\U00002B00-\U00002BFF"  # 화살표·별 (⭐➡ 등)
    "\U0001F1E6-\U0001F1FF"  # 국기 구성요소
    "\U0000FE0F"              # variation selector (이모지 표시 강제)
    "\U0000200D"              # zero-width joiner (복합 이모지)
    "]+"
)


def _strip_bracket_content(s: str) -> str:
    while True:
        stripped = _BRACKET_CONTENT.sub("", s)
        if stripped == s:
            return s
        s = stripped


def _strip_trailing_suffixes(s: str) -> str:
    """수량·사이즈·흔한 접미어를 끝에서 반복 제거한다.

    "양갈비살꼬치 1인분 180g"처럼 표기가 여러 번 겹치면 한 번만 지워선
    "1인분"이 남는다("180g"를 지우면 새로 "1인분"이 끝에 드러나기 때문).
    변화가 없을 때까지 반복해야 전부 지워진다 — 괄호 제거(`_strip_bracket_content`)와
    같은 이유다.
    """
    while True:
        stripped = _TRAILING_QUANTITY.sub("", s)
        stripped = _TRAILING_HANJA_SIZE.sub("", stripped)
        stripped = _TRAILING_KOREAN_MODIFIER.sub("", stripped)
        if stripped == s:
            return s
        s = stripped


@dataclass(frozen=True)
class NormalizedMenu:
    name: str
    normalized_name: str
    price: int | None


@dataclass(frozen=True)
class NormalizedRestaurant:
    name: str
    address: str
    cuisine: str
    source_url: str
    latitude: float | None
    longitude: float | None
    menus: tuple[NormalizedMenu, ...]


class SkipRestaurant(Exception):
    """이 식당 한 건만 건너뛰어야 할 때 사용한다. 배치 전체는 중단하지 않는다."""


def _nfc(s: str) -> str:
    """유니코드 NFC 정규화. 크롤링 데이터에 자모 분리형이 섞여 들어올 수 있어
    반드시 다른 처리보다 먼저 한다."""
    return unicodedata.normalize("NFC", s)


def load_cuisine_map(path: str | Path) -> dict[str, str]:
    mapping: dict[str, str] = {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            cuisine = row["cuisine"].strip()
            if cuisine not in VALID_CUISINE:
                raise ValueError(
                    f"cuisine_map.csv에 잘못된 cuisine 값: {row['raw_category']!r} -> {cuisine!r}"
                )
            mapping[_nfc(row["raw_category"].strip())] = cuisine
    return mapping


def normalize_menu_name(name: str, variants: dict[str, str] | None = None) -> str:
    """메뉴명 정규화. 이모지·괄호로 감싼 부가정보(홍보문구·안내 등)와
    끝에 붙은 사이즈·흔한 접미어를 제거하되, 단어 중간에 낀 글자는
    건드리지 않는다 (예: "대게살유산슬"의 "대"는 유지).

    `variants`는 표기 흔들림(오탈자·이표기) 치환 사전이다("차돌백이"→"차돌박이"
    처럼). `official_food.py`가 이 함수를 그대로 재사용하므로, 여기서
    치환해두면 메뉴·식약처 양쪽이 같은 표준형으로 수렴한다 — 편집거리·n-gram
    유사도로는 못 잡는 짧은 단어의 한 글자 오탈자(4글자 중 1글자만 달라도
    유사도가 0.75/0.2까지 떨어짐)를 이 사전이 대신 흡수한다.
    """
    s = _nfc(name)
    s = _CONTROL_CHARS.sub(" ", s)
    s = _EMOJI.sub(" ", s)
    s = _HANJA.sub(" ", s)
    s = _SLASH.sub("", s)
    s = _strip_bracket_content(s)
    s = _STRAY_BRACKET_CHARS.sub("", s)
    s = _DECORATIVE_EDGE.sub("", s)
    s = _strip_trailing_suffixes(s)
    s = _MULTI_SPACE.sub(" ", s).strip()
    s = s.lower()
    for variant, canonical in (variants or {}).items():
        s = s.replace(variant, canonical)
    return s


def load_menu_variants(path: str | Path) -> dict[str, str]:
    """표기 흔들림 치환 사전을 읽는다. `variant` 문자열을 `canonical`로 바꾼다.

    라벨링·실측에서 실제로 확인된 쌍만 담는다 — 추측으로 채우면 엉뚱한
    치환이 다른 메뉴를 망가뜨릴 수 있다. 파일이 없으면 빈 사전으로 진행한다.
    """
    p = Path(path)
    if not p.exists():
        return {}
    variants: dict[str, str] = {}
    with open(p, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            variant = (row.get("variant") or "").strip().lower()
            canonical = (row.get("canonical") or "").strip().lower()
            if variant and canonical:
                variants[variant] = canonical
    return variants


def is_notice_like(normalized_name: str) -> bool:
    """메뉴명이 아니라 안내문("상차림비 받지않습니다" 등)인지 판정한다.
    괄호 제거 등 정규화가 끝난 문자열에 대해 검사한다 — "[상차림비 X] 상차림비
    받지않습니다"는 괄호 제거 후에야 문장 어미가 드러난다."""
    return bool(_NOTICE_ENDING.search(normalized_name))


def is_set_or_course_like(normalized_name: str) -> bool:
    """요리 1개가 아니라 세트/코스/추가주문 같은 구성 단위인지 판정한다
    ("평일점심특선", "스페셜코스", "냉면사리추가" 등). 이런 항목은 매칭
    가능한 개별 요리가 없으므로 메뉴 목록에서 통째로 제외한다."""
    return bool(_SET_OR_COURSE_LIKE.search(normalized_name))


def load_excluded_menu_terms(path: str | Path) -> list[str]:
    """요리 자체가 아닌 항목(주류·용량단위·비식품 등)의 키워드 목록.

    라벨링 중 실제로 확인된 것만 담는다("참이슬 후레쉬"=주류,
    "하프갤론"=아이스크림 용량 단위, "핸드팩세트"=화장품 증정품 — 전부 크롤링된
    "메뉴" 목록에 섞여 들어온 비요리 항목이다). `excluded_brands.csv`와 같은
    파일 기반 방식이라, 새로 발견되면 코드 수정 없이 이 파일에 한 줄만 추가하면
    된다. 파일이 없으면 빈 목록으로 진행한다(선택 사항).
    """
    p = Path(path)
    if not p.exists():
        return []
    terms: list[str] = []
    with open(p, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            term = (row.get("term") or "").strip().lower()
            if term:
                terms.append(term)
    return terms


def is_excluded_menu_term(normalized_name: str, terms: list[str]) -> bool:
    return any(t in normalized_name for t in terms)


#: 용량(ml) 표기가 붙은 항목은 사실상 음료다. 브랜드를 하나씩 등록하는
#: `excluded_menu_terms.csv` 방식은 새 음료가 나올 때마다 계속 새기 때문에
#: (환타·펩시·탐스…), 표기 패턴으로 한 번에 잡는다.
#:
#: ⚠ **괄호를 지우기 전인 원본 이름**으로 판단해야 한다. 용량은 거의 항상
#: 괄호 안에 들어 있어서("환타 오렌지 추가 (355ml)"), 정규화된 이름에는
#: 이미 사라지고 없다.
_BEVERAGE_VOLUME = re.compile(r"\d+\s*(ml|㎖|리터)", re.IGNORECASE)


def is_beverage_like(original_name: str) -> bool:
    """용량 표기로 음료를 판정한다. 원본(정규화 전) 이름을 넘겨야 한다."""
    return bool(_BEVERAGE_VOLUME.search(original_name))


def normalize_source_url(url: str) -> str:
    """쿼리스트링·fragment 제거, 끝 슬래시 정리. 대소문자는 바꾸지 않는다
    (네이버 place id는 숫자라 안전하지만, 다른 소스가 붙을 걸 대비해 보수적으로 둔다)."""
    parts = urlsplit(_nfc(url).strip())
    cleaned = urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip("/"), "", ""))
    return cleaned


class Normalizer:
    def __init__(
        self,
        cuisine_map: dict[str, str],
        excluded_menu_terms: list[str] | None = None,
        menu_variants: dict[str, str] | None = None,
    ):
        self._cuisine_map = cuisine_map
        self._excluded_menu_terms = excluded_menu_terms or []
        self._menu_variants = menu_variants or {}

    def normalize(self, raw: RawRestaurant) -> NormalizedRestaurant:
        name = _nfc(raw.name).strip()
        address = _nfc(raw.address).strip()
        source_url = raw.source_url and raw.source_url.strip()

        if not name or not address or not source_url:
            raise SkipRestaurant(f"필수값 누락: name={raw.name!r} address={raw.address!r} url={raw.source_url!r}")

        raw_category = _nfc(raw.raw_category.strip()) if raw.raw_category else ""
        cuisine = self._cuisine_map.get(raw_category)
        if cuisine is None:
            raise SkipRestaurant(f"cuisine_map에 없는 raw_category: {raw_category!r} (식당: {name})")

        normalized_menus: list[NormalizedMenu] = []
        for m in raw.menus:
            if not m.name or not m.name.strip():
                continue
            nm = self._normalize_menu(m)
            if nm is not None:
                normalized_menus.append(nm)
        menus = tuple(normalized_menus)

        return NormalizedRestaurant(
            name=name,
            address=address,
            cuisine=cuisine,
            source_url=normalize_source_url(source_url),
            latitude=raw.latitude,
            longitude=raw.longitude,
            menus=menus,
        )

    def _normalize_menu(self, m: RawMenu) -> NormalizedMenu | None:
        """정상 메뉴면 NormalizedMenu, 안내문 등 요리가 아닌 항목이면 None."""
        original = _nfc(m.name).strip()
        normalized = normalize_menu_name(original, self._menu_variants)
        if (
            not normalized
            # 용량 판정만 원본 이름을 쓴다 — 괄호 안 "(355ml)"는 정규화 과정에서
            # 사라지므로, 정규화된 이름으로는 음료인 줄 알 수 없다.
            or is_beverage_like(original)
            or is_notice_like(normalized)
            or is_set_or_course_like(normalized)
            or is_excluded_menu_term(normalized, self._excluded_menu_terms)
        ):
            return None
        return NormalizedMenu(name=original, normalized_name=normalized, price=m.price)
