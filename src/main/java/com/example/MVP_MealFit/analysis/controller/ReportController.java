package com.example.MVP_MealFit.analysis.controller;

import com.example.MVP_MealFit.analysis.dto.ReportResponse;
import com.example.MVP_MealFit.analysis.service.ReportService;
import com.example.MVP_MealFit.global.auth.LoginMember;
import com.example.MVP_MealFit.global.response.ApiResponse;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.responses.ApiResponses;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequiredArgsConstructor
@RequestMapping("/api/reports")
@Tag(name = "Report", description = "AI 영양 리포트 API")
public class ReportController {

    private final ReportService reportService;

    // AI 영양 리포트 조회
    @Operation(
            summary = "내 영양 리포트 조회",
            description = "최신 인바디 점수, 목표 영양치, 부족 영양소 카드 및 AI 요약을 조회합니다."
    )
    @ApiResponses({
            @io.swagger.v3.oas.annotations.responses.ApiResponse(
                    responseCode = "200",
                    description = "영양 리포트 조회 성공"
            ),
            @io.swagger.v3.oas.annotations.responses.ApiResponse(
                    responseCode = "404",
                    description = "인바디 정보 또는 목표 영양치가 준비되지 않음"
            )
    })
    @GetMapping("/me")
    public ApiResponse<ReportResponse> getReport(@Parameter(hidden = true) @LoginMember Long memberId) {
        return ApiResponse.ok(reportService.getReport(memberId));
    }
}