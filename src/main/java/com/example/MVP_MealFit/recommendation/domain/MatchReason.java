package com.example.MVP_MealFit.recommendation.domain;

import lombok.Getter;
import lombok.RequiredArgsConstructor;

// 검색 결과에 이 메뉴/식당이 걸린 이유. 선언 순서가 곧 관련도 등급이다(ordinal() 사용) —
// 메뉴명 일치가 가장 위, 동의어로 넓혀진 태그 일치가 가장 아래.
@Getter
@RequiredArgsConstructor
public enum MatchReason {

    MENU_NAME("메뉴명"),
    RESTAURANT_NAME("식당명"),
    REPRESENTATIVE_FOOD("대표 식품"),
    FOOD_TYPE_TAG("음식 종류");

    private final String displayName;
}
