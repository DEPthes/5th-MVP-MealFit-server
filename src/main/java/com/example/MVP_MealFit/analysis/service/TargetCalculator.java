package com.example.MVP_MealFit.analysis.service;

import com.example.MVP_MealFit.global.vo.Nutrition;
import com.example.MVP_MealFit.member.domain.ExerciseCount;
import com.example.MVP_MealFit.member.domain.ExerciseIntensity;
import com.example.MVP_MealFit.member.domain.Goal;
import org.springframework.stereotype.Component;

import java.math.BigDecimal;
import java.math.RoundingMode;

/**
 * 목표 영양치 계산 (FR-004-1)
 * BMR -> TDEE -> 목표 칼로리 -> 탄단지 분배
 * 활동계수는 주당 운동 횟수와 운동 강도를 조합해 산출한다.
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

    // 주당 운동 횟수별 기본 활동계수
    private static final double FACTOR_NONE = 1.2;
    private static final double FACTOR_ONE_TO_TWO = 1.375;
    private static final double FACTOR_THREE_TO_FOUR = 1.55;
    private static final double FACTOR_FIVE_TO_SIX = 1.725;

    // 운동 강도별 보정치 (중강도 기준 1.0)
    private static final double INTENSITY_LOW = 0.95;
    private static final double INTENSITY_MEDIUM = 1.0;
    private static final double INTENSITY_HIGH = 1.05;

    public Nutrition calculate(double bmr, ExerciseCount exerciseCount,
                               ExerciseIntensity exerciseIntensity, Goal goal) {
        double factor = activityFactor(exerciseCount, exerciseIntensity);
        int tdee = (int) Math.round(bmr * factor);
        int targetCalories = Math.max(tdee + goal.getCalorieAdjustment(), MIN_CALORIES);
        return splitMacros(targetCalories);
    }

    /** 주당 운동 횟수 기본 계수에 강도 보정치를 곱해 활동계수를 산출한다. */
    private double activityFactor(ExerciseCount count, ExerciseIntensity intensity) {
        double base = baseFactor(count);
        // 운동을 하지 않으면 강도는 반영하지 않는다
        if (count == null || count == ExerciseCount.NONE) {
            return base;
        }
        return base * intensityMultiplier(intensity);
    }

    private double baseFactor(ExerciseCount count) {
        if (count == null) {
            return FACTOR_NONE;
        }
        return switch (count) {
            case NONE -> FACTOR_NONE;
            case ONE_TO_TWO -> FACTOR_ONE_TO_TWO;
            case THREE_TO_FOUR -> FACTOR_THREE_TO_FOUR;
            case FIVE_TO_SIX -> FACTOR_FIVE_TO_SIX;
        };
    }

    private double intensityMultiplier(ExerciseIntensity intensity) {
        if (intensity == null) {
            return INTENSITY_MEDIUM;
        }
        return switch (intensity) {
            case LOW -> INTENSITY_LOW;
            case MEDIUM -> INTENSITY_MEDIUM;
            case HIGH -> INTENSITY_HIGH;
        };
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