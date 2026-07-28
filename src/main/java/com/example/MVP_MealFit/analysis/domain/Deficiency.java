package com.example.MVP_MealFit.analysis.domain;

import com.example.MVP_MealFit.member.domain.Disease;

import java.util.List;

/**
 * 부족 영양소 카드 1장 (FR-006)
 * @param priority 카드 순서 (1=단백질 고정, 2·3=질환 이슈)
 * @param issue 영양 이슈
 * @param relatedDiseases 관련 질환 (병합 시 여러 개, 단백질/대체 이슈는 비어있음)
 */
public record Deficiency(
        int priority,
        NutrientIssue issue,
        List<Disease> relatedDiseases
) {
}