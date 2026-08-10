package com.example.MVP_MealFit.recommendation.service;

import com.example.MVP_MealFit.global.vo.Nutrition;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;

import static org.assertj.core.api.Assertions.assertThat;

class MatchScorerTest {

    private final MatchScorer scorer = new MatchScorer();

    @Test
    void 목표와_메뉴의_탄단지_비율이_같으면_매칭률_100이다() {
        Nutrition nutrition = Nutrition.official(300, BigDecimal.valueOf(37.5), BigDecimal.valueOf(22.5), BigDecimal.valueOf(6.67));

        Double matchRate = scorer.score(nutrition, nutrition);

        assertThat(matchRate).isEqualTo(100.0);
    }

    @Test
    void 탄단지_비율이_정반대면_매칭률_0이다() {
        // 탄수화물만: 비율(1,0,0) vs 지방만: 비율(0,0,1) -> TVD=2 -> matchRate=0
        Nutrition 탄수화물만 = Nutrition.official(400, BigDecimal.valueOf(100), BigDecimal.ZERO, BigDecimal.ZERO);
        Nutrition 지방만 = Nutrition.official(900, BigDecimal.ZERO, BigDecimal.ZERO, BigDecimal.valueOf(100));

        Double matchRate = scorer.score(탄수화물만, 지방만);

        assertThat(matchRate).isEqualTo(0.0);
    }

    @Test
    void 목표가_없으면_null을_반환한다() {
        Nutrition menu = Nutrition.official(300, BigDecimal.valueOf(37.5), BigDecimal.valueOf(22.5), BigDecimal.valueOf(6.67));

        assertThat(scorer.score(null, menu)).isNull();
    }

    @Test
    void 메뉴에_영양정보가_없으면_null을_반환한다() {
        Nutrition target = Nutrition.official(300, BigDecimal.valueOf(37.5), BigDecimal.valueOf(22.5), BigDecimal.valueOf(6.67));
        Nutrition emptyMenu = Nutrition.official(null, null, null, null);

        assertThat(scorer.score(target, emptyMenu)).isNull();
    }
}
