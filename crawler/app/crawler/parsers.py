"""브라우저에 의존하지 않는 순수 파싱 함수.

``NaverMapCrawler`` 등 소스 구현체가 페이지에서 읽어온 **텍스트**를 여기 함수들에
넘겨 :class:`~app.model.raw.RawMenu` 로 바꾼다. Page/Frame 객체를 받지 않으므로
브라우저 없이 단위 테스트가 가능하고, 셀렉터가 깨졌을 때도 "무엇을 읽었는지"와
"그걸 어떻게 해석하는지"를 분리해서 디버깅할 수 있다.

이 모듈도 ``raw.py``와 같은 원칙을 따른다: 정규화하지 않는다. 가격을 숫자로
바꾸는 것은 "정규화"가 아니라 "원문에 이미 있는 정보를 그대로 옮겨적는 것"에
가까우므로 여기서 하지만, 메뉴명 자체(``normalized_name``)는 절대 가공하지 않는다.
"""

from __future__ import annotations

import logging
import re

from app.model.raw import RawMenu

logger = logging.getLogger(__name__)

#: "9,000원", "9000 원", "₩9,000" 등에서 숫자만 뽑는다.
_PRICE_DIGITS_RE = re.compile(r"[\d,]+")

#: 가격이 아니라 "가격문의", "품절", "-" 같은 문구로만 채워진 경우를 걸러낸다.
#: 숫자가 하나도 없는 문자열은 애초에 _PRICE_DIGITS_RE가 매치하지 않으므로
#: 이 목록은 "0" 하나만 있는 것처럼 숫자처럼 보이지만 가격이 아닌 경우를 막는 데 쓴다.
_NON_PRICE_TOKENS = {"", "0", "-", "0원"}

#: 한 줄 전체가 "가격 표기 그 자체"인지 판정. "9,000원" / "₩9,000" / "9000"처럼
#: 숫자·쉼표·₩·원 외의 문자가 섞이지 않은 줄만 매치한다. 메뉴명이 우연히 숫자를
#: 포함해도("2인분 세트") 이 패턴에는 걸리지 않도록 하기 위함.
_PRICE_ONLY_LINE_RE = re.compile(r"^[₩]?[\d,]+\s*원?$")

#: 숫자 없이도 "가격 자리"에 흔히 오는 문구. 메뉴판에 실제 가격 대신 이런
#: 문구가 들어있는 경우가 흔해서, 숫자 패턴과 별개로 인정해준다. 매치되면
#: 이름에서는 빠지고 가격은 None으로 처리된다(파싱 실패가 아니라 "가격 미표기"로 봄).
_PRICE_PLACEHOLDER_TOKENS = {"가격문의", "가격 문의", "시가", "품절", "품절중"}


def parse_price(text: str | None) -> int | None:
    """가격 원문 텍스트를 정수(원)로 바꾼다.

    Args:
        text: "9,000원", "9000", "가격문의" 등 원문. None이면 바로 None.

    Returns:
        파싱된 가격(원). 숫자를 찾지 못하면 None.

    Note:
        ``RawMenu.price``의 계약(파싱 실패 시 None)을 지키기 위해 예외를 던지지
        않는다. 여러 개의 숫자 그룹이 있으면(예: "10,000원~15,000원") **첫 번째
        그룹만** 사용한다 — 가격 범위 표현까지 다루는 건 8번 파이프라인의 몫이다.
    """
    if not text:
        return None

    match = _PRICE_DIGITS_RE.search(text)
    if match is None:
        return None

    digits = match.group().replace(",", "")
    if digits in _NON_PRICE_TOKENS:
        return None

    try:
        return int(digits)
    except ValueError:
        return None


def parse_menu_block(name_text: str | None, price_text: str | None) -> RawMenu | None:
    """메뉴 한 항목의 이름·가격 원문을 :class:`RawMenu` 로 묶는다.

    Args:
        name_text: 메뉴명 원문. 공백/개행만 있는 경우도 "이름 없음"으로 취급한다.
        price_text: 가격 원문. 없거나 파싱 실패 시 ``RawMenu.price``는 None.

    Returns:
        이름이 없으면 None(이 메뉴 항목 자체를 건너뛴다는 신호).
        이름만 있고 가격이 없어도 유효한 메뉴로 본다(가격 미표기는 흔하다).

    Note:
        메뉴명은 그대로 담는다. 공백 정리·소문자화 같은 정규화는 8번
        ``Normalizer.normalize_menu_name``의 책임이라 여기서 건드리지 않는다.
        다만 앞뒤 개행·공백만 잘라내는 건 "파싱"의 일부로 보고 수행한다
        (요소의 ``inner_text()``가 줄바꿈을 포함해 넘어오는 경우가 흔함).
    """
    if name_text is None:
        return None

    name = name_text.strip()
    if not name:
        return None

    return RawMenu(name=name, price=parse_price(price_text))


