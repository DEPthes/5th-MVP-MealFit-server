package com.example.MVP_MealFit.inbody.parser;

import com.example.MVP_MealFit.global.exception.BusinessException;
import com.example.MVP_MealFit.global.exception.ErrorCode;
import com.example.MVP_MealFit.inbody.ocr.ClovaOcrEngine;
import com.example.MVP_MealFit.inbody.ocr.ClovaOcrResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;
import org.springframework.web.multipart.MultipartFile;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.Comparator;
import java.util.List;
import java.util.Objects;
import java.util.Optional;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

@Component
@RequiredArgsConstructor
public class InbodyParser {

    // 정수 또는 소수 형태의 숫자를 찾기 위한 정규표현식
    private static final Pattern NUMBER_PATTERN = Pattern.compile("^\\d+(\\.\\d+)?$");

    // 인바디 측정일(yyyy.MM.dd, yyyy-MM-dd, yyyy/MM/dd)을 찾기 위한 정규표현식
    private static final Pattern DATE_PATTERN = Pattern.compile("\\d{4}[./-]\\d{2}[./-]\\d{2}");

    // 숫자가 포함된 문자열의 앞부분 숫자를 추출하기 위한 정규표현식
    private static final Pattern LEADING_NUMBER_PATTERN = Pattern.compile("^\\d+(\\.\\d+)?");

    private final ClovaOcrEngine ocrEngine;

    // 인바디 결과지를 OCR로 분석하여 필요한 데이터를 추출
    public InbodyData parse(MultipartFile file) {

        // OCR 수행
        ClovaOcrResponse response = ocrEngine.execute(file);

        // OCR 응답에서 인식된 문자열 목록 추출
        List<ClovaOcrResponse.Field> fields = extractFields(response);

        // 필요한 데이터 추출
        BigDecimal weight = extractWeight(fields);
        BigDecimal muscleMass = extractMuscleMass(fields);
        BigDecimal bodyFatPercentage = extractBodyFatPercentage(fields);
        Integer bmr = extractBmr(fields);
        Integer inbodyScore = extractInbodyScore(fields);
        Optional<LocalDate> measuredAt = extractDate(fields);

        // DTO 변환
        return new InbodyData(
                weight,
                muscleMass,
                bodyFatPercentage,
                bmr,
                inbodyScore,
                measuredAt
        );
    }

    // OCR 응답의 모든 Field를 하나의 리스트로 변환
    private List<ClovaOcrResponse.Field> extractFields(ClovaOcrResponse response) {
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

                .toList();
    }

    // 체중 추출
    private BigDecimal extractWeight(List<ClovaOcrResponse.Field> fields) {
        ClovaOcrResponse.Field weightLabel =
                findWeightLabel(fields);

        double labelX = weightLabel.centerX();
        double labelY = weightLabel.centerY();

        return fields.stream()
                .filter(field -> field.getInferText() != null)
                .map(field -> {
                    String text = normalize(field.getInferText());

                    Matcher matcher = LEADING_NUMBER_PATTERN.matcher(text);

                    if (!matcher.find()) {
                        return null;
                    }

                    return new NumberCandidate(
                            field,
                            new BigDecimal(matcher.group())
                    );
                })
                .filter(Objects::nonNull)

                // Weight 바로 아래 숫자만
                .filter(candidate -> {
                    double dx = candidate.field().centerX() - labelX;
                    double dy = candidate.field().centerY() - labelY;

                    return dx > 250
                            && dx < 600
                            && dy > 0
                            && dy < 50;
                })

                .min(Comparator.comparingDouble(candidate ->
                        Math.abs(candidate.field().centerX() - labelX)
                ))

                .map(NumberCandidate::value)
                .orElseThrow(() ->
                        new BusinessException(ErrorCode.OCR_PARSE_FAILED));
    }

    // 골격근량 추출
    private BigDecimal extractMuscleMass(List<ClovaOcrResponse.Field> fields) {
        return findNearestNumber(
                fields,
                findMuscleLabel(fields),
                250, 600,
                0, 50,
                10, 60
        );
    }

    // 체지방률 추출
    private BigDecimal extractBodyFatPercentage(List<ClovaOcrResponse.Field> fields) {
        return findNearestNumber(
                fields,
                findBodyFatLabel(fields),
                500, 650,
                0, 50,
                5, 60
        );
    }

    // 기초대사량 추출
    private Integer extractBmr(List<ClovaOcrResponse.Field> fields) {
        return findNearestNumber(
                fields,
                findBmrLabel(fields),
                180, 300,
                -20, 20,
                500, 3000
        ).intValue();
    }

    private Integer extractInbodyScore(List<ClovaOcrResponse.Field> fields) {
        return findNearestNumber(
                fields,
                findInbodyScoreLabel(fields),
                80, 220,    // X 범위 (조정 가능)
                40, 120,    // Y 범위 (조정 가능)
                0, 100      // 점수 범위
        ).intValue();
    }

