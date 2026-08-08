"""writer의 DB 적재 경로 통합 테스트. 실제 MySQL이 필요하다.

실행 방법은 conftest.py 참고. MEALFIT_TEST_DB_URL이 없으면 전부 건너뛴다.

이 테스트가 지키려는 것:
* 크롤러가 쓰는 컬럼명이 서버 엔티티와 어긋나면 즉시 실패한다
  (구 이름 distance_from_front_gate_m으로 되돌아가는 회귀를 막는다)
* 재적재해도 menu_id가 바뀌지 않는다 — 클라이언트가 들고 있는 참조가 깨지면 안 된다
* 좌표가 없으면 거리는 NULL이고, 그래도 적재 자체는 성공한다
"""

from __future__ import annotations

import pytest
from sqlalchemy import text

from app.pipeline.normalizer import NormalizedMenu, NormalizedRestaurant
from app.pipeline.writer import WriteReport, upsert_menus, upsert_restaurant, write_restaurant
from app.settings import settings

pytestmark = pytest.mark.integration

#: 테스트가 만드는 행을 알아볼 수 있게 하는 접두어. 뒷정리와 조회에 쓴다.
TEST_URL_PREFIX = "https://pytest.invalid/place/"

#: 명지대 정문(정류장) 좌표 — settings 기본값과 같아야 한다.
MAIN_GATE = (37.579132, 126.923488)


def make_restaurant(
    suffix: str = "1",
    latitude: float | None = MAIN_GATE[0],
    longitude: float | None = MAIN_GATE[1],
    menus: tuple[NormalizedMenu, ...] = (),
) -> NormalizedRestaurant:
    return NormalizedRestaurant(
        name=f"파이테스트식당{suffix}",
        address="서울시 서대문구 거북골로 34",
        cuisine="KOREAN",
        source_url=f"{TEST_URL_PREFIX}{suffix}",
        latitude=latitude,
        longitude=longitude,
        menus=menus,
    )


@pytest.fixture(autouse=True)
def cleanup(session):
    """테스트가 남긴 행을 지운다. session 픽스처가 롤백까지 하지만,
    커밋이 섞여도 안전하도록 이중으로 막는다."""
    yield
    session.execute(
        text(f"""
            DELETE FROM menu WHERE restaurant_id IN
                (SELECT id FROM restaurant WHERE source_url LIKE '{TEST_URL_PREFIX}%')
        """)
    )
    session.execute(
        text(f"DELETE FROM restaurant WHERE source_url LIKE '{TEST_URL_PREFIX}%'")
    )


class TestUpsertRestaurant:
    def test_서버가_읽는_거리_컬럼에_값이_들어간다(self, session):
        """구 컬럼명(distance_from_*_gate_m)으로 회귀하면 여기서 깨진다."""
        restaurant_id = upsert_restaurant(session, make_restaurant(), None, WriteReport())

        row = session.execute(
            text("""
                SELECT distance_to_main_gate, distance_to_back_gate
                FROM restaurant WHERE id = :id
            """),
            {"id": restaurant_id},
        ).one()

        # 정문 좌표에 세운 식당이므로 정문거리는 0
        assert row[0] == 0
        assert row[1] is not None and row[1] > 0

    def test_좌표가_없으면_거리는_NULL이지만_적재는_성공한다(self, session):
        restaurant_id = upsert_restaurant(
            session, make_restaurant(latitude=None, longitude=None), None, WriteReport()
        )

        row = session.execute(
            text("""
                SELECT distance_to_main_gate, distance_to_back_gate, latitude
                FROM restaurant WHERE id = :id
            """),
            {"id": restaurant_id},
        ).one()

        assert row[0] is None
        assert row[1] is None
        assert row[2] is None

    def test_같은_source_url은_새_행을_만들지_않는다(self, session):
        report = WriteReport()
        first_id = upsert_restaurant(session, make_restaurant(), None, report)
        second_id = upsert_restaurant(session, make_restaurant(), None, report)

        assert first_id == second_id

    def test_재적재하면_변경된_이름이_반영된다(self, session):
        report = WriteReport()
        upsert_restaurant(session, make_restaurant(), None, report)

        renamed = NormalizedRestaurant(
            name="이름바뀐식당",
            address="서울시 서대문구 거북골로 34",
            cuisine="KOREAN",
            source_url=f"{TEST_URL_PREFIX}1",
            latitude=MAIN_GATE[0],
            longitude=MAIN_GATE[1],
            menus=(),
        )
        restaurant_id = upsert_restaurant(session, renamed, None, report)

        name = session.execute(
            text("SELECT name FROM restaurant WHERE id = :id"), {"id": restaurant_id}
        ).scalar()
        assert name == "이름바뀐식당"


