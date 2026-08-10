package com.example.MVP_MealFit.inbody.parser;

import com.example.MVP_MealFit.global.exception.BusinessException;
import com.example.MVP_MealFit.global.exception.ErrorCode;
import com.example.MVP_MealFit.inbody.ocr.ClovaOcrEngine;
import com.example.MVP_MealFit.inbody.ocr.ClovaOcrResponse;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockMultipartFile;
import tools.jackson.databind.ObjectMapper;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

/**
 * InbodyParser OCR 추출 테스트
 *
 * <p>OCR 응답 클래스에는 setter가 없으므로, 운영과 동일하게 JSON을 역직렬화해
 * 가짜 OCR 결과를 만든다. 파서가 좌표 기반으로 동작하므로 각 라벨과 값의
 * 상대 위치가 곧 테스트 입력이다.
 *
 * <p>아래 좌표 배치는 각 항목의 추출 조건을 동시에 만족시키면서,
 * 서로의 숫자를 잘못 주워오지 않도록 계산된 값이다.
 * <pre>
 * 항목          라벨 좌표      값 좌표        dx    dy
 * 체중          (100, 1000)   (500, 1020)   400    20
 * 골격근량       (100, 1100)   (500, 1120)   400    20
 * 체지방률       (100, 1200)   (650, 1220)   550    20
 * 기초대사량     (100, 1300)   (340, 1305)   240     5
 * 내장지방레벨   (100, 1400)   (120, 1450)    20    50
 * 인바디점수     (100, 1500)   (250, 1580)   150    80
 * </pre>
 */
class InbodyParserTest {

    private static final double VISCERAL_LABEL_X = 100;
    private static final double VISCERAL_LABEL_Y = 1400;

    private ClovaOcrEngine ocrEngine;
    private InbodyParser parser;

    @BeforeEach
    void setUp() {
        ocrEngine = mock(ClovaOcrEngine.class);
        parser = new InbodyParser(ocrEngine);
    }

    @Nested
    @DisplayName("정상 추출")
    class Success {

        @Test
        @DisplayName("모든 항목이 정상인 결과지에서 내장지방레벨을 포함한 전체 값을 추출한다")
        void extractsAllValues() {
            InbodyData data = parseWith(baseFields());

            assertThat(data.weight()).isEqualByComparingTo(new BigDecimal("68.5"));
            assertThat(data.skeletalMuscleMass()).isEqualByComparingTo(new BigDecimal("34.2"));
            assertThat(data.bodyFatPercentage()).isEqualByComparingTo(new BigDecimal("19.8"));
            assertThat(data.bmr()).isEqualTo(1620);
            assertThat(data.visceralFatLevel()).isEqualTo(8);
            assertThat(data.inbodyScore()).isEqualTo(80);
            assertThat(data.measuredAt()).isEqualTo(Optional.of(LocalDate.of(2026, 7, 25)));
        }

        @Test
        @DisplayName("라벨에 공백이 섞여도 내장지방레벨을 인식한다")
        void extractsWhenLabelHasWhitespace() {
            List<String> fields = baseFields();
            replaceText(fields, "내장지방레벨", "내장지방 레벨");

            assertThat(parseWith(fields).visceralFatLevel()).isEqualTo(8);
        }

        @Test
        @DisplayName("내장지방레벨이 허용 범위 경계값(1, 20)이면 추출된다")
        void extractsBoundaryValues() {
            assertThat(parseWithVisceralValue("1").visceralFatLevel()).isEqualTo(1);
            assertThat(parseWithVisceralValue("20").visceralFatLevel()).isEqualTo(20);
        }
    }

    /**
     * 아래 테스트들은 "이렇게 동작해야 한다"가 아니라
     * "현재 이렇게 동작한다"를 고정한 것이다.
     * 부분 실패 허용(등급제)을 도입하면 함께 수정되어야 한다.
     */
    @Nested
    @DisplayName("현재 한계 — 하나만 실패해도 업로드 전체가 막힌다")
    class CurrentLimitations {

        @Test
        @DisplayName("내장지방레벨 라벨이 없으면, 나머지 값이 모두 정상이어도 전체가 실패한다")
        void failsWhenLabelMissing() {
            List<String> fields = baseFields();
            removeText(fields, "내장지방레벨");

            assertParseFails(fields);
        }

        @Test
        @DisplayName("라벨이 한 글자만 오인식되어도 실패한다 (체지방률과 달리 대체 후보가 없음)")
        void failsWhenLabelMisrecognized() {
            List<String> fields = baseFields();
            replaceText(fields, "내장지방레벨", "내장지방래벨");

            assertParseFails(fields);
        }

        @Test
        @DisplayName("값이 라벨보다 조금이라도 왼쪽에 있으면 실패한다 (dx 최솟값이 0이라 음수 여유가 없음)")
        void failsWhenValueIsLeftOfLabel() {
            List<String> fields = baseFields();
            removeText(fields, "8");
            // dx = -10 : 값이 라벨 중앙보다 왼쪽에 정렬된 경우
            fields.add(fieldJson("8", VISCERAL_LABEL_X - 10, VISCERAL_LABEL_Y + 50));

            assertParseFails(fields);
        }

