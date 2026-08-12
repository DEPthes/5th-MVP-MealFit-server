package com.example.MVP_MealFit.recommendation.controller;

import com.example.MVP_MealFit.global.auth.LoginMember;
import com.example.MVP_MealFit.global.response.ApiResponse;
import com.example.MVP_MealFit.recommendation.dto.RecommendationCondition;
import com.example.MVP_MealFit.recommendation.dto.RecommendationResponse;
import com.example.MVP_MealFit.recommendation.service.RecommendationService;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.ModelAttribute;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequiredArgsConstructor
@RequestMapping("/api/recommendations")
public class RecommendationController {

    private final RecommendationService recommendationService;

    // 식당 단위 검색 + 추천 (홈·검색 겸용). 검색어 없이 호출하면 홈, 있으면 검색이다.
    @GetMapping
    public ApiResponse<Page<RecommendationResponse>> search(
            @LoginMember Long memberId,
            @ModelAttribute RecommendationCondition cond,
            Pageable p) {
        return ApiResponse.ok(recommendationService.search(memberId, cond, p));
    }
}
