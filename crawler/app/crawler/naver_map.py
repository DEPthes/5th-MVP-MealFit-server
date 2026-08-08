"""네이버지도 소스 구현체.

Selenium으로 이미 동작이 검증된 ``Z:/Python/review_sorting_project/get_data_class.py``의
``NaverMapCrawler``(리뷰 수집용)에서 셀렉터를 그대로 이식했다. 다른 점은 두 가지다.

1. 목적이 "리뷰"가 아니라 "메뉴/가격"이라 상세 페이지에서 메뉴 탭으로 들어간다.
2. 목록↔상세를 오가며 요소 참조가 끊기는 문제를 피하려고, **목록 단계에서
   place_id·상호명·업종까지 전부 모아두고, 상세는 URL로 직접 진입**하는
   2단계 구조로 바꿨다 (기존 코드는 반대로 목록 li를 계속 붙잡고 클릭 →
   뒤로가기를 반복했다).

페이지 구조와 셀렉터 배치
--------------------------
* **최상위 페이지** — searchIframe·entryIframe으로 들어가는 입구, 검색창.
  entryIframe은 place_id 추출 최후 수단(``_extract_place_id`` 3순위)에만
  쓰인다.
* **searchIframe** — 검색 결과 목록: 음식점 항목·스크롤·다음 페이지·상호명·업종.
* **Place 상세 페이지**(``pcmap.place.naver.com`` — iframe이 아니라 **직접 여는
  별도 페이지**) — 주소·메뉴. entryIframe이 화면에 띄우는 내용과 같은
  페이지지만, iframe 전환 없이 새 탭으로 곧장 연다. entryIframe의 옛
  클래스명(``span.LDgIH`` 등)이 더 이상 맞지 않아, iframe 단계 자체를
  걷어내고 이 페이지를 직접 열도록 바꿨다.

셀렉터 표기는 **전부 CSS로 통일**한다. 원본 Selenium 코드에는 XPath와
CSS가 섞여 있었지만, 한 파일 안에서 두 문법을 오가면 셀렉터가 깨졌을 때
어느 문법으로 읽어야 할지부터 판단해야 해서 수정이 느려진다. XPath에서
옮겨온 항목은 각 상수 주석에 원본 XPath를 함께 남겨 대조할 수 있게 했다.
(변환 시 주의: XPath ``div[4]``는 "4번째 div 형제"라서 CSS ``nth-child``가
아니라 ``nth-of-type``에 대응한다.)

메뉴 화면은 실측 결과 **식당마다 두 종류의 구조**로 갈린다 (``MENU_LAYOUTS``
참고).

* **주문형** — "메뉴" 탭을 누르면 ``m.booking.naver.com``(네이버 주문)으로
  페이지 자체가 이동한다. 그 페이지의 클래스명(``MenuContent__*``,
  ``OrderHome__*``)은 CSS Modules 방식이라 끝의 해시(예: ``__OEjdC``)가
  재배포마다 바뀐다. 그래서 ``[class*="..."]`` 부분일치로 앞부분만 잡는다.
* **일반형** — 탭을 눌러도 ``pcmap.place.naver.com``에 그대로 머무르고,
  ``div.place_section_content`` 안의 ``ul``에 메뉴가 나열된다.

`_parse_menus`는 두 구조를 순서대로 시도해, 결과가 나온 첫 구조를 채택한다.
둘 다 실패하면 위치 기반 휴리스틱 폴백으로 넘어간다.

미검증 영역
-----------
* 상세 페이지 URL의 좌표 파라미터 순서(경도, 위도 가정) — DevTools로 실제
  공유 링크를 열어 순서를 확인해야 한다. 틀렸다면 ``_COORDS_URL_RE`` 사용부
  두 줄만 바꾸면 된다. Place 페이지 URL에는 이 파라미터가 아예 없어, 좌표는
  사실상 항상 None이 된다 — 8번 파이프라인의 주소 기반 보정이 필요하다.
"""

from __future__ import annotations

import functools
import logging
import re
from typing import Callable, NamedTuple
from urllib.parse import quote

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import FrameLocator, Locator, Page
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from app.crawler.parsers import dedupe_menus, parse_menu_block, parse_menu_row_text
from app.crawler.playwright_base import PlaywrightCrawler
from app.model.raw import CrawlTarget, RawMenu, RawRestaurant

logger = logging.getLogger(__name__)


