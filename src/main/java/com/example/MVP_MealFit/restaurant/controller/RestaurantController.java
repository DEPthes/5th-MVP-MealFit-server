package com.example.MVP_MealFit.restaurant.controller;

import com.example.MVP_MealFit.global.response.ApiResponse;
import com.example.MVP_MealFit.restaurant.domain.Cuisine;
import com.example.MVP_MealFit.restaurant.dto.MenuSearchCondition;
import com.example.MVP_MealFit.restaurant.dto.MenuSearchResponse;
import com.example.MVP_MealFit.restaurant.dto.RestaurantDetailResponse;
import com.example.MVP_MealFit.restaurant.dto.RestaurantResponse;
import com.example.MVP_MealFit.restaurant.service.RestaurantService;
import jakarta.servlet.http.HttpServletRequest;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.web.bind.annotation.*;

@RestController
@RequiredArgsConstructor
@RequestMapping("/api/restaurants")
public class RestaurantController {

    private final RestaurantService restaurantService;

    // 메뉴 검색
    @GetMapping("/menus")
    public ApiResponse<Page<MenuSearchResponse>> searchMenus(
            @ModelAttribute MenuSearchCondition cond,
            Pageable p) {

        return ApiResponse.ok(
                restaurantService.searchMenus(cond, p)
        );
    }

    // 식당 목록 조회
    @GetMapping
    public ApiResponse<Page<RestaurantResponse>> searchRestaurants(
            @RequestParam(required = false) String keyword,
            @RequestParam(required = false) Cuisine cuisine,
            Pageable p) {

        return ApiResponse.ok(
                restaurantService.searchRestaurants(keyword, cuisine, p)
        );
    }

    // 식당 상세 조회
    @GetMapping("/{id}")
    public ApiResponse<RestaurantDetailResponse> detail(@PathVariable("id") Long id) {
        return ApiResponse.ok(
                restaurantService.getRestaurantDetail(id)
        );
    }
}
