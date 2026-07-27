package com.example.MVP_MealFit.analysis.controller;

import com.example.MVP_MealFit.analysis.dto.TargetResponse;
import com.example.MVP_MealFit.analysis.service.TargetService;
import com.example.MVP_MealFit.global.auth.LoginMember;
import com.example.MVP_MealFit.global.response.ApiResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

@RestController
@RequiredArgsConstructor
@RequestMapping("/api/targets")
public class TargetController {

    private final TargetService targetService;

    @PostMapping
    public ApiResponse<TargetResponse> calculate(@LoginMember Long memberId) {
        return ApiResponse.ok(targetService.calculateTarget(memberId));
    }

    @GetMapping("/me")
    public ApiResponse<TargetResponse> find(@LoginMember Long memberId) {
        return ApiResponse.ok(targetService.findTarget(memberId));
    }
}