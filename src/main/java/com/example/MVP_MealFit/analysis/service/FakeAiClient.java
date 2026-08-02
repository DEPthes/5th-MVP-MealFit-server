package com.example.MVP_MealFit.analysis.service;

import com.example.MVP_MealFit.analysis.domain.Deficiency;
import org.springframework.stereotype.Component;

import java.util.List;
import java.util.stream.Collectors;

/**
 * AiClient의 가짜 구현 (OpenAI 연동 전 임시)
 * 실제 API 호출 없이 카드 내용을 조합한 템플릿 문장을 반환한다.
 * OpenAiClient 구현 후 교체 예정.
 */
//@Component
public class FakeAiClient implements AiClient {

    @Override
    public AiResult generate(int inbodyScore, List<Deficiency> deficiencies) {
        String issues = deficiencies.stream()
                .map(d -> d.issue().getLabel())
                .collect(Collectors.joining(", "));
        String summary = String.format("인바디 점수는 %d점입니다. %s에 신경 쓰세요.", inbodyScore, issues);

        List<String> descriptions = deficiencies.stream()
                .map(d -> String.format("%s 관리를 권장합니다.", d.issue().getLabel()))
                .collect(Collectors.toList());

        return new AiResult(summary, descriptions);
    }
}