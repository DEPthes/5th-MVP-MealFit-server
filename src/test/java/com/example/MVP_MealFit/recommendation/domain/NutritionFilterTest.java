package com.example.MVP_MealFit.recommendation.domain;

import com.example.MVP_MealFit.global.vo.Nutrition;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;

import static org.assertj.core.api.Assertions.assertThat;

class NutritionFilterTest {

    @Test
    void 고단백_기준_11g_이상만_통과한다() {
        Nutrition 고단백 = Nutrition.official(150, BigDecimal.valueOf(10), BigDecimal.valueOf(11), BigDecimal.valueOf(5));
        Nutrition 저단백 = Nutrition.official(150, BigDecimal.valueOf(10), BigDecimal.valueOf(10.9), BigDecimal.valueOf(5));

        assertThat(NutritionFilter.HIGH_PROTEIN.matches(고단백)).isTrue();
        assertThat(NutritionFilter.HIGH_PROTEIN.matches(저단백)).isFalse();
    }

    @Test
    void 저탄수_기준_20g_이하만_통과한다() {
        Nutrition 저탄수 = Nutrition.official(150, BigDecimal.valueOf(20), BigDecimal.valueOf(5), BigDecimal.valueOf(5));
        Nutrition 고탄수 = Nutrition.official(150, BigDecimal.valueOf(20.1), BigDecimal.valueOf(5), BigDecimal.valueOf(5));

        assertThat(NutritionFilter.LOW_CARB.matches(저탄수)).isTrue();
        assertThat(NutritionFilter.LOW_CARB.matches(고탄수)).isFalse();
    }

    @Test
    void 고탄수_기준_40g_이상만_통과한다() {
        Nutrition 고탄수 = Nutrition.official(150, BigDecimal.valueOf(40), BigDecimal.valueOf(5), BigDecimal.valueOf(5));
        Nutrition 저탄수 = Nutrition.official(150, BigDecimal.valueOf(39.9), BigDecimal.valueOf(5), BigDecimal.valueOf(5));

        assertThat(NutritionFilter.HIGH_CARB.matches(고탄수)).isTrue();
        assertThat(NutritionFilter.HIGH_CARB.matches(저탄수)).isFalse();
    }

    @Test
    void 저나트륨_기준_120mg_이하만_통과한다() {
        Nutrition 저나트륨 = Nutrition.official(150, BigDecimal.valueOf(10), BigDecimal.valueOf(5), BigDecimal.valueOf(5), BigDecimal.valueOf(120));
        Nutrition 고나트륨 = Nutrition.official(150, BigDecimal.valueOf(10), BigDecimal.valueOf(5), BigDecimal.valueOf(5), BigDecimal.valueOf(121));

        assertThat(NutritionFilter.LOW_SODIUM.matches(저나트륨)).isTrue();
        assertThat(NutritionFilter.LOW_SODIUM.matches(고나트륨)).isFalse();
    }

    @Test
    void 저지방_기준_3g_이하만_통과한다() {
        Nutrition 저지방 = Nutrition.official(150, BigDecimal.valueOf(10), BigDecimal.valueOf(5), BigDecimal.valueOf(3));
        Nutrition 고지방 = Nutrition.official(150, BigDecimal.valueOf(10), BigDecimal.valueOf(5), BigDecimal.valueOf(3.1));

        assertThat(NutritionFilter.LOW_FAT.matches(저지방)).isTrue();
        assertThat(NutritionFilter.LOW_FAT.matches(고지방)).isFalse();
    }

    @Test
    void 영양정보가_없으면_모든_필터가_통과하지_않는다() {
        for (NutritionFilter filter : NutritionFilter.values()) {
            assertThat(filter.matches(null)).isFalse();
        }
    }
}
