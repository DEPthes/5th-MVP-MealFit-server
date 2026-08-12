package com.example.MVP_MealFit.analysis.dto;

import com.example.MVP_MealFit.inbody.dto.InbodyHistoryResponse;

import java.math.BigDecimal;
import java.time.LocalDate;

/**
 * 분석 히스토리 항목 (측정일 · 업로드일 · 점수 · 그 시점 목표 단백질)
 */
public record AnalysisHistoryResponse(
        LocalDate measuredAt,
        LocalDate uploadedAt,
        Integer inbodyScore,
        BigDecimal proteinTarget
) {
    public static AnalysisHistoryResponse from(InbodyHistoryResponse h) {
        return new AnalysisHistoryResponse(
                h.getMeasuredAt(),
                h.getUploadedAt(),
                h.getInbodyScore(),
                h.getProteinTarget()
        );
    }
}