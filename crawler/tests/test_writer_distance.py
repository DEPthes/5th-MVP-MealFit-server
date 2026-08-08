"""writer._distances 단위 테스트. DB·네트워크·LLM 전부 불필요.

거리 컬럼은 Spring 서버가 그대로 읽어 API로 내보내는 값이라, 좌표 기본값이
서버 쪽 ReferencePoint와 어긋나면 앱에 잘못된 거리가 표시된다. 그 계약을
여기서 고정한다.
"""

from __future__ import annotations

from app.pipeline.distance import haversine_m
from app.pipeline.writer import _distances
from app.settings import settings

# Spring 서버 ReferencePoint.java가 확정한 좌표. 이 값이 바뀌면 서버도 같이 바꿔야 한다.
SERVER_MAIN_GATE = (37.579132, 126.923488)   # 명지대 정류장
SERVER_BACK_GATE = (37.5807266, 126.9244188)  # 명지대 도서관(방목학술정보관)

# FR-012 명세상 두 기준점 사이 직선거리
GATE_TO_GATE_M = 195
GATE_TO_GATE_TOLERANCE_M = 5


class TestGateSettings:
    def test_기본_좌표가_서버_ReferencePoint와_일치한다(self):
        assert (settings.gate_main_lat, settings.gate_main_lng) == SERVER_MAIN_GATE
        assert (settings.gate_back_lat, settings.gate_back_lng) == SERVER_BACK_GATE

    def test_두_기준점_사이_거리는_명세대로_195m_안팎이다(self):
        distance = haversine_m(*SERVER_MAIN_GATE, *SERVER_BACK_GATE)

        assert abs(distance - GATE_TO_GATE_M) <= GATE_TO_GATE_TOLERANCE_M


class TestDistances:
    def test_식당_좌표가_없으면_두_거리_모두_None이다(self):
        assert _distances(None, None) == (None, None)
        assert _distances(37.5, None) == (None, None)
        assert _distances(None, 126.9) == (None, None)

    def test_정문_좌표에_있는_식당은_정문거리가_0이다(self):
        dist_main, dist_back = _distances(*SERVER_MAIN_GATE)

        assert dist_main == 0
        assert abs(dist_back - GATE_TO_GATE_M) <= GATE_TO_GATE_TOLERANCE_M

    def test_후문_좌표에_있는_식당은_후문거리가_0이다(self):
        dist_main, dist_back = _distances(*SERVER_BACK_GATE)

        assert abs(dist_main - GATE_TO_GATE_M) <= GATE_TO_GATE_TOLERANCE_M
        assert dist_back == 0

    def test_거리는_정수_미터로_반환된다(self):
        # restaurant.distance_to_main_gate가 INT 컬럼이라 소수가 들어가면 안 된다.
        dist_main, dist_back = _distances(37.5799, 126.9240)

        assert isinstance(dist_main, int)
        assert isinstance(dist_back, int)

    def test_명지대_인근_식당은_두_거리_모두_1km_미만이다(self):
        dist_main, dist_back = _distances(37.5799, 126.9240)

        assert 0 < dist_main < 1000
        assert 0 < dist_back < 1000
