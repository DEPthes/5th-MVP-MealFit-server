package com.example.MVP_MealFit.restaurant.domain;

import lombok.Getter;
import lombok.RequiredArgsConstructor;

@Getter
@RequiredArgsConstructor
public enum Cuisine {

    KOREAN("한식"),
    CHINESE("중식"),
    JAPANESE("일식"),
    WESTERN("양식"),

    // 향후 확장 대비용
    ASIAN("아시안"),
    SNACK("분식"),
    CAFE_DESSERT("카페/디저트"),
    ETC("기타");

    private final String displayName;
}