class TestUpsertMenus:
    def test_메뉴가_적재된다(self, session):
        restaurant_id = upsert_restaurant(session, make_restaurant(), None, WriteReport())
        menus = (
            NormalizedMenu(name="김치찌개", normalized_name="김치찌개", price=9000),
            NormalizedMenu(name="된장찌개", normalized_name="된장찌개", price=8500),
        )

        inserted, deduped = upsert_menus(session, restaurant_id, menus)

        assert inserted == 2
        assert deduped == 0
        count = session.execute(
            text("SELECT COUNT(*) FROM menu WHERE restaurant_id = :id"), {"id": restaurant_id}
        ).scalar()
        assert count == 2

    def test_정규화명이_같은_메뉴는_하나로_합쳐진다(self, session):
        """uk_menu_natural 위반을 배치 단계에서 미리 막는지 확인한다."""
        restaurant_id = upsert_restaurant(session, make_restaurant(), None, WriteReport())
        menus = (
            NormalizedMenu(name="김치찌개 (대)", normalized_name="김치찌개", price=11000),
            NormalizedMenu(name="김치찌개 (소)", normalized_name="김치찌개", price=9000),
        )

        inserted, deduped = upsert_menus(session, restaurant_id, menus)

        assert inserted == 1
        assert deduped == 1

    def test_재적재해도_menu_id가_바뀌지_않는다(self, session):
        """menu_id가 바뀌면 클라이언트가 들고 있던 참조가 깨진다."""
        restaurant_id = upsert_restaurant(session, make_restaurant(), None, WriteReport())
        menus = (NormalizedMenu(name="김치찌개", normalized_name="김치찌개", price=9000),)

        upsert_menus(session, restaurant_id, menus)
        first_id = session.execute(
            text("SELECT id FROM menu WHERE restaurant_id = :id"), {"id": restaurant_id}
        ).scalar()

        # 가격만 바뀐 채로 재적재
        upsert_menus(
            session,
            restaurant_id,
            (NormalizedMenu(name="김치찌개", normalized_name="김치찌개", price=9500),),
        )
        second_id, price = session.execute(
            text("SELECT id, price FROM menu WHERE restaurant_id = :id"), {"id": restaurant_id}
        ).one()

        assert second_id == first_id
        assert price == 9500


class TestWriteRestaurant:
    def test_식당과_메뉴가_함께_적재되고_리포트에_집계된다(self, session):
        report = WriteReport()
        restaurant = make_restaurant(
            menus=(
                NormalizedMenu(name="김치찌개", normalized_name="김치찌개", price=9000),
                NormalizedMenu(name="비빔밥", normalized_name="비빔밥", price=10000),
            )
        )

        write_restaurant(session, restaurant, report)

        assert report.restaurants_upserted == 1
        assert report.menus_upserted == 2
        assert report.menus_deduped == 0

    def test_적재된_식당은_서버_조회_조건을_만족한다(self, session):
        """서버 RecommendationService가 쓰는 조건(cuisine, 거리, normalized_name)이
        전부 채워지는지 — 적재는 됐는데 API에서 안 보이는 상황을 막는다."""
        report = WriteReport()
        restaurant = make_restaurant(
            menus=(NormalizedMenu(name="김치찌개", normalized_name="김치찌개", price=9000),)
        )
        write_restaurant(session, restaurant, report)

        row = session.execute(
            text(f"""
                SELECT r.cuisine, r.distance_to_main_gate, m.normalized_name, m.price
                FROM restaurant r
                JOIN menu m ON m.restaurant_id = r.id
                WHERE r.source_url = '{TEST_URL_PREFIX}1'
            """)
        ).one()

        assert row[0] == "KOREAN"
        assert row[1] is not None
        assert row[2] == "김치찌개"
        assert row[3] == 9000


class TestSettingsContract:
    def test_게이트_좌표가_설정에_들어있다(self, session):
        """좌표가 비면 거리가 전부 NULL로 적재된다 — 과거에 실제로 있었던 사고다."""
        assert settings.gate_main_lat is not None
        assert settings.gate_main_lng is not None
        assert settings.gate_back_lat is not None
        assert settings.gate_back_lng is not None
