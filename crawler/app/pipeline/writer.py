"""DB 적재 — restaurant/menu 테이블의 쓰기 주인.

upsert 키:
  restaurant : source_url (기존 UNIQUE)
  menu       : (restaurant_id, normalized_name)  — uk_menu_natural

전삭제 후 재삽입은 하지 않는다. menu_id가 재적재마다 바뀌면 클라이언트가
들고 있던 참조가 깨지기 때문이다.

좌표는 restaurant 테이블 자체를 캐시로 쓴다: 같은 source_url의 기존 행에
이미 좌표가 있고 주소가 안 바뀌었으면 지오코딩 API를 다시 부르지 않는다.
"""

from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass, field

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.pipeline.distance import haversine_m
from app.pipeline.geocoder import KakaoGeocoder
from app.pipeline.normalizer import NormalizedMenu, NormalizedRestaurant
from app.settings import settings

logger = logging.getLogger(__name__)

_SELECT_EXISTING = text("""
    SELECT address, latitude, longitude
    FROM restaurant
    WHERE source_url = :source_url
""")

_UPSERT_RESTAURANT = text("""
    INSERT INTO restaurant
        (name, address, cuisine, source_url, latitude, longitude,
         distance_to_main_gate, distance_to_back_gate,
         crawled_at, created_at, updated_at)
    VALUES
        (:name, :address, :cuisine, :source_url, :latitude, :longitude,
         :dist_main, :dist_back,
         :now, :now, :now)
    AS new
    ON DUPLICATE KEY UPDATE
        name = new.name,
        address = new.address,
        cuisine = new.cuisine,
        latitude = new.latitude,
        longitude = new.longitude,
        distance_to_main_gate = new.distance_to_main_gate,
        distance_to_back_gate = new.distance_to_back_gate,
        crawled_at = new.crawled_at,
        updated_at = new.updated_at
""")

_SELECT_RESTAURANT_ID = text("SELECT id FROM restaurant WHERE source_url = :source_url")

_UPSERT_MENU = text("""
    INSERT INTO menu (restaurant_id, name, normalized_name, price)
    VALUES (:restaurant_id, :name, :normalized_name, :price)
    AS new
    ON DUPLICATE KEY UPDATE
        name = new.name,
        price = new.price
""")


@dataclass
class WriteReport:
    restaurants_upserted: int = 0
    restaurants_skipped: list[tuple[str, str]] = field(default_factory=list)  # (name, reason)
    menus_upserted: int = 0
    menus_deduped: int = 0
    geocoded: int = 0
    geocode_cache_hit: int = 0
    geocode_failed: int = 0

    def add_skip(self, name: str, reason: str) -> None:
        self.restaurants_skipped.append((name, reason))

    def summary(self) -> str:
        lines = [
            f"식당 적재 {self.restaurants_upserted}건, 건너뜀 {len(self.restaurants_skipped)}건",
            f"메뉴 적재 {self.menus_upserted}건, 정규화 후 중복 제거 {self.menus_deduped}건",
            f"지오코딩: 신규 {self.geocoded}건 / 캐시 재사용 {self.geocode_cache_hit}건 / 실패 {self.geocode_failed}건",
        ]
        for name, reason in self.restaurants_skipped:
            lines.append(f"  건너뜀: {name} — {reason}")
        return "\n".join(lines)


def _dedupe_menus(menus: tuple[NormalizedMenu, ...]) -> tuple[list[NormalizedMenu], int]:
    """같은 식당 안에서 normalized_name이 같아진 메뉴를 첫 항목 기준으로 합친다.
    (사이즈 표기 제거 등 정규화 과정에서 서로 다른 원문이 같은 정규화명으로
    수렴할 수 있다 — uk_menu_natural 위반을 막기 위해 배치 자체에서 정리한다.)
    """
    seen: dict[str, NormalizedMenu] = {}
    dup_count = 0
    for m in menus:
        if m.normalized_name in seen:
            dup_count += 1
            continue
        seen[m.normalized_name] = m
    return list(seen.values()), dup_count


