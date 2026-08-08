"""소스별 크롤러의 추상 기반 클래스.

Spring 설계의 ``RestaurantCrawler`` 인터페이스와 대응되는 Python 측 정의다.
소스를 교체하거나 추가할 때 이 인터페이스만 구현하면 파이프라인·CLI는 무수정으로
동작하는 것이 목적이다.

구현체가 반드시 지켜야 할 계약
------------------------------
1. ``crawl()``은 언제나 :class:`~app.model.raw.RawRestaurant` 리스트를 반환한다.
   도메인 객체 생성·DB 접근은 금지(8번 파이프라인의 몫).
2. ``source_name``은 소스를 식별하는 소문자 문자열이며, 로그 접두사와
   ``CrawlerFactory`` 등록 키로 쓰인다.
3. 리소스를 쓰는 구현체는 ``with`` 블록으로 수명을 관리한다.
   기반 클래스가 무동작 컨텍스트 매니저를 제공하므로, 리소스가 없는 구현체도
   호출부는 동일하게 ``with`` 를 쓸 수 있다.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from types import TracebackType
from typing import ClassVar

from app.model.raw import CrawlTarget, RawRestaurant

logger = logging.getLogger(__name__)


class RestaurantCrawler(ABC):
    """모든 소스 크롤러가 상속하는 인터페이스."""

    #: 소스 식별자. 예) 'naver', 'baemin'
    #: 구현체가 클래스 속성으로 반드시 덮어써야 한다.
    source_name: ClassVar[str] = ""

    # ------------------------------------------------------------------
    # 핵심 계약
    # ------------------------------------------------------------------
    @abstractmethod
    def crawl(self, target: CrawlTarget) -> list[RawRestaurant]:
        """대상 지역/키워드를 수집해 원시 dataclass 리스트를 반환한다.

        Args:
            target: 수집 대상(지역·검색어·상한).

        Returns:
            수집된 :class:`RawRestaurant` 목록. 결과가 없으면 빈 리스트.
            ``len(result) <= target.max_count`` 를 구현체가 보장한다.

        Note:
            개별 식당 파싱 실패는 예외로 올리지 말고 건너뛰며 경고 로그를 남긴다.
            한 건의 결함이 배치 전체를 중단시키면 안 된다. 브라우저 기동 실패처럼
            수집 자체가 불가능한 상황만 예외로 전파한다.
        """

    # ------------------------------------------------------------------
    # 수명 관리 (리소스를 쓰는 구현체가 오버라이드)
    # ------------------------------------------------------------------
    def __enter__(self) -> RestaurantCrawler:
        """기본 구현은 무동작. 리소스가 필요한 구현체가 오버라이드한다."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> bool:
        """기본 구현은 무동작.

        Returns:
            항상 ``False`` — 블록 안에서 발생한 예외를 삼키지 않는다.
        """
        return False

    # ------------------------------------------------------------------
    # 공통 편의
    # ------------------------------------------------------------------
    def _log_prefix(self) -> str:
        """로그 메시지 앞에 붙일 소스 식별 문자열."""
        return f"[{self.source_name or self.__class__.__name__}]"

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} source={self.source_name!r}>"
