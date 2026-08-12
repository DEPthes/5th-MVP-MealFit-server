package com.example.MVP_MealFit.recommendation.service;

import com.example.MVP_MealFit.global.vo.Nutrition;
import org.springframework.stereotype.Component;

import java.math.BigDecimal;
import java.math.RoundingMode;

/**
 * 목표와 메뉴의 탄단지 칼로리 비율을 TVD(총변동거리)로 비교해 0~100 매칭률을 낸다.
 * 총량이 아니라 균형을 본다. 목표 비율을 하드코딩하지 않고 넘겨받은 target Nutrition에서
 * 직접 유도한다 — TargetCalculator가 5:3:2 고정이라 현재는 항상 그 비율로 수렴하지만,
 * 나중에 TargetCalculator가 바뀌어도 이 클래스는 손댈 필요가 없다.
 */
@Component
public class MatchScorer {

    private static final int KCAL_PER_CARB = 4;
    private static final int KCAL_PER_PROTEIN = 4;
    private static final int KCAL_PER_FAT = 9;

    // 목표와 메뉴 각각의 탄단지 칼로리 비율을 비교한다. 둘 중 하나라도 계산 불가면 null —
    // 예외가 아니다. 영양정보가 없는 메뉴는 검색 결과에는 나오되 정렬에서 뒤로 간다.
    public Double score(Nutrition target, Nutrition menu) {
        double[] targetRatio = macroRatio(target);
        double[] menuRatio = macroRatio(menu);
        if (targetRatio == null || menuRatio == null) {
            return null;
        }

        double totalVariation = 0;
        for (int i = 0; i < targetRatio.length; i++) {
            totalVariation += Math.abs(targetRatio[i] - menuRatio[i]);
        }

        double matchRate = (1 - totalVariation / 2) * 100;
        return BigDecimal.valueOf(matchRate).setScale(1, RoundingMode.HALF_UP).doubleValue();
    }

    // [탄수화물, 단백질, 지방] 칼로리 비율. 값이 없거나 합계가 0이면 null.
    private double[] macroRatio(Nutrition n) {
        if (n == null || n.getCarbohydrate() == null || n.getProtein() == null || n.getFat() == null) {
            return null;
        }
        double carbKcal = n.getCarbohydrate().doubleValue() * KCAL_PER_CARB;
        double proteinKcal = n.getProtein().doubleValue() * KCAL_PER_PROTEIN;
        double fatKcal = n.getFat().doubleValue() * KCAL_PER_FAT;
        double total = carbKcal + proteinKcal + fatKcal;
        if (total <= 0) {
            return null;
        }
        return new double[] { carbKcal / total, proteinKcal / total, fatKcal / total };
    }
}
