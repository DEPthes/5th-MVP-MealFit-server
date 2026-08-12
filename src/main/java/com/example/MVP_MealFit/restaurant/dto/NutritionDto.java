package com.example.MVP_MealFit.restaurant.dto;

import com.example.MVP_MealFit.global.vo.Nutrition;
import com.example.MVP_MealFit.global.vo.NutritionSource;
import lombok.Builder;
import lombok.Getter;

import java.math.BigDecimal;

@Getter
@Builder
public class NutritionDto {

    private Integer calories;
    private BigDecimal carbohydrate;
    private BigDecimal protein;
    private BigDecimal fat;
    private NutritionSource source;
    private BigDecimal confidence;
    private BigDecimal sodium;

    public static NutritionDto from(Nutrition nutrition) {

        if (nutrition == null) {
            return null;
        }

        return NutritionDto.builder()
                .calories(nutrition.getCalories())
                .carbohydrate(nutrition.getCarbohydrate())
                .protein(nutrition.getProtein())
                .fat(nutrition.getFat())
                .source(nutrition.getSource())
                .confidence(nutrition.getConfidence())
                .sodium(nutrition.getSodium())
                .build();
    }



}
