package com.example.MVP_MealFit.restaurant.domain;

import lombok.Getter;
import lombok.RequiredArgsConstructor;

@Getter
@RequiredArgsConstructor
public enum FoodType {

    MEAT("고기"),
    NOODLE("면"),
    RICE("밥"),
    SOUP("찌개/국"),
    SNACK("분식"),

    // 향후 확장 대비용
    SALAD("샐러드"),
    SEAFOOD("해산물"),
    FRIED("튀김"),
    DESSERT("디저트"),
    PIZZA("피자"),
    SANDWICH("샌드위치");

    private final String displayName;

}