        @Test
        @DisplayName("내장지방레벨이 20을 초과하면 실패한다")
        void failsWhenValueExceedsRange() {
            List<String> fields = baseFields();
            removeText(fields, "8");
            fields.add(fieldJson("25", VISCERAL_LABEL_X + 20, VISCERAL_LABEL_Y + 50));

            assertParseFails(fields);
        }

        /**
         * 설계서 3.inbody 30행은 필수값 미검출 시 INBODY_PARSE_FAILED(422)를 규정하지만,
         * 실제로는 OCR_PARSE_FAILED(500)가 발생한다.
         * 500은 서버 장애로 분류되어 프론트가 "재업로드" 안내를 띄우기 어렵다.
         */
        @Test
        @DisplayName("추출 실패 시 오류 코드가 422가 아닌 500(OCR_PARSE_FAILED)이다")
        void failsWithServerErrorInsteadOfUnprocessable() {
            List<String> fields = baseFields();
            removeText(fields, "내장지방레벨");

            assertThatThrownBy(() -> parseWith(fields))
                    .isInstanceOf(BusinessException.class)
                    .extracting(e -> ((BusinessException) e).getErrorCode())
                    .isEqualTo(ErrorCode.OCR_PARSE_FAILED);
        }
    }

    // ============================================================
    // 헬퍼
    // ============================================================

    /** 모든 항목이 정상 인식된 인바디 결과지 */
    private List<String> baseFields() {
        List<String> fields = new ArrayList<>();

        fields.add(fieldJson("2026.07.25", 700, 200));

        fields.add(fieldJson("체중", 100, 1000));
        fields.add(fieldJson("68.5", 500, 1020));

        fields.add(fieldJson("골격근량", 100, 1100));
        fields.add(fieldJson("34.2", 500, 1120));

        fields.add(fieldJson("체지방률", 100, 1200));
        fields.add(fieldJson("19.8", 650, 1220));

        fields.add(fieldJson("기초대사량", 100, 1300));
        fields.add(fieldJson("1620", 340, 1305));

        fields.add(fieldJson("내장지방레벨", VISCERAL_LABEL_X, VISCERAL_LABEL_Y));
        fields.add(fieldJson("8", VISCERAL_LABEL_X + 20, VISCERAL_LABEL_Y + 50));

        fields.add(fieldJson("인바디점수", 100, 1500));
        fields.add(fieldJson("80", 250, 1580));

        return fields;
    }

    /** 내장지방레벨 값만 바꿔서 파싱 */
    private InbodyData parseWithVisceralValue(String value) {
        List<String> fields = baseFields();
        removeText(fields, "8");
        fields.add(fieldJson(value, VISCERAL_LABEL_X + 20, VISCERAL_LABEL_Y + 50));

        return parseWith(fields);
    }

    private InbodyData parseWith(List<String> fieldJsons) {
        ClovaOcrResponse response = toResponse(fieldJsons);
        when(ocrEngine.execute(any())).thenReturn(response);

        return parser.parse(dummyFile());
    }

    private void assertParseFails(List<String> fieldJsons) {
        assertThatThrownBy(() -> parseWith(fieldJsons))
                .isInstanceOf(BusinessException.class);
    }

    /** 지정한 텍스트를 가진 필드를 제거 */
    private void removeText(List<String> fieldJsons, String text) {
        fieldJsons.removeIf(json -> json.contains("\"inferText\":\"" + text + "\""));
    }

    /** 지정한 텍스트를 다른 텍스트로 교체 (좌표는 유지) */
    private void replaceText(List<String> fieldJsons, String from, String to) {
        for (int i = 0; i < fieldJsons.size(); i++) {
            String json = fieldJsons.get(i);

            if (json.contains("\"inferText\":\"" + from + "\"")) {
                fieldJsons.set(i, json.replace(
                        "\"inferText\":\"" + from + "\"",
                        "\"inferText\":\"" + to + "\""
                ));
                return;
            }
        }
    }

    /**
     * 중심이 (cx, cy)인 사각형 영역 하나를 CLOVA OCR 필드 JSON으로 만든다.
     * 네 꼭짓점의 평균이 중심 좌표가 되도록 배치한다.
     */
    private String fieldJson(String text, double cx, double cy) {
        double halfWidth = 30;
        double halfHeight = 10;

        return """
                {"inferText":"%s","inferConfidence":0.99,"boundingPoly":{"vertices":[\
                {"x":%s,"y":%s},{"x":%s,"y":%s},{"x":%s,"y":%s},{"x":%s,"y":%s}]}}"""
                .formatted(
                        text,
                        cx - halfWidth, cy - halfHeight,
                        cx + halfWidth, cy - halfHeight,
                        cx + halfWidth, cy + halfHeight,
                        cx - halfWidth, cy + halfHeight
                );
    }

    private ClovaOcrResponse toResponse(List<String> fieldJsons) {
        String json = """
                {"images":[{"fields":[%s]}]}"""
                .formatted(String.join(",", fieldJsons));

        return new ObjectMapper().readValue(json, ClovaOcrResponse.class);
    }

    private MockMultipartFile dummyFile() {
        return new MockMultipartFile(
                "file",
                "inbody.jpg",
                "image/jpeg",
                new byte[]{1, 2, 3}
        );
    }
}
