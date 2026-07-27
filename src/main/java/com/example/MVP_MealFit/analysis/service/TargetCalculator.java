package com.example.MVP_MealFit.analysis.service;

import com.example.MVP_MealFit.global.vo.Nutrition;
import com.example.MVP_MealFit.member.domain.ActivityLevel;
import com.example.MVP_MealFit.member.domain.Goal;
import org.springframework.stereotype.Component;

import java.math.BigDecimal;
import java.math.RoundingMode;

/**
 * 목표 영양치 계산 (FR-004-1)
 * BMR -> TDEE -> 목표 칼로리 -> 탄단지 분배
 * AI를 쓰지 않고 고정 공식으로만 계산한다.
 */
@Component
public class TargetCalculator {

    // 매크로 비율 (탄:단:지) (5:3:2)
    private static final double CARB_RATIO = 0.5;
    private static final double PROTEIN_RATIO = 0.3;
    private static final double FAT_RATIO = 0.2;

    // 영양소 1g당 칼로리 
    private static final int KCAL_PER_CARB = 4;
    private static final int KCAL_PER_PROTEIN = 4;
    private static final int KCAL_PER_FAT = 9;

    // 안전 하한선
    private static final int MIN_CALORIES = 1200;

    public Nutrition calculate(double bmr, ActivityLevel activityLevel, Goal goal) {
        int tdee = (int) Math.round(bmr * activityLevel.getFactor());
        int targetCalories = Math.max(tdee + goal.getCalorieAdjustment(), MIN_CALORIES);
        return splitMacros(targetCalories);
    }

    private Nutrition splitMacros(int calories) {
        return Nutrition.official(
                calories,
                grams(calories, CARB_RATIO, KCAL_PER_CARB),
                grams(calories, PROTEIN_RATIO, KCAL_PER_PROTEIN),
                grams(calories, FAT_RATIO, KCAL_PER_FAT)
        );
    }

    private BigDecimal grams(int calories, double ratio, int kcalPerGram) {
        return BigDecimal.valueOf(calories * ratio / kcalPerGram)
                .setScale(2, RoundingMode.HALF_UP);
    }
}