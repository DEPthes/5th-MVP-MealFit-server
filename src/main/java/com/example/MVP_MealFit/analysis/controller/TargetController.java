package com.example.MVP_MealFit.analysis.controller;

import com.example.MVP_MealFit.analysis.dto.TargetResponse;
import com.example.MVP_MealFit.analysis.service.TargetService;
import com.example.MVP_MealFit.global.auth.LoginMember;
import com.example.MVP_MealFit.global.response.ApiResponse;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.responses.ApiResponses;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

@RestController
@RequiredArgsConstructor
@RequestMapping("/api/targets")
@Tag(name = "Target", description = "목표 영양치 API")
public class TargetController {

    private final TargetService targetService;

    @PostMapping
    @Operation(
            summary = "목표 영양치 계산",
            description = "회원의 최신 인바디 정보와 활동 수준 및 목표를 기반으로 목표 영양치를 계산하고 저장합니다."
    )
    @ApiResponses({
            @io.swagger.v3.oas.annotations.responses.ApiResponse(
                    responseCode = "200",
                    description = "목표 영양치 계산 및 저장 성공"
            ),
            @io.swagger.v3.oas.annotations.responses.ApiResponse(
                    responseCode = "404",
                    description = "회원 또는 최신 인바디 정보를 찾을 수 없음"
            )
    })
    public ApiResponse<TargetResponse> calculate(@Parameter(hidden = true) @LoginMember Long memberId) {
        return ApiResponse.ok(targetService.calculateTarget(memberId));
    }

    @GetMapping("/me")
    @Operation(
            summary = "내 목표 영양치 조회",
            description = "로그인한 회원에게 저장된 목표 영양치를 조회합니다. 최신 인바디를 기준으로 목표 영양치가 최신 상태인지 함께 확인합니다."
    )
    @ApiResponses({
            @io.swagger.v3.oas.annotations.responses.ApiResponse(
                    responseCode = "200",
                    description = "목표 영양치 조회 성공"
            ),
            @io.swagger.v3.oas.annotations.responses.ApiResponse(
                    responseCode = "404",
                    description = "목표 영양치가 아직 산출되지 않음"
            )
    })
    public ApiResponse<TargetResponse> find(@Parameter(hidden = true) @LoginMember Long memberId) {
        return ApiResponse.ok(targetService.findTarget(memberId));
    }
}