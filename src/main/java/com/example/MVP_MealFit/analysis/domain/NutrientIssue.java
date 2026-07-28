package com.example.MVP_MealFit.analysis.domain;

/**
 * 부족 영양소 카드에 표시되는 영양 이슈 (FR-006)
 * 시트5 질환별 매핑 + 단백질(고정) + 대체 이슈
 */
public enum NutrientIssue {
    PROTEIN("단백질"),                       // 카드1 고정
    CARBOHYDRATE_SUGAR("탄수화물·당류 관리"),   // 당뇨 1순위
    DIETARY_FIBER("식이섬유"),                // 당뇨·고지혈증 2순위 (병합)
    SODIUM("나트륨 제한"),                    // 고혈압 1순위
    SATURATED_FAT("포화지방 관리"),            // 고혈압 2순위
    FAT("지방 관리"),                        // 고지혈증·역류성 (병합 여부 회의 대기)
    IRRITATING_FOOD("자극적인 음식 회피"),      // 역류성 2순위
    CALORIE("칼로리"),                       // 대체 이슈
    CARBOHYDRATE("탄수화물"),                 // 대체 이슈
    ;

    private final String label;

    NutrientIssue(String label) {
        this.label = label;
    }

    public String getLabel() {
        return label;
    }
}