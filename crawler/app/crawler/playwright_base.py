"""Playwright 기반 동적 렌더링 크롤러의 공통 베이스.

소스가 달라도 '브라우저 기동 → 페이지 열기 → 무한 스크롤 → 정리'라는 흐름과
요청 간 지연 같은 매너는 동일하다. 그 공통 부분만 여기 모으고, 소스별 구현체
(``NaverMapCrawler`` 등)는 셀렉터와 파싱만 책임진다.

이 클래스 자체는 ``crawl()`` 을 구현하지 않으므로 추상 클래스로 남는다.
"""

from __future__ import annotations

import logging
import random
import time
from types import TracebackType

from playwright.sync_api import (
    Browser,
    BrowserContext,
    FrameLocator,
    Locator,
    Page,
    Playwright,
    sync_playwright,
)
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from app.crawler.base import RestaurantCrawler

logger = logging.getLogger(__name__)

#: 요소를 찾는 범위. 셋 다 ``.locator()``를 가지고 있어서, 최상위 페이지든
#: iframe 안이든 이미 좁혀둔 요소 하나 안이든 같은 헬퍼로 다룰 수 있다.
#: 헬퍼가 대상별로 여러 벌 갈라지는 걸 막는 지점이 바로 여기다.
Scope = Page | FrameLocator | Locator

#: 기본 브라우저 식별 문자열. 헤드리스 기본값이 서버로 그대로 노출되면
#: 정상 렌더링이 되지 않는 사이트가 많아 일반 데스크톱 값을 쓴다.
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)


