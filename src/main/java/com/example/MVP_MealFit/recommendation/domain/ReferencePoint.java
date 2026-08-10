package com.example.MVP_MealFit.recommendation.domain;

import com.example.MVP_MealFit.restaurant.domain.Restaurant;
import lombok.Getter;

/**
 * FR-012 — 경로 안내(네이버 지도 핸드오프)에 쓰이는 고정 기준점. 사용자의 실시간 GPS
 * 위치가 아니라 이 두 지점 중 하나로부터의 거리를 쓴다.
 * <p>
 * 거리 자체는 여기서 계산하지 않는다 — Python 크롤러가 적재 시점에 미리 계산해
 * restaurant.distance_to_main_gate / distance_to_back_gate 컬럼에 넣어 두고,
 * 여기서는 그중 어느 컬럼을 볼지만 고른다. 계산 로직의 주인은 크롤러 쪽
 * (app/pipeline/distance.py의 haversine_m)이다.
 */
@Getter
public enum ReferencePoint {

    // 정문 방향 — 명지대 정류장(동일명 정류장이 양방향에 있어 도서관과 더 떨어진 쪽으로 확정)
    MAIN_GATE("명지대 정류장"),

    // 후문 방향 — 명지대 도서관(방목학술정보관)
    BACK_GATE("명지대 도서관");

    private final String displayName;

    ReferencePoint(String displayName) {
        this.displayName = displayName;
    }

    // 크롤러가 미리 계산해 적재한 거리(m). 값이 없으면 null
    public Integer distanceMetersTo(Restaurant restaurant) {
        return switch (this) {
            case MAIN_GATE -> restaurant.getDistanceToMainGate();
            case BACK_GATE -> restaurant.getDistanceToBackGate();
        };
    }
}