class _ListingRef(NamedTuple):
    """목록(searchIframe) 단계에서 미리 확보해두는 정보.

    Place 상세 페이지로 넘어간 뒤에는 이 정보를 다시 읽지 않는다. 목록에서
    이미 확실하게 읽은 값을 굳이 상세에서 또 찾을 이유가 없고, 목록↔상세를
    오가며 값이 흔들릴 여지도 없앤다.
    """

    place_id: str
    name: str | None
    raw_category: str | None


class _MenuLayout(NamedTuple):
    """메뉴 화면 한 종류의 구조 — "무엇을 순회하고 어디서 이름·가격을 읽는가".

    실측 결과 식당마다 메뉴 화면이 두 종류로 갈려서(``MENU_LAYOUTS``),
    분기문 대신 구조 자체를 값으로 만들어 순서대로 시도한다. 나중에 세
    번째 구조가 발견되어도 이 튜플 하나만 추가하면 된다.
    """

    label: str  #: 로그에 남길 이름. 예) "주문형"
    list_selector: str  #: 항목들을 감싸는 컨테이너. 수집 범위를 여기로 한정한다.
    item_selector: str  #: 메뉴 한 항목.
    name_selector: str  #: 항목 안에서 메뉴명이 있는 곳.
    price_selector: str  #: 항목 안에서 가격이 있는 곳.


