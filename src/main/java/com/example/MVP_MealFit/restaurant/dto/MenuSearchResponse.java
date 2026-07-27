package com.example.MVP_MealFit.restaurant.dto;

import com.example.MVP_MealFit.restaurant.domain.Cuisine;
import com.example.MVP_MealFit.restaurant.domain.FoodType;
import com.example.MVP_MealFit.restaurant.domain.Menu;
import com.example.MVP_MealFit.restaurant.domain.Restaurant;
import lombok.Builder;
import lombok.Getter;

import java.util.Set;

@Getter
@Builder
public class MenuSearchResponse {

    private Long menuId;
    private String menuName;
    private Integer price;
    private Set<FoodType> foodTypes;
    private NutritionDto nutrition;
    private Long restaurantId;
    private String restaurantName;
    private Cuisine cuisine;
    private String address;

    public static MenuSearchResponse from(Menu menu) {

        Restaurant restaurant = menu.getRestaurant();

        return MenuSearchResponse.builder()
                .menuId(menu.getId())
                .menuName(menu.getName())
                .price(menu.getPrice())
                .foodTypes(menu.getFoodTypes())
                .nutrition(NutritionDto.from(menu.getNutrition()))
                .restaurantId(restaurant.getId())
                .restaurantName(restaurant.getName())
                .cuisine(restaurant.getCuisine())
                .address(restaurant.getAddress())
                .build();

    }
}
