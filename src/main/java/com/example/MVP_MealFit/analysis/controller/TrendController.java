package com.example.MVP_MealFit.analysis.controller;

import com.example.MVP_MealFit.analysis.dto.AnalysisHistoryResponse;
import com.example.MVP_MealFit.analysis.dto.ScoreTrendResponse;
import com.example.MVP_MealFit.analysis.service.TrendService;
import com.example.MVP_MealFit.global.auth.LoginMember;
import com.example.MVP_MealFit.global.response.ApiResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequiredArgsConstructor
@RequestMapping("/api/reports")
public class TrendController {

    private final TrendService trendService;

    // 점수 추이 조회. expanded=true면 최대 12개, 기본 4개
    @GetMapping("/scores")
    public ApiResponse<List<ScoreTrendResponse>> scoreTrend(
            @LoginMember Long memberId,
            @RequestParam(defaultValue = "false") boolean expanded
    ) {
        return ApiResponse.ok(trendService.getScoreTrend(memberId, expanded));
    }

    // 분석 히스토리 조회 (측정일·업로드일·점수·목표 단백질)
    @GetMapping("/analysis-history")
    public ApiResponse<List<AnalysisHistoryResponse>> analysisHistory(
            @LoginMember Long memberId,
            @RequestParam(defaultValue = "false") boolean expanded
    ) {
        return ApiResponse.ok(trendService.getAnalysisHistory(memberId, expanded));
    }
}