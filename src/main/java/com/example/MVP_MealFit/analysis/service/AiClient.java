package com.example.MVP_MealFit.analysis.service;

import com.example.MVP_MealFit.analysis.domain.Deficiency;

import java.util.List;

/**
 * AI 요약 문장 생성 (FR-006)
 * 코드가 산출한 부족 영양소 카드를 받아 설명 문장만 생성한다.
 * 점수·판정 등 결정론적 값은 넘기지 않는다.
 */
public interface AiClient {

    AiResult generate(int inbodyScore, List<Deficiency> deficiencies);
}