package com.example.MVP_MealFit.restaurant.dto;

import com.example.MVP_MealFit.restaurant.domain.Cuisine;
import com.example.MVP_MealFit.restaurant.domain.Restaurant;
import lombok.Builder;
import lombok.Getter;

@Getter
@Builder
public class RestaurantResponse {

    private Long restaurantId;
    private String name;
    private String address;
    private Cuisine cuisine;
    private Integer distanceToMainGate;
    private Integer distanceToBackGate;

    public static RestaurantResponse from(Restaurant restaurant) {

        return RestaurantResponse.builder()
                .restaurantId(restaurant.getId())
                .name(restaurant.getName())
                .address(restaurant.getAddress())
                .cuisine(restaurant.getCuisine())
                .distanceToMainGate(restaurant.getDistanceToMainGate())
                .distanceToBackGate(restaurant.getDistanceToBackGate())
                .build();
    }
}