class PlaywrightCrawler(RestaurantCrawler):
    """브라우저 수명·스크롤·요청 간 지연을 캡슐화한 베이스 크롤러."""

    def __init__(
        self,
        headless: bool = True,
        nav_timeout_ms: int = 15_000,
        request_delay: float = 1.0,
        user_agent: str = DEFAULT_USER_AGENT,
        viewport: tuple[int, int] = (1280, 900),
        locale: str = "ko-KR",
        block_heavy_resources: bool = True,
    ) -> None:
        #: 헤드리스 모드 여부. 셀렉터 디버깅 시 False로 두면 실제 창이 뜬다.
        self.headless = headless

        #: 페이지 이동·기본 동작 타임아웃(ms)
        self.nav_timeout_ms = nav_timeout_ms

        #: 요청 간 최소 지연(초). 상대 서버 부하를 줄이기 위한 rate limit.
        self.request_delay = request_delay

        self.user_agent = user_agent
        self.viewport = viewport
        self.locale = locale

        #: 이미지·폰트·미디어 요청을 차단할지 여부.
        #: 기존 Selenium 코드가 Chrome prefs로 이미지 로딩을 껐던 것과 같은
        #: 목적으로, 렌더링에 필요 없는 요청을 걸러 수집 속도를 높인다.
        self.block_heavy_resources = block_heavy_resources

        # 수명 관리 대상 핸들. __enter__ 전에는 전부 None이다.
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None

        #: 마지막 요청 시각(monotonic). 지연 계산용.
        self._last_request_at: float = 0.0

    # ------------------------------------------------------------------
    # 수명 관리
    # ------------------------------------------------------------------
    def __enter__(self) -> PlaywrightCrawler:
        """브라우저와 컨텍스트를 기동한다.

        컨텍스트를 페이지마다 새로 만들지 않고 하나로 재사용해, 쿠키·세션이
        유지되면서 기동 비용도 아낀다.
        """
        logger.info("%s 브라우저 기동 (headless=%s)", self._log_prefix(), self.headless)
        self._playwright = sync_playwright().start()
        try:
            self._browser = self._playwright.chromium.launch(
                headless=self.headless,
                # 자동화 탐지 배너/차단 회피. Selenium판 원본(기존
                # get_data_class.py의 excludeSwitches·useAutomationExtension·
                # disable-blink-features 조합)과 같은 목적의 Playwright 대응.
                args=["--disable-blink-features=AutomationControlled"],
            )
            self._context = self._browser.new_context(
                user_agent=self.user_agent,
                viewport={"width": self.viewport[0], "height": self.viewport[1]},
                locale=self.locale,
            )
            self._context.set_default_timeout(self.nav_timeout_ms)
            if self.block_heavy_resources:
                self._block_heavy_resources()
        except BaseException:
            # 기동 도중 실패해도 이미 뜬 프로세스는 반드시 회수한다.
            self.close()
            raise
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> bool:
        self.close()
        return False

    def close(self) -> None:
        """열려 있는 리소스를 역순으로 정리한다.

        중간에 하나가 실패해도 나머지는 계속 닫아야 브라우저 프로세스가
        좀비로 남지 않으므로, 단계마다 예외를 삼키고 로그만 남긴다.
        """
        for name, handle in (
            ("context", self._context),
            ("browser", self._browser),
            ("playwright", self._playwright),
        ):
            if handle is None:
                continue
            try:
                # Playwright 핸들만 stop(), 나머지는 close()
                handle.stop() if name == "playwright" else handle.close()
            except Exception as e:  # noqa: BLE001 - 정리 실패는 치명적이지 않다
                logger.warning("%s %s 정리 실패: %s", self._log_prefix(), name, e)

        self._context = None
        self._browser = None
        self._playwright = None

    @property
    def context(self) -> BrowserContext:
        """활성 브라우저 컨텍스트.

        Raises:
            RuntimeError: ``with`` 블록 밖에서 접근한 경우.
        """
        if self._context is None:
            raise RuntimeError(
                f"{self.__class__.__name__}는 with 블록 안에서만 사용할 수 있습니다. "
                f"예) with {self.__class__.__name__}() as crawler: crawler.crawl(target)"
            )
        return self._context

    # ------------------------------------------------------------------
    # 페이지 조작
    # ------------------------------------------------------------------
    def _respect_delay(self) -> None:
        """직전 요청으로부터 ``request_delay`` 만큼 지날 때까지 대기한다.

        일정한 간격은 그 자체로 부자연스러운 트래픽이 되므로 약간의 흔들림을 준다.
        """
        if self.request_delay <= 0:
            return
        target = self.request_delay * random.uniform(1.0, 1.3)
        elapsed = time.monotonic() - self._last_request_at
        remaining = target - elapsed
        if remaining > 0:
            time.sleep(remaining)
        self._last_request_at = time.monotonic()

    def _open_page(self, url: str) -> Page:
        """새 페이지를 열고 로딩이 안정될 때까지 기다린다.

        호출자는 사용 후 ``page.close()`` 로 닫아야 한다. 목록에서 상세로
        수십 건을 도는 동안 페이지를 닫지 않으면 메모리가 계속 늘어난다.

        Args:
            url: 이동할 주소.

        Returns:
            로딩이 끝난 페이지.

        Raises:
            PlaywrightTimeoutError: 지정 시간 안에 문서를 받지 못한 경우.
        """
        self._respect_delay()
        page = self.context.new_page()
        try:
            page.goto(url, timeout=self.nav_timeout_ms, wait_until="domcontentloaded")
            # 동적 렌더링 페이지는 문서 수신 이후에 내용이 채워지므로 한 번 더 기다린다.
            # 광고·트래킹 요청이 계속 도는 사이트에서는 networkidle이 오지 않을 수
            # 있는데, 그건 실패가 아니라 흔한 상황이라 넘어간다.
            try:
                page.wait_for_load_state("networkidle", timeout=self.nav_timeout_ms)
            except PlaywrightTimeoutError:
                logger.debug("%s networkidle 미도달, 계속 진행: %s", self._log_prefix(), url)
        except BaseException:
            page.close()
            raise
        return page

    def _scroll_until_stable(
        self,
        page: Page,
        scope: Scope,
        box_selector: str,
        item_selector: str,
        rounds: int = 15,
        pause_ms: int = 700,
    ) -> None:
        """무한 스크롤 목록을 끝까지 로드한다.

        실제 마우스 휠 이벤트를 컨테이너 위에서 발생시켜 스크롤한다. 스크립트로
        직접 스크롤(``element.scrollTo`` 등)하는 대신 이 방식을 쓰는 이유는,
        ``FrameLocator``는 ``evaluate()`` 대상이 아니라서 iframe 안에서는 JS
        스크롤이 애초에 불가능하기 때문이다. 마우스 휠은 최상위 페이지든 iframe
        안이든 동일하게 동작해, 대상을 가리지 않는 함수 하나로 통일할 수 있다.

        판정 기준은 스크롤 높이가 아니라 **항목 개수**다. 컨테이너 구조에 따라
        스크롤 높이가 안 바뀌는 경우가 있어 개수 쪽이 더 믿을 만하다.

        Args:
            page: 실제 마우스 이벤트를 발생시킬 최상위 페이지
                (``scope``가 iframe이어도 마우스 좌표는 항상 최상위 페이지 기준).
            scope: 스크롤 컨테이너와 항목이 들어있는 범위.
            box_selector: 스크롤할 컨테이너.
            item_selector: 개수를 셀 항목. 늘어나지 않으면 끝으로 본다.
            rounds: 최대 스크롤 횟수. 끝없이 로드되는 목록에서 무한 루프를 막는 상한.
            pause_ms: 각 스크롤 후 새 항목이 붙기를 기다리는 시간.
        """
        box = scope.locator(box_selector)
        try:
            box.wait_for(state="visible", timeout=self.nav_timeout_ms)
        except PlaywrightTimeoutError:
            logger.warning(
                "%s 스크롤 컨테이너를 찾지 못했습니다: %s", self._log_prefix(), box_selector
            )
            return

        bbox = box.bounding_box()
        if bbox is None:
            return
        cx = bbox["x"] + bbox["width"] / 2
        cy = bbox["y"] + bbox["height"] / 2
        page.mouse.move(cx, cy)

        previous = scope.locator(item_selector).count()
        for i in range(rounds):
            page.mouse.wheel(0, 2000)
            page.wait_for_timeout(pause_ms)
            current = scope.locator(item_selector).count()
            if current == previous:
                logger.debug("%s 스크롤 %d회에서 목록 끝 도달", self._log_prefix(), i + 1)
                return
            previous = current

        logger.debug("%s 스크롤 상한(%d회) 도달", self._log_prefix(), rounds)

    def _settle(self, page: Page, scope: Scope, selector: str, fallback_ms: int = 800) -> None:
        """``selector``가 나타날 때까지 기다리되, 최대 ``fallback_ms``만 기다린다.

        페이지 전환처럼 네트워크 요청이 딸린 변화는 조건 대기가 더 빠르고
        정확하다. 다만 탭 전환처럼 클라이언트 사이드에서 화면만 바뀌는
        경우는 "무엇이 나타나면 끝났다고 볼지" 특정하기 애매할 때가 있어,
        그 경우엔 이 함수가 고정 시간만큼 기다린 뒤 조용히 넘어간다
        (기존에 흩어져 있던 ``wait_for_timeout(800)`` 고정 대기를 대체).
        """
        try:
            scope.locator(selector).first.wait_for(state="visible", timeout=fallback_ms)
        except PlaywrightTimeoutError:
            pass

    def _block_heavy_resources(self) -> None:
        """이미지·폰트·미디어 요청을 가로채 차단한다.

        렌더링에 필요한 텍스트·구조는 그대로 받고, 무거운 리소스만 걷어내
        페이지 로딩을 앞당긴다. 기존 Selenium 코드가
        ``profile.managed_default_content_settings.images`` prefs로 이미지를
        껐던 것과 같은 목적이며, 여기서는 컨텍스트 단위로 한 번만 등록하면
        그 컨텍스트에서 여는 모든 페이지에 적용된다.
        """
        blocked_types = {"image", "font", "media"}
        self.context.route(
            "**/*",
            lambda route: route.abort()
            if route.request.resource_type in blocked_types
            else route.continue_(),
        )

    def _frame(self, page: Page, selector: str) -> FrameLocator:
        """iframe이 실제로 붙을 때까지 기다린 뒤 그 프레임을 반환한다.

        ``page.frame_locator()``는 그 자체로는 즉시 반환되는 지연 평가값이라,
        iframe이 아직 DOM에 없어도 예외 없이 넘어가 버린다. 그 상태로 프레임
        내부를 조회하면 몇 초 뒤 애매한 타임아웃으로 실패해서 원인을 짚기
        어렵다. 여기서 먼저 iframe 엘리먼트 자체의 존재를 기다려, 실패할 때
        "어떤 iframe을 못 찾았는지"가 에러 메시지에 바로 남게 한다.

        Args:
            page: iframe을 담고 있는 상위 페이지.
            selector: iframe을 가리키는 CSS 셀렉터. 예) ``"#entryIframe"``

        Returns:
            해당 iframe 내부를 조회할 수 있는 :class:`FrameLocator`.

        Raises:
            PlaywrightTimeoutError: 지정 시간 안에 iframe이 나타나지 않은 경우.
        """
        try:
            page.wait_for_selector(selector, state="attached", timeout=self.nav_timeout_ms)
        except PlaywrightTimeoutError:
            logger.warning("%s iframe을 찾지 못했습니다: %s", self._log_prefix(), selector)
            raise
        return page.frame_locator(selector)

    def _click_tab_by_text(self, scope: Scope, container_selector: str, tab_name: str) -> bool:
        """탭 목록 컨테이너 안에서 이름이 ``tab_name``인 탭을 클릭한다.

        기존 Selenium ``BaseCrawler.click_tab``(리뷰/메뉴 탭 전환에 쓰던 것)을
        이식한 것이다. 탭 텍스트에 부가 정보(리뷰 개수 등)가 개행으로
        덧붙는 사이트가 많아, 원본과 동일하게 **첫 줄만** 비교한다. 위치
        기반(몇 번째 탭인지)이 아니라 텍스트로 찾으므로, 식당마다 탭 구성이
        달라 순서가 밀리는 경우에도 흔들리지 않는다.

        Args:
            scope: 탭 컨테이너가 들어있는 범위 (``Page``·``FrameLocator``·``Locator``).
            container_selector: 탭들을 감싸는 컨테이너 셀렉터.
            tab_name: 클릭할 탭의 표시 텍스트. 예) "메뉴"

        Returns:
            일치하는 탭을 찾아 클릭했으면 True, 컨테이너나 탭을 못 찾았으면 False.
        """
        container = scope.locator(container_selector)
        try:
            container.wait_for(state="visible", timeout=self.nav_timeout_ms)
        except PlaywrightTimeoutError:
            logger.warning(
                "%s 탭 컨테이너를 찾지 못했습니다: %s", self._log_prefix(), container_selector
            )
            return False

        tabs = container.locator("a")
        count = tabs.count()
        for i in range(count):
            tab = tabs.nth(i)
            full_text = tab.inner_text()
            first_line = full_text.split("\n")[0].strip()
            if first_line == tab_name:
                tab.click()
                return True

        logger.debug("%s 탭을 찾지 못했습니다: %s", self._log_prefix(), tab_name)
        return False

    # ------------------------------------------------------------------
    # 파싱 편의 (구현체용) — Page·FrameLocator·Locator 무엇이든 동일하게 다룬다
    # ------------------------------------------------------------------
    def _text_or_none(self, scope: Scope, selector: str) -> str | None:
        """``scope`` 범위에서 텍스트를 읽되, 없으면 None을 돌려준다.

        상세 페이지마다 있는 필드와 없는 필드가 섞여 있어서, 없는 필드 하나
        때문에 예외가 나는 상황을 피하려는 헬퍼다. 읽은 값은 **가공하지
        않는다** (정규화는 8번 파이프라인 책임).

        ``scope``에는 최상위 페이지(``Page``), iframe(``FrameLocator``),
        이미 좁혀둔 요소 하나(``Locator`` — 예: 목록 항목 ``li``)를 모두
        넘길 수 있다. 셋 다 ``.locator()``를 지원하므로 대상별로 함수를
        따로 만들 필요가 없다.
        """
        locator = scope.locator(selector).first
        try:
            if locator.count() == 0:
                return None
        except PlaywrightError as e:
            logger.debug("%s 셀렉터 조회 실패 %s: %s", self._log_prefix(), selector, e)
            return None
        return locator.inner_text()

    def _exists(self, scope: Scope, selector: str) -> bool:
        """``scope`` 범위에 ``selector``가 하나라도 있는지 확인한다.

        오류 배너 감지처럼 "있다/없다"만 필요하고 텍스트는 필요 없는
        곳에서 ``_text_or_none``보다 의도가 분명하다.
        """
        try:
            return scope.locator(selector).count() > 0
        except PlaywrightError:
            return False

    # ------------------------------------------------------------------
    # 하위 클래스가 채우는 훅
    # ------------------------------------------------------------------
    # crawl()은 구현하지 않는다. 이 클래스는 '어떻게 브라우저를 다루는가'만
    # 책임지고, '무엇을 어떤 셀렉터로 읽는가'는 소스별 구현체의 몫이기 때문이다.
    # 따라서 PlaywrightCrawler는 추상 클래스로 남으며 직접 인스턴스화되지 않는다.
