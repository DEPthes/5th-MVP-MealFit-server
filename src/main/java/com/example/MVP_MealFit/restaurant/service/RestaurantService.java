package com.example.MVP_MealFit.restaurant.service;

import com.example.MVP_MealFit.global.exception.BusinessException;
import com.example.MVP_MealFit.global.exception.ErrorCode;
import com.example.MVP_MealFit.restaurant.domain.Cuisine;
import com.example.MVP_MealFit.restaurant.domain.FoodType;
import com.example.MVP_MealFit.restaurant.domain.Menu;
import com.example.MVP_MealFit.restaurant.domain.Restaurant;
import com.example.MVP_MealFit.restaurant.dto.*;
import com.example.MVP_MealFit.restaurant.repository.MenuRepository;
import com.example.MVP_MealFit.restaurant.repository.RestaurantRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
@RequiredArgsConstructor
public class RestaurantService {

    private final RestaurantRepository restaurantRepository;
    private final MenuRepository menuRepository;
    private final SynonymResolver synonymResolver;

    // 메뉴 검색
    public Page<MenuSearchResponse> searchMenus(MenuSearchCondition cond, Pageable p) {
        FoodType foodType = cond.getFoodType();
        String keyword = cond.getKeyword();

        // 음식 종류가 선택되지 않은 경우 동의어 검색
        if (foodType == null) {
            var resolved = synonymResolver.resolve(keyword);

            if (resolved.isPresent()) {
                foodType = resolved.get();
                keyword = null;
            }
        }

        return menuRepository.searchMenus(
                cond.getCuisine(),
                foodType,
                keyword,
                p
        )
                .map(MenuSearchResponse::from);
    }

    // 식당 검색
    public Page<RestaurantResponse> searchRestaurants(String keyword, Cuisine cuisine, Pageable p) {
        return restaurantRepository.searchRestaurants(keyword, cuisine, p)
                .map(RestaurantResponse::from);
    }

    // 식당 상세 조회
    public RestaurantDetailResponse getRestaurantDetail(Long restaurantId) {
        Restaurant restaurant = restaurantRepository.findById(restaurantId)
                .orElseThrow(() -> new BusinessException(ErrorCode.RESTAURANT_NOT_FOUND));

        List<MenuSearchResponse> menus = menuRepository.findByRestaurantId(restaurantId)
                .stream()
                .map(MenuSearchResponse::from)
                .toList();

        return RestaurantDetailResponse.builder()
                .restaurant(RestaurantResponse.from(restaurant))
                .menus(menus)
                .build();
    }

    // 추천 후보 메뉴 조회
    public List<Menu> getCandidateMenus(Cuisine cuisine, FoodType foodType, int limit) {
        return menuRepository.findAllForRecommendation(cuisine, foodType, limit);
    }
}