def _distances(lat: float | None, lng: float | None) -> tuple[int | None, int | None]:
    """정문·후문 좌표가 설정돼 있을 때만 거리를 계산한다. 둘 중 하나라도
    없으면(식당 좌표 없음 / 게이트 좌표 미확정) 해당 거리는 None."""
    if lat is None or lng is None:
        return None, None

    dist_main = (
        haversine_m(lat, lng, settings.gate_main_lat, settings.gate_main_lng)
        if settings.gate_main_lat is not None and settings.gate_main_lng is not None
        else None
    )
    dist_back = (
        haversine_m(lat, lng, settings.gate_back_lat, settings.gate_back_lng)
        if settings.gate_back_lat is not None and settings.gate_back_lng is not None
        else None
    )
    return dist_main, dist_back


def resolve_location(
    session: Session,
    nr: NormalizedRestaurant,
    geocoder: KakaoGeocoder | None,
    report: WriteReport,
) -> tuple[float | None, float | None, int | None, int | None]:
    """좌표를 확보한다: 크롤링 값 → DB 캐시(같은 주소) → 지오코딩 API 순.

    Returns:
        (latitude, longitude, distance_to_main_gate, distance_to_back_gate)
    """
    if nr.latitude is not None and nr.longitude is not None:
        lat, lng = nr.latitude, nr.longitude
    else:
        existing = session.execute(_SELECT_EXISTING, {"source_url": nr.source_url}).first()
        if existing is not None and existing[0] == nr.address and existing[1] is not None:
            lat, lng = existing[1], existing[2]
            report.geocode_cache_hit += 1
        elif geocoder is not None:
            result = geocoder.geocode(nr.address)
            if result is None:
                report.geocode_failed += 1
                lat, lng = None, None
            else:
                lat, lng = result
                report.geocoded += 1
        else:
            lat, lng = None, None

    dist_main, dist_back = _distances(lat, lng)
    return lat, lng, dist_main, dist_back


def upsert_restaurant(
    session: Session,
    nr: NormalizedRestaurant,
    geocoder: KakaoGeocoder | None,
    report: WriteReport,
) -> int:
    lat, lng, dist_main, dist_back = resolve_location(session, nr, geocoder, report)
    now = dt.datetime.now()
    session.execute(
        _UPSERT_RESTAURANT,
        {
            "name": nr.name,
            "address": nr.address,
            "cuisine": nr.cuisine,
            "source_url": nr.source_url,
            "latitude": lat,
            "longitude": lng,
            "dist_main": dist_main,
            "dist_back": dist_back,
            "now": now,
        },
    )
    row = session.execute(_SELECT_RESTAURANT_ID, {"source_url": nr.source_url}).first()
    if row is None:  # pragma: no cover - upsert 직후이므로 정상 흐름에선 발생하지 않음
        raise RuntimeError(f"upsert 직후 restaurant를 못 찾음: {nr.source_url}")
    return row[0]


def upsert_menus(session: Session, restaurant_id: int, menus: tuple[NormalizedMenu, ...]) -> tuple[int, int]:
    deduped, dup_count = _dedupe_menus(menus)
    for m in deduped:
        session.execute(
            _UPSERT_MENU,
            {
                "restaurant_id": restaurant_id,
                "name": m.name,
                "normalized_name": m.normalized_name,
                "price": m.price,
            },
        )
    return len(deduped), dup_count


def write_restaurant(
    session: Session,
    nr: NormalizedRestaurant,
    report: WriteReport,
    geocoder: KakaoGeocoder | None = None,
) -> None:
    """식당 1건 + 메뉴 전체를 같은 트랜잭션으로 적재하고 report에 집계한다."""
    restaurant_id = upsert_restaurant(session, nr, geocoder, report)
    menu_count, dup_count = upsert_menus(session, restaurant_id, nr.menus)
    report.restaurants_upserted += 1
    report.menus_upserted += menu_count
    report.menus_deduped += dup_count
