package com.example.MVP_MealFit.inbody.dto;

import com.example.MVP_MealFit.inbody.domain.Inbody;
import lombok.AccessLevel;
import lombok.AllArgsConstructor;
import lombok.Getter;

import java.math.BigDecimal;
import java.time.LocalDate;

@Getter
@AllArgsConstructor(access = AccessLevel.PRIVATE)
public class InbodyResponse {

    private final Long inbodyId;
    private final BigDecimal weight;
    private final BigDecimal skeletalMuscleMass;
    private final BigDecimal bodyFatPercentage;
    private final Integer bmr;
    private final Integer inbodyScore;
    private final LocalDate measuredAt;
    private final LocalDate uploadedAt;
    private final boolean stale;
    private final String imagePath;

    public static InbodyResponse from(Inbody inbody, LocalDate today) {

        return new InbodyResponse(
                inbody.getId(),
                inbody.getWeight(),
                inbody.getSkeletalMuscleMass(),
                inbody.getBodyFatPercentage(),
                inbody.getBmr(),
                inbody.getInbodyScore(),
                inbody.getMeasuredAt(),
                inbody.getUploadedAt(),
                inbody.isStale(today),
                inbody.getImagePath()
        );
    }

}
