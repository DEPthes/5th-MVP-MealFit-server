package com.example.MVP_MealFit.analysis.controller;

import com.example.MVP_MealFit.analysis.dto.ReportResponse;
import com.example.MVP_MealFit.analysis.service.ReportService;
import com.example.MVP_MealFit.global.auth.LoginMember;
import com.example.MVP_MealFit.global.response.ApiResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequiredArgsConstructor
@RequestMapping("/api/reports")
public class ReportController {

    private final ReportService reportService;

    // AI 영양 리포트 조회
    @GetMapping("/me")
    public ApiResponse<ReportResponse> getReport(@LoginMember Long memberId) {
        return ApiResponse.ok(reportService.getReport(memberId));
    }
}