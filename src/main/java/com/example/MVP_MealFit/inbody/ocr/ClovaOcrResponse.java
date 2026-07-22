package com.example.MVP_MealFit.inbody.ocr;

import lombok.Getter;
import lombok.NoArgsConstructor;

import java.util.List;

@Getter
@NoArgsConstructor
public class ClovaOcrResponse {
    // OCR API가 변환하는 이미지별 인식 결과 목록
    private List<Image> images;

    @Getter
    @NoArgsConstructor
    public static class Image {

        // 해당 이미지에서 인식된 모든 텍스트 영역(Field) 목록
        private List<Field> fields;
    }

    @Getter
    @NoArgsConstructor
    public static class Field {
        // OCR이 인식한 실제 텍스트 (체중, 골격근량, 체지방률, 기초대사량)
        private String inferText;

        // OCR 신뢰도 (현재는 사용하지 않지만 추후 확장 가능)
        private Double inferConfidence;

        // OCR이 인식한 테스트의 위치 좌표
        private BoundingPoly boundingPoly;

        // x 좌표
        public double centerX() {

            if (boundingPoly == null || boundingPoly.getVertices() == null) {
                return 0;
            }

            return boundingPoly.getVertices()
                    .stream()
                    .mapToDouble(Vertex::getX)
                    .average()
                    .orElse(0);
        }

        // y 좌표
        public double centerY() {

            if (boundingPoly == null || boundingPoly.getVertices() == null) {
                return 0;
            }

            return boundingPoly.getVertices()
                    .stream()
                    .mapToDouble(Vertex::getY)
                    .average()
                    .orElse(0);
        }
    }
    
    // OCR 텍스트 영역의 꼭짓점 좌표
    @Getter
    @NoArgsConstructor
    public static class BoundingPoly {
        private List<Vertex> vertices;
    }

    // OCR 좌표 (x, y)
    @Getter
    @NoArgsConstructor
    public static class Vertex {
        private double x;
        private double y;
    }
}