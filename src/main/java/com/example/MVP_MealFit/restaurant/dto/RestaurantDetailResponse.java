package com.example.MVP_MealFit.restaurant.dto;

import lombok.Builder;
import lombok.Getter;

import java.util.List;

@Getter
@Builder
public class RestaurantDetailResponse {

    private RestaurantResponse restaurant;
    private List<MenuSearchResponse> menus;
}
