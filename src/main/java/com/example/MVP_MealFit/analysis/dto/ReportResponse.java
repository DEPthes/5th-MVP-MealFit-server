package com.example.MVP_MealFit.analysis.dto;

import java.util.List;

public record ReportResponse(
        int healthScore,
        NutritionDto dailyTarget,
        List<DeficiencyDto> deficiencies,
        Long basisInbodyId
) {
}