package com.example.MVP_MealFit.analysis.dto;

import com.example.MVP_MealFit.global.vo.Nutrition;
import java.math.BigDecimal;

public record NutritionDto(
        Integer calories,
        BigDecimal carbohydrate,
        BigDecimal protein,
        BigDecimal fat
) {
    public static NutritionDto from(Nutrition n) {
        return new NutritionDto(
                n.getCalories(),
                n.getCarbohydrate(),
                n.getProtein(),
                n.getFat()
        );
    }
}