def parse_menu_row_text(row_text: str | None) -> RawMenu | None:
    """메뉴 한 행의 **통짜 텍스트**(``li.inner_text()`` 등)를 이름/가격으로 나눈다.

    지정된 셀렉터(메뉴명 셀렉터, 가격 셀렉터)가 실제 페이지 구조와 맞지 않을 때
    쓰는 대체 경로다. 이름과 가격이 각각 별도 요소가 아니라 하나의 컨테이너
    안에 줄바꿈으로만 구분돼 있는 경우, 개별 셀렉터 없이도 최소한의 결과를
    뽑아내기 위한 휴리스틱이다.

    규칙: 여러 줄 중 **마지막 줄이 가격 자리처럼 생겼으면**(숫자 가격이거나
    "가격문의"·"시가"·"품절" 같은 흔한 placeholder 문구) 그 줄을 가격 자리로
    보고 나머지 줄을 합쳐 이름으로 삼는다 — placeholder면 가격은 None이 된다.
    둘 다 아니면 마지막 줄도 이름의 일부로 본다.

    Args:
        row_text: 메뉴 한 행의 원문 텍스트. 여러 줄일 수 있다.

    Returns:
        파싱 결과. 이름으로 삼을 텍스트가 하나도 없으면 None.
    """
    if not row_text:
        return None

    lines = [line.strip() for line in row_text.splitlines() if line.strip()]
    if not lines:
        return None

    last_line = lines[-1]
    is_price_slot = _PRICE_ONLY_LINE_RE.match(last_line) or last_line in _PRICE_PLACEHOLDER_TOKENS

    if len(lines) > 1 and is_price_slot:
        price = parse_price(last_line)
        name = " ".join(lines[:-1]).strip()
    else:
        price = None
        name = " ".join(lines).strip()

    if not name:
        return None

    return RawMenu(name=name, price=price)


def dedupe_menus(menus: list[RawMenu]) -> list[RawMenu]:
    """``(이름, 가격)``이 완전히 같은 메뉴만 중복으로 보고 걸러낸다.

    네이버지도 상세 페이지는 메뉴 목록(``ul``)이 카테고리별로 여러 개 있을 수
    있고, 같은 메뉴가 대표메뉴 섹션과 전체메뉴 섹션 양쪽에 다시 노출되는 경우가
    있다. **이름만으로 판정하면** "김치찌개(소) 9,000"과 "김치찌개(대) 12,000"
    처럼 양이 달라 가격이 다른 별개 메뉴까지 사라지므로, 이름과 가격이 **둘 다**
    같을 때만 같은 메뉴로 본다.

    이름은 같은데 가격이 다른 경우는 중복으로 보지 않고 **둘 다 남긴다** —
    배달/매장처럼 성격이 다른 목록이 섞였을 가능성이 있어, 임의로 하나를
    버리기보다는 로그로 남겨 실제 수집 결과를 보고 판단할 근거를 남긴다.

    Args:
        menus: 파싱된 메뉴 목록. 등장 순서가 메뉴판 순서를 반영할 수 있으므로
            결과도 **첫 등장 순서를 그대로 유지**한다.

    Returns:
        중복이 제거된 목록.
    """
    seen_pairs: set[tuple[str, int | None]] = set()
    known_prices: dict[str, set[int | None]] = {}
    result: list[RawMenu] = []

    for menu in menus:
        pair = (menu.name, menu.price)
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)

        prices = known_prices.setdefault(menu.name, set())
        if prices and menu.price not in prices:
            logger.info(
                "메뉴명은 같지만 가격이 달라 별개로 보존: %r (%s)",
                menu.name,
                sorted((p for p in (*prices, menu.price) if p is not None)),
            )
        prices.add(menu.price)

        result.append(menu)

    return result
