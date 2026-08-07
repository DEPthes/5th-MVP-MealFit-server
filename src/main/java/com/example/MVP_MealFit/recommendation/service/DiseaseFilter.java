package com.example.MVP_MealFit.recommendation.service;

import com.example.MVP_MealFit.analysis.domain.DiseaseIssue;
import com.example.MVP_MealFit.analysis.domain.NutrientIssue;
import com.example.MVP_MealFit.global.vo.Nutrition;
import com.example.MVP_MealFit.member.domain.Disease;
import org.springframework.stereotype.Component;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.EnumSet;
import java.util.List;
import java.util.Set;

/**
 * 회원의 기저질환(DiseaseIssue.ISSUE_MAP 재사용) → 메뉴 100g당 절대수치로 경고 문자열을
 * 만든다. 결과에서 메뉴를 빼지 않는다 — 검색 겸용 엔드포인트라 0건으로 만들면 검색이
 * 고장 난 것처럼 보인다. 경고 임계값은 홈 영양 필터 버튼(NutritionFilter)의 "좋은 것만
 * 남기는" 임계값과는 별개다 — 이건 "나쁜 것을 알리는" 임계값이다.
 */
@Component
public class DiseaseFilter {

    // 나트륨 600mg/100g 초과 — WHO 1일 나트륨 권장 2000mg 기준 한 끼(약 667mg)에 근접
    private static final BigDecimal SODIUM_WARNING_MG = BigDecimal.valueOf(600);
    // 지방 15g/100g 초과
    private static final BigDecimal FAT_WARNING_G = BigDecimal.valueOf(15);
    // 탄수화물 40g/100g 초과. 당류 전용 컬럼이 없어 탄수화물로 근사한다
    private static final BigDecimal CARBOHYDRATE_WARNING_G = BigDecimal.valueOf(40);
    // 칼로리 250kcal/100g 초과
    private static final int CALORIE_WARNING_KCAL = 250;

    public List<String> warningsFor(List<Disease> diseases, Nutrition menu) {
        List<String> warnings = new ArrayList<>();
        if (diseases == null || diseases.isEmpty() || menu == null) {
            return warnings;
        }

        Set<NutrientIssue> issues = EnumSet.noneOf(NutrientIssue.class);
        for (Disease disease : diseases) {
            List<NutrientIssue> mapped = DiseaseIssue.ISSUE_MAP.get(disease);
            if (mapped != null) {
                issues.addAll(mapped);
            }
        }

        if (issues.contains(NutrientIssue.SODIUM) && exceeds(menu.getSodium(), SODIUM_WARNING_MG)) {
            warnings.add("나트륨 함량이 높은 메뉴예요");
        }
        if (issues.contains(NutrientIssue.FAT) && exceeds(menu.getFat(), FAT_WARNING_G)) {
            warnings.add("지방 함량이 높은 메뉴예요");
        }
        if ((issues.contains(NutrientIssue.CARBOHYDRATE_SUGAR) || issues.contains(NutrientIssue.CARBOHYDRATE))
                && exceeds(menu.getCarbohydrate(), CARBOHYDRATE_WARNING_G)) {
            warnings.add("탄수화물 함량이 높은 메뉴예요");
        }
        if (issues.contains(NutrientIssue.CALORIE) && menu.getCalories() != null
                && menu.getCalories() > CALORIE_WARNING_KCAL) {
            warnings.add("칼로리가 높은 메뉴예요");
        }
        // DIETARY_FIBER, SATURATED_FAT, IRRITATING_FOOD는 판정 불가 — official_food에
        // 칼로리·탄·단·지·나트륨 5종뿐이라 식이섬유·포화지방·자극성 데이터가 없다.
        // 데이터가 생기면 여기에 분기를 추가한다.

        return warnings;
    }

    private boolean exceeds(BigDecimal value, BigDecimal threshold) {
        return value != null && value.compareTo(threshold) > 0;
    }
}
