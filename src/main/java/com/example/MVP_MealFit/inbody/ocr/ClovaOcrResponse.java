package com.example.MVP_MealFit.inbody.ocr;

import lombok.Getter;

import java.util.List;

@Getter
public class ClovaOcrResponse {

    // OCR API가 변환하는 이미지별 인식 결과 목록
    private List<Image> images;

    @Getter
    public static class Image {

        // 해당 이미지에서 인식된 모든 텍스트 영역(Field) 목록
        private List<Field> fields;
    }

    @Getter
    public static class Field {
        // OCR이 인식한 실제 텍스트 (체중, 골격근량, 체지방률, 기초대사량)
        private String inferText;

        // OCR 신뢰도 (현재는 사용하지 않지만 추후 확장 가능)
        private Double inferConfidence;
    }

}
