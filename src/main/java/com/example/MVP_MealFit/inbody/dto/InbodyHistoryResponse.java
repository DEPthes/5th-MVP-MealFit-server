package com.example.MVP_MealFit.inbody.dto;

import com.example.MVP_MealFit.inbody.domain.Inbody;
import lombok.AccessLevel;
import lombok.AllArgsConstructor;
import lombok.Getter;

import java.math.BigDecimal;
import java.time.LocalDate;

@Getter
@AllArgsConstructor(access = AccessLevel.PRIVATE)
public class InbodyHistoryResponse {

    // 인바디 ID
    private final Long inbodyId;

    // 원본 파일명
    private final String originalFilename;

    // 파일 크기 (Byte)
    private final Long fileSize;

    // 체중
    private final BigDecimal weight;

    // 골격근량
    private final BigDecimal skeletalMuscleMass;

    // 체지방률
    private final BigDecimal bodyFatPercentage;

    // 기초대사량
    private final Integer bmr;

    // 측정일
    private final LocalDate measuredAt;

    public static InbodyHistoryResponse from(Inbody inbody) {
        return new InbodyHistoryResponse(
                inbody.getId(),
                inbody.getOriginalFilename(),
                inbody.getFileSize(),
                inbody.getWeight(),
                inbody.getSkeletalMuscleMass(),
                inbody.getBodyFatPercentage(),
                inbody.getBmr(),
                inbody.getMeasuredAt()
        );
    }
}
