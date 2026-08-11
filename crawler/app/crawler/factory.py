"""source 문자열로 알맞은 크롤러 구현체를 만든다.

신규 소스를 추가할 때 이 파일의 ``_registry`` 한 줄만 늘리면 되고,
``main.py``나 파이프라인 쪽 코드는 손댈 필요가 없다.
"""

from __future__ import annotations

from typing import Any

from app.crawler.base import RestaurantCrawler
from app.crawler.naver_map import NaverMapCrawler


class CrawlerFactory:
    """등록된 소스 이름으로 크롤러 인스턴스를 생성한다."""

    _registry: dict[str, type[RestaurantCrawler]] = {
        "naver": NaverMapCrawler,
    }

    @staticmethod
    def create(source: str, **kwargs: Any) -> RestaurantCrawler:
        """``source``에 해당하는 크롤러를 생성해 반환한다.

        Args:
            source: 소스 식별자. 예) "naver"
            **kwargs: 크롤러 생성자에 그대로 전달할 인자
                (``headless``, ``request_delay`` 등).

        Returns:
            생성된 크롤러 인스턴스. 아직 ``with`` 블록에 들어가지 않은 상태.

        Raises:
            ValueError: 등록되지 않은 소스인 경우. 현재 등록된 소스 목록을
                메시지에 포함해, 오타를 바로 알아챌 수 있게 한다.
        """
        crawler_cls = CrawlerFactory._registry.get(source)
        if crawler_cls is None:
            registered = ", ".join(sorted(CrawlerFactory._registry)) or "(없음)"
            raise ValueError(
                f"등록되지 않은 소스입니다: {source!r}. 등록된 소스: {registered}"
            )
        return crawler_cls(**kwargs)