    // 측정일 추출, 실패하면 Optional.empty()를 반환하며 호출 측에서 업로드일로 대체
    private Optional<LocalDate> extractDate(List<ClovaOcrResponse.Field> fields) {
        return fields.stream()

                .map(ClovaOcrResponse.Field::getInferText)

                .filter(Objects::nonNull)
                .map(text -> {
                    Matcher matcher = DATE_PATTERN.matcher(text);
                    return matcher.find() ? matcher.group() : null;
                })
                .filter(Objects::nonNull)
                .map(text -> text.replace('.', '-')
                        .replace('/', '-'))
                .map(LocalDate::parse)
                .findFirst();
    }

    // 공통 라벨 검색
    private ClovaOcrResponse.Field findLabel(
            List<ClovaOcrResponse.Field> fields,
            String... labels
    ) {

        return fields.stream()
                .filter(field -> field.getInferText() != null)
                .filter(field -> {

                    String text = normalize(field.getInferText());

                    for (String label : labels) {
                        if (text.equals(label)) {
                            return true;
                        }
                    }

                    return false;
                })
                .findFirst()
                .orElseThrow(() ->
                        new BusinessException(ErrorCode.OCR_PARSE_FAILED));
    }

    // 체중 전용 라벨
    private ClovaOcrResponse.Field findWeightLabel(List<ClovaOcrResponse.Field> fields) {

        return fields.stream()
                .filter(field -> "체중".equals(normalize(field.getInferText())))
                .filter(field -> field.centerY() > 800 && field.centerY() < 1200)
                .findFirst()
                .orElseThrow(() ->
                        new BusinessException(ErrorCode.OCR_PARSE_FAILED));
    }

    // 골격근량 라벨 검색
    private ClovaOcrResponse.Field findMuscleLabel(
            List<ClovaOcrResponse.Field> fields) {

        return findLabel(
                fields,
                "골격근량"
        );
    }


    // 체지방률 라벨 검색
    private ClovaOcrResponse.Field findBodyFatLabel(
            List<ClovaOcrResponse.Field> fields) {

        return findLabel(
                fields,
                "체지방률",
                "체지방를"
        );
    }

    // 기초대사량 라벨 검색
    private ClovaOcrResponse.Field findBmrLabel(
            List<ClovaOcrResponse.Field> fields) {

        return findLabel(
                fields,
                "기초대사량"
        );
    }

    // 인바디 점수 라벨 검색
    private ClovaOcrResponse.Field findInbodyScoreLabel(
            List<ClovaOcrResponse.Field> fields) {

        return findLabel(
                fields,
                "인바디점수",
                "인바디 점수"
        );
    }

    // 라벨 주변에서 조건에 맞는 가장 가까운 숫자 검색
    private BigDecimal findNearestNumber(
            List<ClovaOcrResponse.Field> fields,
            ClovaOcrResponse.Field label,
            double minDx,
            double maxDx,
            double minDy,
            double maxDy,
            double minValue,
            double maxValue
    ) {

        double labelX = label.centerX();
        double labelY = label.centerY();

        return fields.stream()

                .filter(field -> field.getInferText() != null)

                .map(field -> {

                    String text = normalize(field.getInferText());

                    Matcher matcher = LEADING_NUMBER_PATTERN.matcher(text);

                    if (!matcher.find()) {
                        return null;
                    }

                    return new NumberCandidate(
                            field,
                            new BigDecimal(matcher.group())
                    );
                })

                .filter(Objects::nonNull)

                .filter(candidate -> {

                    double dx = candidate.field().centerX() - labelX;
                    double dy = candidate.field().centerY() - labelY;

                    return dx >= minDx
                            && dx <= maxDx
                            && dy >= minDy
                            && dy <= maxDy;
                })

                .filter(candidate -> {

                    double value = candidate.value().doubleValue();

                    return value >= minValue
                            && value <= maxValue;
                })

                .min(
                        Comparator
                                .<NumberCandidate>comparingDouble(candidate ->
                                        Math.abs(candidate.field().centerY() - labelY)
                                )
                                .thenComparingDouble(candidate ->
                                        Math.abs(candidate.field().centerX() - labelX)
                                )
                )

                .map(NumberCandidate::value)

                .orElseThrow(() ->
                        new BusinessException(ErrorCode.OCR_PARSE_FAILED));
    }

    // OCR이 인식한 문자열의 모든 공백을 제거하여 비교하기 쉬운 형태로 정규화
    private String normalize(String text) {

        if (text == null) {
            return "";
        }

        return text.replaceAll("\\s+", "");
    }

    // OCR 숫자 후보
    private record NumberCandidate(ClovaOcrResponse.Field field, BigDecimal value) {
    }
}