package com.example.MVP_MealFit.analysis.service;

import com.example.MVP_MealFit.analysis.domain.Deficiency;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

/**
 * Gemini API 기반 요약/카드 설명 생성 (FR-006)
 * 코드가 산출한 부족 영양소 카드를 바탕으로 설명 문장만 생성한다.
 * 점수·판정 등 결정론적 값은 넘기지 않으며, AI 실패 시 fallback 처리.
 */
@Component
public class GeminiClient implements AiClient {

    private final RestClient restClient;
    private final String apiKey;
    private final String model;

    public GeminiClient(
            @Value("${gemini.api-key}") String apiKey,
            @Value("${gemini.model}") String model
    ) {
        this.apiKey = apiKey;
        this.model = model;
        this.restClient = RestClient.builder()
                .baseUrl("https://generativelanguage.googleapis.com")
                .build();
    }

    @Override
    public AiResult generate(int inbodyScore, List<Deficiency> deficiencies) {
        String prompt = buildPrompt(inbodyScore, deficiencies);

        try {
            Map<String, Object> requestBody = Map.of(
                    "contents", List.of(
                            Map.of("parts", List.of(Map.of("text", prompt)))
                    )
            );

            Map<String, Object> response = restClient.post()
                    .uri("/v1beta/models/{model}:generateContent?key={key}", model, apiKey)
                    .body(requestBody)
                    .retrieve()
                    .body(Map.class);

            String text = extractText(response);
            return parseResult(text, deficiencies);

        } catch (Exception e) {
            System.out.println("Gemini 호출 실패: " + e.getMessage());
            return buildFallback(deficiencies);
        }
    }

    private String buildPrompt(int inbodyScore, List<Deficiency> deficiencies) {
        StringBuilder cards = new StringBuilder();
        for (int i = 0; i < deficiencies.size(); i++) {
            cards.append(String.format("%d. %s%n", i + 1, deficiencies.get(i).issue().getLabel()));
        }

        return String.format("""
                당신은 영양 상담 도우미입니다.
                사용자의 인바디 점수는 %d점이고, 관리가 필요한 영양 이슈 카드는 다음과 같습니다:
                %s

                아래 형식의 JSON만 출력하세요. 코드블록이나 다른 설명은 붙이지 마세요.
                {
                  "summary": "전체 상황을 요약한 따뜻하고 간결한 조언 2~3문장",
                  "cardDescriptions": ["1번 카드 설명 1~2문장", "2번 카드 설명 1~2문장"]
                }

                규칙:
                - cardDescriptions는 카드 순서와 개수를 정확히 맞추세요 (총 %d개).
                - 모든 문장은 부드러운 '~요' 체로 끝맺어 주세요. (예: "권장해요", "좋아요", "시작해 보세요")
                - 의학적 진단이나 단정적 표현은 피하고 권유하는 어조로 작성하세요.
                - 점수나 수치를 새로 만들어내지 말고 주어진 정보만 사용하세요.
                """, inbodyScore, cards, deficiencies.size());
    }

    @SuppressWarnings("unchecked")
    private String extractText(Map<String, Object> response) {
        try {
            List<Map<String, Object>> candidates =
                    (List<Map<String, Object>>) response.get("candidates");
            Map<String, Object> content =
                    (Map<String, Object>) candidates.get(0).get("content");
            List<Map<String, Object>> parts =
                    (List<Map<String, Object>>) content.get("parts");
            return (String) parts.get(0).get("text");
        } catch (Exception e) {
            return null;
        }
    }

    private AiResult parseResult(String text, List<Deficiency> deficiencies) {
        if (text == null) return buildFallback(deficiencies);
        try {
            String summary = extractJsonString(text, "summary");
            List<String> descriptions = extractJsonArray(text, "cardDescriptions");

            if (summary == null || descriptions.isEmpty()
                    || descriptions.size() != deficiencies.size()) {
                return buildFallback(deficiencies);
            }
            return new AiResult(summary, descriptions);

        } catch (Exception e) {
            System.out.println("Gemini 응답 파싱 실패: " + e.getMessage());
            return buildFallback(deficiencies);
        }
    }

    private String extractJsonString(String json, String key) {
        java.util.regex.Matcher m = java.util.regex.Pattern
                .compile("\"" + key + "\"\\s*:\\s*\"((?:[^\"\\\\]|\\\\.)*)\"")
                .matcher(json);
        return m.find() ? unescape(m.group(1)) : null;
    }

    private List<String> extractJsonArray(String json, String key) {
        List<String> result = new java.util.ArrayList<>();
        java.util.regex.Matcher arr = java.util.regex.Pattern
                .compile("\"" + key + "\"\\s*:\\s*\\[(.*?)\\]", java.util.regex.Pattern.DOTALL)
                .matcher(json);
        if (arr.find()) {
            java.util.regex.Matcher items = java.util.regex.Pattern
                    .compile("\"((?:[^\"\\\\]|\\\\.)*)\"")
                    .matcher(arr.group(1));
            while (items.find()) {
                result.add(unescape(items.group(1)));
            }
        }
        return result;
    }

    private String unescape(String s) {
        return s.replace("\\n", "\n").replace("\\\"", "\"").replace("\\\\", "\\");
    }

    private AiResult buildFallback(List<Deficiency> deficiencies) {
        String issues = deficiencies.stream()
                .map(d -> d.issue().getLabel())
                .collect(Collectors.joining(", "));
        String summary = String.format("%s에 신경 쓰며 균형 잡힌 식단을 유지해보세요.", issues);

        List<String> descriptions = deficiencies.stream()
                .map(d -> String.format("%s 관리를 권장합니다.", d.issue().getLabel()))
                .collect(Collectors.toList());

        return new AiResult(summary, descriptions);
    }
}