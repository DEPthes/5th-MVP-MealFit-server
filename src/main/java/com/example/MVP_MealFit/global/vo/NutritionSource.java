package com.example.MVP_MealFit.global.vo;

public enum NutritionSource {
    OFFICIAL,   // 공식 데이터 (예: 식약처 DB) - confidence 없음
    ESTIMATED   // AI 추정치 - confidence 있음
}
