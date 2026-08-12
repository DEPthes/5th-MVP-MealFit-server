package com.example.MVP_MealFit.recommendation.dto;

import com.example.MVP_MealFit.recommendation.domain.NutritionFilter;
import com.example.MVP_MealFit.recommendation.domain.ReferencePoint;
import com.example.MVP_MealFit.restaurant.domain.Cuisine;
import com.example.MVP_MealFit.restaurant.domain.FoodType;
import lombok.Getter;
import lombok.Setter;

@Getter
@Setter
public class RecommendationCondition {

    // 검색 키워드
    private String keyword;

    // 화면 "1. 음식 종류" 칩
    private Cuisine cuisine;

    // 화면 "2. 세부 종류" 칩
    private FoodType foodType;

    // 홈 화면 영양 필터 버튼 (한 번에 하나만)
    private NutritionFilter nutritionFilter;

    // FR-010 가격대 필터 (예: 10000 = 1만원 이하). 안 보내면 가격 무관
    private Integer maxPrice;

    // FR-012 거리 계산 기준점. 안 보내면 MAIN_GATE(명지대 정류장)
    private ReferencePoint referencePoint;
}