class NaverMapCrawler(PlaywrightCrawler):
    """네이버지도에서 식당 기본정보와 메뉴를 수집하는 크롤러."""

    source_name = "naver"

    # ==================================================================
    # 최상위 페이지 — iframe 두 개로 들어가는 입구
    # ==================================================================

    #: 검증됨 (기존 Selenium 코드 249행)
    SEARCH_URL_TMPL = "https://map.naver.com/p/search/{query}?c=13.00,0,0,0,dh"

    #: 검증됨 (251–253행) — 검색 결과 목록을 실제로 로드시키는 트리거.
    #: searchIframe으로 전환하기 *이전에* 최상위 페이지에서 클릭한다.
    SEL_SEARCH_INPUT = ".input_search"

    #: 검증됨 (255행) — searchIframe 그 자체를 가리키는 셀렉터 (최상위 페이지 기준)
    SEL_LIST_IFRAME = "#searchIframe"

    #: 검증됨 (300행) — entryIframe 그 자체를 가리키는 셀렉터 (최상위 페이지 기준)
    SEL_ENTRY_IFRAME = "#entryIframe"

    # ==================================================================
    # searchIframe 내부 — 검색 결과 목록
    # ==================================================================

    #: 검증됨 (257행) — 목록의 스크롤 컨테이너
    SEL_SCROLL_BOX = "#_pcmap_list_scroll_container"

    #: 검증됨 (285행) — 음식점 목록 항목 하나
    SEL_LIST_ITEM = 'li[data-laim-exp-id="undefinedundefined"]'

    #: 검증됨 (289행) — 항목 안의 상세 링크 (place_id 추출용 1순위).
    #: 원본 XPath ``.//div[1]/div[1]/a`` 를 CSS로 옮긴 것. 호출부에서 ``.first``를
    #: 쓰므로 DOM 순서상 첫 번째가 선택되어 원본과 같은 요소를 가리킨다.
    SEL_LIST_ITEM_LINK = "div > div > a"

    #: 검증됨 (289행) — restaurant_name. 목록 항목 하나 안에서 읽는다.
    SEL_NAME = "span.TYaxT"

    #: 검증됨 (290행) — category(업종 원문). 목록 항목 하나 안에서 읽는다.
    SEL_CATEGORY = "span.KCMnt"

    #: 검증됨 (276행, {} 안에 링크 인덱스) — 다음 페이지.
    #: 원본 XPath ``//*[@id="app-root"]/div/div[2]/div[2]/a[{}]`` 를 CSS로 옮긴 것.
    #: XPath의 ``div[2]``·``a[n]``은 "n번째 같은 태그"이므로 nth-child가 아니라
    #: nth-of-type으로 옮겨야 의미가 같다.
    #: 기존 코드가 검증한 상한(1~5페이지, a[2]~a[6])과 동일하게 유지한다.
    SEL_PAGE_LINK_TMPL = (
        "#app-root > div > div:nth-of-type(2) > div:nth-of-type(2) > a:nth-of-type({})"
    )
    MAX_LIST_PAGES = 5

    # ==================================================================
    # Place 상세 페이지 (pcmap.place.naver.com) — iframe이 아니라 별도 탭으로 직접 연다
    # ==================================================================

    #: entryIframe이 가리키던 실제 주소(실측). {} 에 place_id가 들어간다.
    #: DB에 저장하는 ``source_url``(map.naver.com, ``_canonical_url``)과는
    #: 다른 값이다 — 수집은 이 주소로 하고 기록은 지도 URL로 한다.
    SEL_PLACE_URL_TMPL = "https://pcmap.place.naver.com/place/{}"

    #: 검증됨 (실측) — 주소
    SEL_ADDRESS = "span.pz7wy"

    #: 검증됨 (실측) — 탭(홈/메뉴/리뷰 등) 바 컨테이너. CSS Modules 해시가 아니라
    #: 의미 있는 이름의 클래스라 옛 ``div:nth-of-type(4)...`` 위치 체인보다 안정적이다.
    SEL_MENU_TAB_CONTAINER = "div.place_fixed_maintab"

    #: 클릭할 탭 이름 — 컨테이너 안 <a> 중 첫 줄 텍스트가 이 값과 일치하는 것을
    #: 찾는다(``_click_tab_by_text``). 몇 번째 탭인지에 의존하지 않으므로,
    #: 식당마다 탭 구성이 달라 순서가 밀려도 흔들리지 않는다.
    MENU_TAB_NAME = "메뉴"

    #: 실측으로 확인된 메뉴 화면 두 종류. 순서대로 시도해 결과가 나온 첫
    #: 구조를 채택한다 (``_parse_menus`` 참고).
    #:
    #: * "주문형" — ``m.booking.naver.com``(네이버 주문)으로 페이지가 이동한
    #:   뒤 나타나는 구조. ``list_selector``로 걸리는 컨테이너가 **한 문서에
    #:   여러 개** 있을 수 있어(카테고리별 구분), 전부를 대상으로 순회한다.
    #: * "일반형" — 탭을 눌러도 ``pcmap.place.naver.com``에 그대로 머무르는
    #:   식당의 구조. ``div.place_section_content`` 안의 ``ul``에 메뉴가 있다.
    MENU_LAYOUTS: tuple[_MenuLayout, ...] = (
        _MenuLayout(
            label="주문형",
            list_selector='[class*="OrderHome__order_list_area"]',
            item_selector='[class*="MenuContent__order_list_item"]',
            name_selector='[class*="MenuContent__tit"]',
            # price div 자체가 아니라 그 안의 strong에서 읽는다. div 텍스트를
            # 그대로 읽으면 "원" 표기나 부가 문구가 섞여 들어올 수 있다.
            price_selector='[class*="MenuContent__price"] strong',
        ),
        _MenuLayout(
            label="일반형",
            list_selector="div.place_section_content ul",
            item_selector="li.E2jtL",
            name_selector="span.lPzHi",
            price_selector="div.GXS1X span em",
        ),
    )

    #: 휴리스틱 폴백에서 순회할 대상. 위 MENU_LAYOUTS 두 구조 모두 안 맞을
    #: 때만 쓰는 최후의 수단이라 넓게 잡아도 무방하다.
    #: XPath의 ``contains(@class, 'place_section')`` 는 CSS의 부분일치
    #: 속성 선택자 ``[class*="place_section"]`` 로 옮긴다.
    SEL_MENU_FALLBACK_ITEM = '#app-root div[class*="place_section"] li'

    # ==================================================================
    # 공통 패턴 (특정 iframe에 속하지 않음)
    # ==================================================================

    #: 상세 페이지 URL에서 좌표를 뽑는 패턴. 순서는 (경도, 위도)로 가정
    #: — 실제 공유 링크로 확인 필요. 뒤바뀌어 있으면 group(1)/(2)만 교체.
    _COORDS_URL_RE = re.compile(r"[?&]c=(-?\d+\.\d+),(-?\d+\.\d+)")

    #: place_id 패턴: "/place/12345678" 형태. href와 entryIframe URL 양쪽에서 씀.
    _PLACE_ID_RE = re.compile(r"/place/(\d+)")

    # ------------------------------------------------------------------
    # 공개 API
    # ------------------------------------------------------------------
    def crawl(self, target: CrawlTarget) -> list[RawRestaurant]:
        listings = self._collect_listings(target)
        logger.info("%s 목록 %d건 수집, 상세 파싱 시작", self._log_prefix(), len(listings))

        results: list[RawRestaurant] = []
        no_menu_count = 0
        failed_count = 0

        for listing in listings:
            try:
                restaurant = self._parse_restaurant(listing)
            except Exception as e:  # noqa: BLE001 - 건별 격리, 배치 전체를 막지 않는다
                logger.warning(
                    "%s 상세 파싱 실패 %s: %s", self._log_prefix(), listing.place_id, e
                )
                failed_count += 1
                continue

            if restaurant is None:
                failed_count += 1
                continue
            if restaurant.menu_count == 0:
                no_menu_count += 1
                continue
            results.append(restaurant)

        logger.info(
            "%s 수집 완료: 성공 %d건 / 메뉴 없어 제외 %d건 / 실패 %d건",
            self._log_prefix(),
            len(results),
            no_menu_count,
            failed_count,
        )
        return results

    # ------------------------------------------------------------------
    # 1단계 — searchIframe: 목록에서 place_id·상호명·업종 수집
    # ------------------------------------------------------------------
    def _collect_listings(self, target: CrawlTarget) -> list[_ListingRef]:
        """검색 결과 목록을 페이지네이션하며 항목별 정보를 모은다.

        상호명(``SEL_NAME``)·업종(``SEL_CATEGORY``)은 **여기, 목록 단계에서만**
        읽는다. entryIframe에는 이 정보가 없다고 가정하지 않고, 애초에 원본
        Selenium 코드가 이 값들을 목록에서 읽던 방식(289~296행)을 그대로 따른다.

        ``target.max_count``에 도달하는 즉시 중단하므로, 필요한 것보다 많은
        페이지를 넘기지 않는다.
        """
        url = self.SEARCH_URL_TMPL.format(query=quote(target.query))
        page = self._open_page(url)
        try:
            # 최초 진입만으로는 목록이 비어 있을 수 있어 재검색을 트리거한다.
            # (최상위 페이지에서 클릭 — searchIframe 진입 이전 단계)
            # 페이지에 .input_search 요소가 2개 존재해(실측 확인) .first로 특정한다.
            search_input = page.locator(self.SEL_SEARCH_INPUT).first
            search_input.click()
            search_input.press("Enter")

            list_frame = self._frame(page, self.SEL_LIST_IFRAME)
            self._scroll_until_stable(page, list_frame, self.SEL_SCROLL_BOX, self.SEL_LIST_ITEM)

            listings: list[_ListingRef] = []
            seen: set[str] = set()

            for page_num in range(1, self.MAX_LIST_PAGES + 1):
                items = list_frame.locator(self.SEL_LIST_ITEM)
                count = items.count()

                for i in range(count):
                    if len(listings) >= target.max_count:
                        break
                    item = items.nth(i)

                    place_id = self._extract_place_id(page, item)
                    if not place_id or place_id in seen:
                        continue
                    seen.add(place_id)

                    name = self._text_or_none(item, self.SEL_NAME)
                    category = self._text_or_none(item, self.SEL_CATEGORY)
                    listings.append(
                        _ListingRef(place_id=place_id, name=name, raw_category=category)
                    )

                if len(listings) >= target.max_count:
                    break

                if page_num == self.MAX_LIST_PAGES:
                    break

                moved = self._go_to_next_list_page(list_frame, next_page_number=page_num + 1)
                if not moved:
                    logger.debug("%s %d페이지에서 목록 종료", self._log_prefix(), page_num)
                    break

                # 페이지 전환 후 새 목록이 그려질 시간을 준다.
                self._settle(page, list_frame, self.SEL_LIST_ITEM)
                self._scroll_until_stable(
                    page, list_frame, self.SEL_SCROLL_BOX, self.SEL_LIST_ITEM
                )

            return listings
        finally:
            page.close()

    def _go_to_next_list_page(self, list_frame: FrameLocator, next_page_number: int) -> bool:
        """목록 하단 페이지네이션(다음 페이지)에서 ``next_page_number``로 이동한다.

        기존 코드의 인덱싱(``a[2]``=1페이지 기준, ``a[j]``→(j-1)페이지)과
        동일하게 링크 인덱스는 ``next_page_number + 1``이다.
        """
        link_index = next_page_number + 1
        link = list_frame.locator(self.SEL_PAGE_LINK_TMPL.format(link_index))
        if link.count() == 0:
            return False
        link.click()
        return True

    def _extract_place_id(self, page: Page, item: Locator) -> str | None:
        """목록 항목 하나에서 place_id를 뽑는다. 세 가지 방식을 순서대로 시도한다.

        1. 상세 링크의 ``href`` — 가장 저렴하고, 대부분의 경우 이걸로 끝난다.
        2. 항목/링크의 ``data-*`` 속성 — href가 비어 있는 변형 대비.
        3. 링크를 실제로 클릭해 entryIframe의 URL에서 추출 — 위 둘이 실패했을
           때만 쓰는 마지막 수단. 클릭 한 번당 상세 페이지 하나가 로드되므로
           비용이 크다.
        """
        link = item.locator(self.SEL_LIST_ITEM_LINK).first
        if link.count() == 0:
            return None

        href = link.get_attribute("href")
        if href:
            match = self._PLACE_ID_RE.search(href)
            if match:
                return match.group(1)

        for attr in ("data-id", "data-place-id", "data-laim-place-id"):
            value = link.get_attribute(attr) or item.get_attribute(attr)
            if value and value.isdigit():
                return value

        # 마지막 수단: 클릭 후 entryIframe URL에서 추출.
        # ElementHandle.content_frame() 대신 page.frames를 순회한다 — Frame
        # 객체(iframe의 실제 URL을 노출)를 얻는 데 ElementHandle을 거칠 필요가 없다.
        try:
            link.click()
            self._frame(page, self.SEL_ENTRY_IFRAME)  # 로드될 때까지 대기(진행 불가 시 예외)
            for frame in page.frames:
                match = self._PLACE_ID_RE.search(frame.url)
                if match:
                    return match.group(1)
            return None
        except (PlaywrightError, PlaywrightTimeoutError) as e:
            logger.debug("%s place_id 클릭 추출 실패: %s", self._log_prefix(), e)
            return None

    # ------------------------------------------------------------------
    # 2단계 — Place 상세 페이지 파싱 (entryIframe 대신 직접 연다)
    # ------------------------------------------------------------------
    def _canonical_url(self, place_id: str) -> str:
        """upsert 키로 쓸 고정 형태의 상세 URL. **저장용**이지 여는 주소가 아니다.

        지도 URL에는 좌표·줌·세션 파라미터가 붙어 매번 달라질 수 있어,
        ``restaurant.source_url``(UNIQUE)에는 이 파라미터 없는 형태만 저장한다.
        실제로 정보를 읽어오는 페이지는 :meth:`_place_url`이 여는 쪽이다 —
        사람이 이 URL을 열었을 때 정상적인 지도 화면이 뜨는 쪽을 기록으로 남긴다.
        """
        return f"https://map.naver.com/p/entry/place/{place_id}"

    def _place_url(self, place_id: str) -> str:
        """실제로 열어서 정보를 읽어올 Place 상세 페이지 주소.

        entryIframe의 ``src``가 가리키던 곳과 같은 페이지다. iframe으로
        간접적으로 읽는 대신 이 페이지를 별도 탭으로 직접 연다.
        """
        return self.SEL_PLACE_URL_TMPL.format(place_id)

    def _parse_restaurant(self, listing: _ListingRef) -> RawRestaurant | None:
        """Place 상세 페이지에서 주소·메뉴만 읽는다.

        상호명·업종은 목록 단계(``listing``)에서 이미 확보했으므로 여기서는
        다시 읽지 않는다.
        """
        source_url = self._canonical_url(listing.place_id)
        page = self._open_page(self._place_url(listing.place_id))
        try:
            address = self._text_or_none(page, self.SEL_ADDRESS)
            name = listing.name.strip() if listing.name else None

            if not name or not address:
                logger.warning(
                    "%s 필수 정보 누락으로 건너뜀 %s (name=%r, address=%r)",
                    self._log_prefix(), listing.place_id, name, address,
                )
                return None

            latitude, longitude = self._extract_coords(page)
            menus = self._parse_menus(page)

            return RawRestaurant(
                name=name,
                address=address.strip(),
                raw_category=(listing.raw_category or "").strip(),
                source_url=source_url,
                latitude=latitude,
                longitude=longitude,
            ).with_menus(menus)
        finally:
            page.close()

    def _extract_coords(self, page: Page) -> tuple[float | None, float | None]:
        """상세 페이지 URL에서 좌표를 읽는다. 못 찾으면 (None, None).

        네이버 SPA가 place 로드 후 주소창을 ``?c=경도,위도,줌,...`` 형태로
        갱신하는 것을 가정한다 — **미검증**. 실측 결과 순서가 반대(위도,경도)
        라면 아래 두 줄의 lng/lat만 서로 바꾸면 된다.

        네트워크 응답을 가로채 좌표를 읽는 방법도 있지만, 실제 API 응답
        구조를 실측하지 않고서는 신뢰할 수 없는 코드가 되므로 이번 구현에는
        넣지 않았다. 이 방식이 안 맞으면 그 방식으로 교체한다.
        """
        match = self._COORDS_URL_RE.search(page.url)
        if not match:
            return None, None
        try:
            lng, lat = float(match.group(1)), float(match.group(2))
        except ValueError:
            return None, None
        return lat, lng

    # ------------------------------------------------------------------
    # Place 상세 페이지: 메뉴 파싱
    # ------------------------------------------------------------------
    def _parse_menus(self, page: Page) -> list[RawMenu]:
        clicked = self._click_tab_by_text(page, self.SEL_MENU_TAB_CONTAINER, self.MENU_TAB_NAME)
        if not clicked:
            logger.info("%s 메뉴 탭 없음 (메뉴 미제공 식당으로 간주)", self._log_prefix())
            return []

        # 주문형은 탭 클릭 후 m.booking.naver.com으로 페이지 자체가 이동하므로
        # 일반형(같은 페이지 안에서 패널만 바뀜)보다 오래 걸린다. 두 구조의
        # 항목 셀렉터를 쉼표로 묶어(CSS의 OR) 어느 쪽이든 먼저 나타나면
        # 진행하고, 도메인 이동까지 감안해 nav_timeout_ms만큼 넉넉히 기다린다.
        any_item_selector = ", ".join(layout.item_selector for layout in self.MENU_LAYOUTS)
        self._settle(page, page, any_item_selector, fallback_ms=self.nav_timeout_ms)

        menus: list[RawMenu] = []
        for layout in self.MENU_LAYOUTS:
            items = page.locator(layout.list_selector).locator(layout.item_selector)
            menus = self._collect_menu_items(
                items, functools.partial(self._parse_menu_item, layout=layout)
            )
            if menus:
                logger.info("%s 메뉴 구조: %s", self._log_prefix(), layout.label)
                break

        if not menus:
            logger.info(
                "%s 지정 메뉴 셀렉터 매칭 실패, 휴리스틱 파싱으로 전환", self._log_prefix()
            )
            menus = self._collect_menu_items(
                page.locator(self.SEL_MENU_FALLBACK_ITEM),
                self._parse_menu_fallback_item,
            )

        # 여러 ul(카테고리별 구분 등)에 같은 메뉴가 중복 노출될 수 있다.
        # (이름, 가격)이 완전히 같을 때만 제거한다.
        return dedupe_menus(menus)

    @staticmethod
    def _collect_menu_items(
        items: Locator, parse_one: Callable[[Locator], RawMenu | None]
    ) -> list[RawMenu]:
        """항목 목록을 돌며 항목별 파서를 적용하는 공통 루프.

        지정 셀렉터 경로와 휴리스틱 폴백 경로의 반복 구조가 동일해서,
        "무엇을 순회하고 각 항목을 어떻게 해석하는가"만 갈아끼울 수 있게
        여기 하나로 모았다.
        """
        count = items.count()
        menus: list[RawMenu] = []
        for i in range(count):
            menu = parse_one(items.nth(i))
            if menu:
                menus.append(menu)
        return menus

    def _parse_menu_item(self, item: Locator, layout: _MenuLayout) -> RawMenu | None:
        """``layout``의 name_selector/price_selector 기준 파서."""
        name_text = self._text_or_none(item, layout.name_selector)
        price_text = self._text_or_none(item, layout.price_selector)
        return parse_menu_block(name_text, price_text)

    def _parse_menu_fallback_item(self, item: Locator) -> RawMenu | None:
        """지정 셀렉터가 안 맞을 때: 항목 통짜 텍스트를 휴리스틱으로 분리."""
        return parse_menu_row_text(item.inner_text())
