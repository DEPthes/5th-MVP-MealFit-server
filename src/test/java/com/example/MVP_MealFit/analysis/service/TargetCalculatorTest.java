package com.example.MVP_MealFit.analysis.service;

import com.example.MVP_MealFit.global.vo.Nutrition;
import com.example.MVP_MealFit.member.domain.ActivityLevel;
import com.example.MVP_MealFit.member.domain.Goal;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class TargetCalculatorTest {

    private final TargetCalculator calculator = new TargetCalculator();

    @Test
    void 유지_목표는_TDEE를_그대로_사용한다() {
        // BMR 1500 x 활동계수 1.2 = 1800, 유지라서 가감 없음
        Nutrition result = calculator.calculate(1500, ActivityLevel.SEDENTARY, Goal.MAINTAIN);

        assertThat(result.getCalories()).isEqualTo(1800);
        assertThat(result.getCarbohydrate()).isEqualByComparingTo("225.00");
        assertThat(result.getProtein()).isEqualByComparingTo("135.00");
        assertThat(result.getFat()).isEqualByComparingTo("40.00");
    }

    @Test
    void 감량_목표는_500kcal를_뺀다() {
        // 2000 x 1.55 = 3100, 감량이라 -500
        Nutrition result = calculator.calculate(2000, ActivityLevel.MODERATE, Goal.LOSS);

        assertThat(result.getCalories()).isEqualTo(2600);
    }

    @Test
    void 증량_목표는_300kcal를_더한다() {
        // 1600 x 1.375 = 2200, 증량이라 +300
        Nutrition result = calculator.calculate(1600, ActivityLevel.LIGHT, Goal.GAIN);

        assertThat(result.getCalories()).isEqualTo(2500);
    }

    @Test
    void 계산_결과가_너무_낮으면_최소_칼로리로_보정한다() {
        // 1000 x 1.2 = 1200, 감량이면 700이 되므로 1200으로 올림
        Nutrition result = calculator.calculate(1000, ActivityLevel.SEDENTARY, Goal.LOSS);

        assertThat(result.getCalories()).isEqualTo(1200);
    }

    @Test
    void 활동량이_높을수록_목표_칼로리도_높다() {
        int 앉아서생활 = calculator.calculate(1500, ActivityLevel.SEDENTARY, Goal.MAINTAIN).getCalories();
        int 활동적 = calculator.calculate(1500, ActivityLevel.ACTIVE, Goal.MAINTAIN).getCalories();

        assertThat(활동적).isGreaterThan(앉아서생활);
    }
}