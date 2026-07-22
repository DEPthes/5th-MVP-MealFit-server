package com.example.MVP_MealFit.inbody.parser;

import com.example.MVP_MealFit.inbody.ocr.ClovaOcrEngine;
import com.example.MVP_MealFit.inbody.ocr.ClovaOcrResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;
import org.springframework.web.multipart.MultipartFile;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.List;
import java.util.Objects;
import java.util.Optional;
import java.util.regex.Pattern;

@Component
@RequiredArgsConstructor
public class InbodyParser {

    // 정수 또는 소수 형태의 숫자를 찾기 위한 정규표현식
    private static final Pattern NUMBER_PATTERN = Pattern.compile("\\d+(\\.\\d+)?");

    // 인바디 측정일(yyyy.MM.dd, yyyy-MM-dd, yyyy/MM/dd)을 찾기 위한 정규표현식
    private static final Pattern DATE_PATTERN = Pattern.compile("\\d{4}[./-]\\d{1,2}[./-]\\d{1,2}");

    private static final String WEIGHT = "체중";
    private static final String MUSCLE_MASS = "골격근량";
    private static final String BODY_FAT = "체지방률";
    private static final String BMR = "기초대사량";

    private final ClovaOcrEngine ocrEngine;

    // 인바디 결과지를 OCR로 분석하여 필요한 데이터를 추출
    public InbodyData parse(MultipartFile file) {

        // OCR 수행
        ClovaOcrResponse response = ocrEngine.execute(file);

        // OCR 응답에서 인식된 문자열 목록 추출
        List<String> texts = extractTexts(response);

        // 필요한 데이터 추출
        BigDecimal weight = extractWeight(texts);
        BigDecimal muscleMass = extractMuscleMass(texts);
        BigDecimal bodyFatPercentage = extractBodyFatPercentage(texts);
        Integer bmr = extractBmr(texts);
        Optional<LocalDate> measuredAt = extractDate(texts);

        // DTO 변환
        return new InbodyData(
                weight,
                muscleMass,
                bodyFatPercentage,
                bmr,
                measuredAt
        );
    }

    // OCR 응답에서 인식된 텍스트만 추출하여 문자열 목록으로 변환
    private List<String> extractTexts(ClovaOcrResponse response) {
        if (response == null || response.getImages() == null || response.getImages().isEmpty()) {
            throw new BusinessException(ErrorCode.OCR_PARSE_FAILED);
        }

        return response.getImages().stream()
                // fields가 없는 이미지는 제외
                .filter(image -> image.getFields() != null)
                .filter(image -> !image.getFields().isEmpty())

                // 모든 필드를 하나의 Stream으로 변환
                .flatMap(image -> image.getFields().stream())

                // null 제거
                .filter(Objects::nonNull)

                // OCR이 인식한 문자열만 추출
                .map(ClovaOcrResponse.Field::getInferText)
                
                // 빈 문자열 제거
                .filter(text -> text != null && !text.isBlank())

                // 공백 제거 후 반환
                .map(this::normalize)
                .toList();
    }

    // 체중 추출
    private BigDecimal extractWeight(List<String> texts) {
        return extractNumber(texts, WEIGHT);
    }

    // 골격근량 추출
    private BigDecimal extractMuscleMass(List<String> texts) {
        return extractNumber(texts, MUSCLE_MASS);
    }

    // 체지방률 추출
    private BigDecimal extractBodyFatPercentage(List<String> texts) {
        return extractNumber(texts, BODY_FAT);
    }

    // 기초대사량 추출
    private Integer extractBmr(List<String> texts) {
        return extractNumber(texts, BMR).intValue();
    }

    // 측정일 추출, 실패하면 Optional.empty()를 반환하며 호출 측에서 업로드일로 대체
    private Optional<LocalDate> extractDate(List<String> texts) {
        for (String text : texts) {
            var matcher = DATE_PATTERN.matcher(text);

            if (matcher.find()) {
                try {

                    // LocalDate.parse() 형식에 맞게 날짜 구분자를 '-'로 통일
                    String date = matcher.group()
                            .replace('.', '-')
                            .replace('/', '-');

                    return Optional.of(LocalDate.parse(date));
                } catch (Exception e) {
                    return Optional.empty();
                }
            }
        }

        // 날짜를 찾지 못한 경우
        return Optional.empty();
    }

    // 키워드 이후 숫자를 추출
    private BigDecimal extractNumber(List<String> texts, String keyword) {
        for (int i = 0; i < texts.size(); i++) {

            // 현재 문자열이 원하는 키워드가 아니면 다음 문자열 검사
            if (!texts.get(i).equals(keyword)) {
                continue;
            }

            // 키워드 이후 최대 5개의 OCR 결과만 탐색
            int limit = Math.min(i + 5, texts.size());

            for (int j = i + 1; j < limit; j++) {
                var matcher = NUMBER_PATTERN.matcher(texts.get(j));

                // 숫자를 찾은 경우 반환
                if (matcher.find()) {
                    return new BigDecimal(matcher.group());
                }
            }
        }

        throw new BusinessException(ErrorCode.INBODY_PARSE_FAILED);
    }

    // OCR이 인식한 문자열의 모든 공백을 제거하여 비교하기 쉬운 형태로 정규화
    private String normalize(String text) {
        return text.replaceAll("\\s+", "");
    }
}