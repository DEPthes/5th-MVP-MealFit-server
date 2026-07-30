package com.example.MVP_MealFit.analysis.service;

import com.example.MVP_MealFit.analysis.domain.Deficiency;
import com.example.MVP_MealFit.analysis.domain.NutrientIssue;
import com.example.MVP_MealFit.member.domain.Disease;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class DeficiencyResolverTest {

    private final DeficiencyResolver resolver = new DeficiencyResolver();

    @Test
    void 카드1은_항상_단백질이다() {
        List<Deficiency> cards = resolver.resolve(List.of());

        assertThat(cards.get(0).priority()).isEqualTo(1);
        assertThat(cards.get(0).issue()).isEqualTo(NutrientIssue.PROTEIN);
    }

    @Test
    void 항상_3장을_반환한다() {
        assertThat(resolver.resolve(List.of())).hasSize(3);
        assertThat(resolver.resolve(List.of(Disease.DIABETES))).hasSize(3);
        assertThat(resolver.resolve(List.of(
                Disease.DIABETES, Disease.HYPERTENSION, Disease.HYPERLIPIDEMIA
        ))).hasSize(3);
    }

    @Test
    void 질환없으면_단백질_다음은_대체이슈로_채운다() {
        List<Deficiency> cards = resolver.resolve(List.of());

        // 단백질 + 대체(칼로리, 탄수화물)
        assertThat(cards).extracting(Deficiency::issue)
                .containsExactly(
                        NutrientIssue.PROTEIN,
                        NutrientIssue.CALORIE,
                        NutrientIssue.CARBOHYDRATE
                );
    }

    @Test
    void 당뇨_고혈압은_각_1순위가_카드2_3이다() {
        List<Deficiency> cards = resolver.resolve(List.of(
                Disease.DIABETES, Disease.HYPERTENSION
        ));

        assertThat(cards).extracting(Deficiency::issue)
                .containsExactly(
                        NutrientIssue.PROTEIN,             // 카드1
                        NutrientIssue.CARBOHYDRATE_SUGAR,  // 당뇨 1순위
                        NutrientIssue.SODIUM               // 고혈압 1순위
                );
    }

    @Test
    void 중요도_순서를_지킨다_역류성보다_당뇨가_먼저() {
        // 역류성(4)을 먼저 넣어도 당뇨(1)가 우선
        List<Deficiency> cards = resolver.resolve(List.of(
                Disease.GASTROESOPHAGEAL_REFLUX, Disease.DIABETES
        ));

        assertThat(cards.get(1).issue()).isEqualTo(NutrientIssue.CARBOHYDRATE_SUGAR); // 당뇨 먼저
    }

    @Test
    void 같은_지방이슈는_병합되고_관련질환이_함께_담긴다() {
        // 고지혈증 1순위 FAT + 역류성 1순위 FAT → 병합
        List<Deficiency> cards = resolver.resolve(List.of(
                Disease.HYPERLIPIDEMIA, Disease.GASTROESOPHAGEAL_REFLUX
        ));

        Deficiency fatCard = cards.get(1);
        assertThat(fatCard.issue()).isEqualTo(NutrientIssue.FAT);
        assertThat(fatCard.relatedDiseases())
                .containsExactlyInAnyOrder(
                        Disease.HYPERLIPIDEMIA,
                        Disease.GASTROESOPHAGEAL_REFLUX
                );

        // 병합으로 자리가 남아 식이섬유가 카드3에 들어옴
        assertThat(cards.get(2).issue()).isEqualTo(NutrientIssue.DIETARY_FIBER);
    }

    @Test
    void 같은_식이섬유이슈도_병합된다() {
        // 당뇨 2순위 + 고지혈증 2순위 = 둘 다 식이섬유
        List<Deficiency> cards = resolver.resolve(List.of(
                Disease.DIABETES, Disease.HYPERLIPIDEMIA
        ));

        // 카드2·3: 당뇨1(탄수화물·당류), 고지혈증1(지방) — 1순위들이 먼저 채움
        assertThat(cards).extracting(Deficiency::issue)
                .containsExactly(
                        NutrientIssue.PROTEIN,
                        NutrientIssue.CARBOHYDRATE_SUGAR,  // 당뇨 1순위
                        NutrientIssue.FAT                  // 고지혈증 1순위
                );
    }
}