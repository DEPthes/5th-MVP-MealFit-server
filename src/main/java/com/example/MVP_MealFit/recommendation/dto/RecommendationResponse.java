package com.example.MVP_MealFit.recommendation.dto;

import com.example.MVP_MealFit.recommendation.domain.MatchReason;
import com.example.MVP_MealFit.restaurant.dto.RestaurantResponse;
import lombok.Builder;
import lombok.Getter;

import java.util.List;

// 식당 카드 하나. RestaurantDetailResponse와 모양이 비슷하지만 재사용하지 않는다 —
// 상세는 식당의 전체 메뉴, 이건 검색·추천 조건에 걸린 메뉴만 담아 의미가 다르다.
@Getter
@Builder
public class RecommendationResponse {

    private RestaurantResponse restaurant;

    // 걸린 메뉴만, 관련도(matchReason) → 매칭률 순으로 정렬돼 있다
    private List<RecommendedMenuResponse> menus;

    private int matchedMenuCount;

    // 이 식당이 검색·추천 결과에 걸린 이유 (대표 메뉴 기준)
    private MatchReason matchReason;

    // 카드 우측 "00% MATCH" — 첫 메뉴의 matchRate. 목표치 없으면 null
    private Double topMatchRate;

    // FR-012 — 기준점으로부터의 직선거리(m). 식당 좌표가 없으면 null
    private Integer distanceMeters;

    // 도보 소요 시간(분). 거리가 없으면 null
    private Integer walkingMinutes;

    // 거리 계산에 쓰인 기준점 이름 (예: "명지대 정류장"). 화면에 "○○ 기준"으로 표시
    private String distanceBasis;
}
