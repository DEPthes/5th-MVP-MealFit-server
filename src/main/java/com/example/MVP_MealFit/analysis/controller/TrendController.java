package com.example.MVP_MealFit.analysis.controller;

import com.example.MVP_MealFit.analysis.dto.AnalysisHistoryResponse;
import com.example.MVP_MealFit.analysis.dto.ScoreTrendResponse;
import com.example.MVP_MealFit.analysis.service.TrendService;
import com.example.MVP_MealFit.global.auth.LoginMember;
import com.example.MVP_MealFit.global.response.ApiResponse;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.responses.ApiResponses;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequiredArgsConstructor
@RequestMapping("/api/reports")
@Tag(name = "Trend", description = "인바디 분석 추이 및 히스토리 API")
public class TrendController {

    private final TrendService trendService;

    // 점수 추이 조회. expanded=true면 최대 12개, 기본 4개
    @GetMapping("/scores")
    @Operation(
            summary = "인바디 점수 추이 조회",
            description = "회원의 인바디 점수 추이를 조회합니다. 기본적으로 최근 4개를 반환하며 expanded=true인 경우 최대 12개를 반환합니다."
    )
    @ApiResponses({
            @io.swagger.v3.oas.annotations.responses.ApiResponse(
                    responseCode = "200",
                    description = "인바디 점수 추이 조회 성공"
            ),
            @io.swagger.v3.oas.annotations.responses.ApiResponse(
                    responseCode = "401",
                    description = "인증이 필요합니다."
            )
    })
    public ApiResponse<List<ScoreTrendResponse>> scoreTrend(
            @Parameter(hidden = true)
            @LoginMember Long memberId,

            @Parameter(
                    description = "확장 조회 여부. false이면 최근 4개, true이면 최대 12개를 반환합니다.",
                    example = "false"
            )
            @RequestParam(defaultValue = "false") boolean expanded
    ) {
        return ApiResponse.ok(trendService.getScoreTrend(memberId, expanded));
    }

    // 분석 히스토리 조회 (측정일·업로드일·점수·목표 단백질)
    @GetMapping("/analysis-history")
    @Operation(
            summary = "분석 히스토리 조회",
            description = "회원의 인바디 분석 히스토리를 조회합니다. 측정일, 업로드일, 인바디 점수 및 해당 시점의 목표 단백질을 반환합니다. 기본적으로 최근 4개를 반환하며 expanded=true인 경우 최대 12개를 반환합니다."
    )
    @ApiResponses({
            @io.swagger.v3.oas.annotations.responses.ApiResponse(
                    responseCode = "200",
                    description = "분석 히스토리 조회 성공"
            ),
            @io.swagger.v3.oas.annotations.responses.ApiResponse(
                    responseCode = "401",
                    description = "인증이 필요합니다."
            )
    })
    public ApiResponse<List<AnalysisHistoryResponse>> analysisHistory(
            @Parameter(hidden = true)
            @LoginMember Long memberId,

            @Parameter(
                    description = "확장 조회 여부. false이면 최근 4개, true이면 최대 12개를 반환합니다.",
                    example = "false"
            )
            @RequestParam(defaultValue = "false") boolean expanded
    ) {
        return ApiResponse.ok(trendService.getAnalysisHistory(memberId, expanded));
    }
}