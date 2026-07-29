package com.example.MVP_MealFit.analysis.service;

import com.example.MVP_MealFit.analysis.domain.Deficiency;

import java.util.List;

/**
 * AI 요약 문장 생성 (FR-006)
 * 코드가 산출한 부족 영양소 카드를 받아 설명 문장만 생성한다.
 * 점수·판정 등 결정론적 값은 넘기지 않는다.
 */
public interface AiClient {

    /**
     * 부족 영양소 카드 기반 요약 문장 생성
     * @param inbodyScore 인바디 점수 (문맥용)
     * @param deficiencies 부족 영양소 카드 목록
     * @return 사용자에게 보여줄 요약 문장
     */
    String summarize(int inbodyScore, List<Deficiency> deficiencies);
}