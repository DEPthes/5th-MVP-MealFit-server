package com.example.MVP_MealFit.analysis.domain;

import com.example.MVP_MealFit.member.domain.Disease;

import java.util.List;
import java.util.Map;

/**
 * 질환별 영양 이슈 매핑 (시트5)
 * 중요도 순서: 당뇨 > 고혈압 > 고지혈증 > 역류성식도염
 * 각 질환의 [1순위, 2순위] 이슈
 */
public final class DiseaseIssue {

    private DiseaseIssue() {}

    // 질환 중요도 순서 (작을수록 우선)
    public static final List<Disease> PRIORITY_ORDER = List.of(
            Disease.DIABETES,                 // 1
            Disease.HYPERTENSION,             // 2
            Disease.HYPERLIPIDEMIA,           // 3
            Disease.GASTROESOPHAGEAL_REFLUX   // 4
    );

    // 질환 → [1순위 이슈, 2순위 이슈]
    public static final Map<Disease, List<NutrientIssue>> ISSUE_MAP = Map.of(
            Disease.DIABETES, List.of(
                    NutrientIssue.CARBOHYDRATE_SUGAR,  // 1순위: 탄수화물·당류
                    NutrientIssue.DIETARY_FIBER        // 2순위: 식이섬유
            ),
            Disease.HYPERTENSION, List.of(
                    NutrientIssue.SODIUM,              // 1순위: 나트륨
                    NutrientIssue.SATURATED_FAT        // 2순위: 포화지방
            ),
            Disease.HYPERLIPIDEMIA, List.of(
                    NutrientIssue.FAT,                 // 1순위: 지방
                    NutrientIssue.DIETARY_FIBER        // 2순위: 식이섬유
            ),
            Disease.GASTROESOPHAGEAL_REFLUX, List.of(
                    NutrientIssue.FAT,                 // 1순위: 지방
                    NutrientIssue.IRRITATING_FOOD      // 2순위: 자극적 음식
            )
    );

    // 대체 이슈 순서 (질환 이슈 부족 시): 칼로리 → 탄수화물 → 지방
    public static final List<NutrientIssue> FALLBACK_ORDER = List.of(
            NutrientIssue.CALORIE,
            NutrientIssue.CARBOHYDRATE,
            NutrientIssue.FAT
    );
}