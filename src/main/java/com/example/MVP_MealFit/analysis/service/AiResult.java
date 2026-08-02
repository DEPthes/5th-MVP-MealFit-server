package com.example.MVP_MealFit.analysis.service;

import java.util.List;

/**
 * AI 생성 결과 (FR-006)
 * @param summary 전체 요약 문장
 * @param cardDescriptions 카드별 설명 문장 (카드 순서와 동일)
 */
public record AiResult(
        String summary,
        List<String> cardDescriptions
) {
}