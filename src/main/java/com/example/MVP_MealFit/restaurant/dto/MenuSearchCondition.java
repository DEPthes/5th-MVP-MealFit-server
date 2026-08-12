package com.example.MVP_MealFit.restaurant.dto;

import com.example.MVP_MealFit.restaurant.domain.Cuisine;
import com.example.MVP_MealFit.restaurant.domain.FoodType;
import lombok.Getter;
import lombok.Setter;

@Getter
@Setter
public class MenuSearchCondition {

    // 검색 키워드
    private String keyword;

    // 음식 종류
    private Cuisine cuisine;

    // 세부 음식 종류
    private FoodType foodType;
}
