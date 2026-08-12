package com.example.MVP_MealFit.recommendation.dto;

import com.example.MVP_MealFit.restaurant.dto.MenuSearchResponse;
import lombok.Builder;
import lombok.Getter;

import java.util.List;

@Getter
@Builder
public class RecommendedMenuResponse {

    private MenuSearchResponse menu;

    // 목표치가 없거나 이 메뉴에 영양정보가 없으면 null
    private Double matchRate;

    // "하루 목표(109g)의 26% 충족" 자리. 목표치 없으면 null
    private Integer proteinTargetPercent;

    // 질환 경고. 없으면 빈 목록 — 결과에서 메뉴를 빼지 않고 경고만 붙인다
    private List<String> warnings;
}
