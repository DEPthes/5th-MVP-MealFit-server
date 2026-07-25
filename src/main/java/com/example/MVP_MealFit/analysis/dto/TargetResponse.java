package com.example.MVP_MealFit.analysis.dto;

import com.example.MVP_MealFit.member.domain.NutritionTarget;
import java.time.LocalDateTime;

public record TargetResponse(
        NutritionDto dailyTarget,
        NutritionDto perMealTarget,
        Long basisInbodyId,
        LocalDateTime calculatedAt,
        boolean outdated
) {
    public static TargetResponse from(NutritionTarget target, boolean outdated) {
        return new TargetResponse(
                NutritionDto.from(target.getTarget()),
                NutritionDto.from(target.perMeal()),
                target.getSourceInbodyId(),
                target.getCalculatedAt(),
                outdated
        );
    }
}