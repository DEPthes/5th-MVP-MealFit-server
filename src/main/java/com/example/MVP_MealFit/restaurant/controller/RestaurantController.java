package com.example.MVP_MealFit.restaurant.controller;

import com.example.MVP_MealFit.global.response.ApiResponse;
import com.example.MVP_MealFit.restaurant.domain.Cuisine;
import com.example.MVP_MealFit.restaurant.dto.MenuSearchCondition;
import com.example.MVP_MealFit.restaurant.dto.MenuSearchResponse;
import com.example.MVP_MealFit.restaurant.dto.RestaurantDetailResponse;
import com.example.MVP_MealFit.restaurant.dto.RestaurantResponse;
import com.example.MVP_MealFit.restaurant.service.RestaurantService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.responses.ApiResponses;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.servlet.http.HttpServletRequest;
import lombok.RequiredArgsConstructor;
import org.springdoc.core.annotations.ParameterObject;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.web.bind.annotation.*;

@RestController
@RequiredArgsConstructor
@RequestMapping("/api/restaurants")
@Tag(name = "Restaurant", description = "식당 및 메뉴 API")
public class RestaurantController {

    private final RestaurantService restaurantService;

    // 메뉴 검색
    @GetMapping("/menus")
    @Operation(
            summary = "메뉴 검색",
            description = "음식 종류, 음식 분류, 검색어 등의 조건을 이용하여 메뉴를 검색합니다."
    )
    @ApiResponses({
            @io.swagger.v3.oas.annotations.responses.ApiResponse(
                    responseCode = "200",
                    description = "메뉴 검색 성공"
            )
    })
    public ApiResponse<Page<MenuSearchResponse>> searchMenus(
            @Parameter(
                    description = "메뉴 검색 조건"
            )
            @ParameterObject MenuSearchCondition cond,

            @ParameterObject Pageable p) {

        return ApiResponse.ok(
                restaurantService.searchMenus(cond, p)
        );
    }

    // 식당 목록 조회
    @GetMapping
    @Operation(
            summary = "식당 목록 조회",
            description = "검색어와 음식 분류를 기준으로 식당 목록을 조회합니다."
    )
    @ApiResponses({
            @io.swagger.v3.oas.annotations.responses.ApiResponse(
                    responseCode = "200",
                    description = "식당 목록 조회 성공"
            )
    })
    public ApiResponse<Page<RestaurantResponse>> searchRestaurants(
            @Parameter(
                    description = "식당 검색어",
                    example = "김밥"
            )
            @RequestParam(required = false) String keyword,

            @Parameter(
                    description = "음식 분류",
                    example = "KOREAN"
            )
            @RequestParam(required = false) Cuisine cuisine,

            @ParameterObject Pageable p) {

        return ApiResponse.ok(
                restaurantService.searchRestaurants(keyword, cuisine, p)
        );
    }

    // 식당 상세 조회
    @GetMapping("/{id}")
    @Operation(
            summary = "식당 상세 조회",
            description = "식당 ID를 기준으로 식당 정보와 해당 식당의 메뉴 목록을 조회합니다."
    )
    @ApiResponses({
            @io.swagger.v3.oas.annotations.responses.ApiResponse(
                    responseCode = "200",
                    description = "식당 상세 조회 성공"
            ),
            @io.swagger.v3.oas.annotations.responses.ApiResponse(
                    responseCode = "404",
                    description = "존재하지 않는 식당입니다."
            )
    })
    public ApiResponse<RestaurantDetailResponse> detail(
            @Parameter(
                    description = "식당 ID",
                    required = true,
                    example = "1"
            )
            @PathVariable("id") Long id) {
        return ApiResponse.ok(
                restaurantService.getRestaurantDetail(id)
        );
    }
}
