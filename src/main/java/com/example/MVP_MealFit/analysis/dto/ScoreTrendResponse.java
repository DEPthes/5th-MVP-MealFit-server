package com.example.MVP_MealFit.analysis.dto;

import com.example.MVP_MealFit.inbody.dto.InbodyHistoryResponse;

import java.time.LocalDate;

public record ScoreTrendResponse(
        LocalDate measuredAt,
        Integer inbodyScore
) {
    public static ScoreTrendResponse from(InbodyHistoryResponse history) {
        return new ScoreTrendResponse(
                history.getMeasuredAt(),
                history.getInbodyScore()
        );
    }
}