"""Kakao Local API(주소 검색)로 주소를 좌표로 바꾼다.

문서: https://developers.kakao.com/docs/latest/ko/local/dev-guide#address-coord
주의: Kakao 응답의 x=경도(longitude), y=위도(latitude) — 관례적인 (lat, lng)
순서와 반대이므로 여기서만 뒤집어 돌려준다. 이 모듈 밖에서는 항상 (lat, lng)다.
"""

from __future__ import annotations

import logging

import requests
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed

logger = logging.getLogger(__name__)

_ENDPOINT = "https://dapi.kakao.com/v2/local/search/address.json"


class KakaoGeocoder:
    def __init__(self, api_key: str, timeout: float = 5.0):
        self._headers = {"Authorization": f"KakaoAK {api_key}"}
        self._timeout = timeout

    @retry(
        retry=retry_if_exception_type(requests.exceptions.RequestException),
        stop=stop_after_attempt(2),
        wait=wait_fixed(1.0),
        reraise=True,
    )
    def geocode(self, address: str) -> tuple[float, float] | None:
        """주소 -> (lat, lng). 매칭 결과가 없으면 None (예외 아님)."""
        resp = requests.get(
            _ENDPOINT,
            params={"query": address},
            headers=self._headers,
            timeout=self._timeout,
        )
        resp.raise_for_status()
        documents = resp.json().get("documents", [])
        if not documents:
            logger.warning("지오코딩 매칭 실패: %r", address)
            return None

        top = documents[0]
        return float(top["y"]), float(top["x"])  # (lat, lng)
