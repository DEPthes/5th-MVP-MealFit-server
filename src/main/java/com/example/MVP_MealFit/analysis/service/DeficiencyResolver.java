package com.example.MVP_MealFit.analysis.service;

import com.example.MVP_MealFit.analysis.domain.Deficiency;
import com.example.MVP_MealFit.analysis.domain.DiseaseIssue;
import com.example.MVP_MealFit.analysis.domain.NutrientIssue;
import com.example.MVP_MealFit.member.domain.Disease;
import org.springframework.stereotype.Component;

import java.util.ArrayList;
import java.util.List;

/**
 * 부족 영양소 카드 3장 산출 (FR-006)
 * 카드1 = 단백질(고정), 카드2·3 = 기저질환 이슈
 * 규칙: 질환 중요도순 → 각 질환 1순위→2순위 → 같은 이슈 병합 → 부족 시 대체 이슈
 * AI 미개입, 결정론적 산출.
 */
@Component
public class DeficiencyResolver {

    private static final int MAX_CARDS = 3;

    public List<Deficiency> resolve(List<Disease> diseases) {
        List<Deficiency> cards = new ArrayList<>();

        // 카드1: 단백질 고정
        cards.add(new Deficiency(1, NutrientIssue.PROTEIN, List.of()));

        // 카드2·3 후보: 질환 이슈를 순서대로 수집 (병합 처리)
        List<Deficiency> diseaseCards = collectDiseaseIssues(diseases);

        // 대체 이슈로 부족분 채우기
        fillWithFallback(diseaseCards);

        // 최대 3장까지, priority 부여하며 추가
        for (Deficiency card : diseaseCards) {
            if (cards.size() >= MAX_CARDS) break;
            cards.add(new Deficiency(cards.size() + 1, card.issue(), card.relatedDiseases()));
        }

        return cards;
    }

    /**
     * 질환들을 중요도순으로 순회하며 이슈 수집.
     * 각 질환의 1순위 → 2순위 순서로 보되, 이미 나온 이슈면 관련 질환만 추가(병합).
     */
    private List<Deficiency> collectDiseaseIssues(List<Disease> diseases) {
        List<Deficiency> result = new ArrayList<>();

        // 우선순위: 1순위들을 먼저 다 돌고, 그다음 2순위들
        for (int rank = 0; rank < 2; rank++) {
            for (Disease disease : DiseaseIssue.PRIORITY_ORDER) {
                if (!diseases.contains(disease)) continue;

                List<NutrientIssue> issues = DiseaseIssue.ISSUE_MAP.get(disease);
                if (issues == null || rank >= issues.size()) continue;

                NutrientIssue issue = issues.get(rank);
                addOrMerge(result, issue, disease);
            }
        }
        return result;
    }

    /** 같은 이슈가 이미 있으면 관련 질환만 추가(병합), 없으면 새 카드 */
    private void addOrMerge(List<Deficiency> cards, NutrientIssue issue, Disease disease) {
        for (int i = 0; i < cards.size(); i++) {
            if (cards.get(i).issue() == issue) {
                List<Disease> merged = new ArrayList<>(cards.get(i).relatedDiseases());
                merged.add(disease);
                cards.set(i, new Deficiency(0, issue, merged));
                return;
            }
        }
        List<Disease> related = new ArrayList<>();
        related.add(disease);
        cards.add(new Deficiency(0, issue, related));
    }

    /** 질환 이슈가 3장(카드1 제외 2장)에 못 미치면 대체 이슈로 채움 */
    private void fillWithFallback(List<Deficiency> cards) {
        for (NutrientIssue fallback : DiseaseIssue.FALLBACK_ORDER) {
            if (cards.size() >= MAX_CARDS - 1) break;  // 카드1 제외 2장이면 충분
            boolean exists = cards.stream().anyMatch(c -> c.issue() == fallback);
            if (!exists) {
                cards.add(new Deficiency(0, fallback, List.of()));
            }
        }
    }
}