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
@Component
public class FakeAiClient implements AiClient {

    @Override
    public String summarize(int inbodyScore, List<Deficiency> deficiencies) {
        String issues = deficiencies.stream()
                .map(d -> d.issue().getLabel())
                .collect(Collectors.joining(", "));

        return String.format(
                "현재 인바디 점수는 %d점입니다. %s에 특히 신경 쓰는 것이 좋겠습니다. "
                        + "균형 잡힌 식단으로 건강을 관리해보세요.",
                inbodyScore, issues
        );
    }
}