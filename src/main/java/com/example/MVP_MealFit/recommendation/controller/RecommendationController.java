package com.example.MVP_MealFit.recommendation.controller;

import com.example.MVP_MealFit.global.auth.LoginMember;
import com.example.MVP_MealFit.global.response.ApiResponse;
import com.example.MVP_MealFit.recommendation.dto.RecommendationCondition;
import com.example.MVP_MealFit.recommendation.dto.RecommendationResponse;
import com.example.MVP_MealFit.recommendation.service.RecommendationService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.responses.ApiResponses;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import org.springdoc.core.annotations.ParameterObject;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.ModelAttribute;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequiredArgsConstructor
@RequestMapping("/api/recommendations")
@Tag(name = "Recommendations", description = "식당 및 메뉴 추천 API")
public class RecommendationController {

    private final RecommendationService recommendationService;

    // 식당 단위 검색 + 추천 (홈·검색 겸용). 검색어 없이 호출하면 홈, 있으면 검색이다.
    @GetMapping
    @Operation(
            summary = "식당 및 메뉴 추천 조회",
            description = "검색 조건과 회원의 영양 목표 및 기저질환을 기반으로 식당과 메뉴를 추천합니다. "
                    + "검색어 없이 호출하면 홈 추천으로 동작하며, 검색어를 입력하면 검색 결과를 반환합니다."
    )
    @ApiResponses({
            @io.swagger.v3.oas.annotations.responses.ApiResponse(
                    responseCode = "200",
                    description = "식당 및 메뉴 추천 조회 성공"
            ),
            @io.swagger.v3.oas.annotations.responses.ApiResponse(
                    responseCode = "401",
                    description = "인증이 필요합니다."
            ),
            @io.swagger.v3.oas.annotations.responses.ApiResponse(
                    responseCode = "404",
                    description = "존재하지 않는 회원입니다."
            )
    })
    public ApiResponse<Page<RecommendationResponse>> search(
            @Parameter(hidden = true)
            @LoginMember Long memberId,
            @ParameterObject RecommendationCondition cond,
            @ParameterObject Pageable p) {
        return ApiResponse.ok(recommendationService.search(memberId, cond, p));
    }
}
