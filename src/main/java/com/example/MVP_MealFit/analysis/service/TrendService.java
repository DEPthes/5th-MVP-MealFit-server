package com.example.MVP_MealFit.analysis.service;

import com.example.MVP_MealFit.analysis.dto.AnalysisHistoryResponse;
import com.example.MVP_MealFit.analysis.dto.ScoreTrendResponse;
import com.example.MVP_MealFit.inbody.service.InbodyService;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.Collections;
import java.util.List;

@Service
@RequiredArgsConstructor
public class TrendService {

    private static final int DEFAULT_LIMIT = 4;   // 기본 노출
    private static final int MAX_LIMIT = 12;       // 더보기 최대

    private final InbodyService inbodyService;

    /**
     * 인바디 점수 추이 조회 (FR-007)
     * @param expanded false면 최근 4개, true면 최근 12개
     * 그래프는 오래된 → 최신 순(측정일 오름차순)으로 반환
     */
    @Transactional(readOnly = true)
    public List<ScoreTrendResponse> getScoreTrend(Long memberId, boolean expanded) {
        int limit = expanded ? MAX_LIMIT : DEFAULT_LIMIT;

        // findHistory는 측정일 내림차순(최신 먼저). 최근 N개를 자른 뒤 그래프용으로 뒤집는다.
        List<ScoreTrendResponse> recent = inbodyService.findAnalysisHistory(memberId).stream()
                .limit(limit)
                .map(ScoreTrendResponse::from)
                .collect(java.util.stream.Collectors.toList());

        Collections.reverse(recent);  // 오래된 → 최신 (그래프 X축 방향)
        return recent;
    }

    /**
     * 분석 히스토리 조회 (측정일 · 업로드일 · 점수 · 그 시점 목표 단백질)
     * 최신순(측정일 내림차순)으로 반환
     */
    @Transactional(readOnly = true)
    public List<AnalysisHistoryResponse> getAnalysisHistory(Long memberId, boolean expanded) {
        int limit = expanded ? MAX_LIMIT : DEFAULT_LIMIT;

        return inbodyService.findAnalysisHistory(memberId).stream()
                .limit(limit)
                .map(AnalysisHistoryResponse::from)
                .collect(java.util.stream.Collectors.toList());
    }
}