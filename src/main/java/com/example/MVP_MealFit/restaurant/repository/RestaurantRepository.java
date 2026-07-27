package com.example.MVP_MealFit.restaurant.repository;

import com.example.MVP_MealFit.restaurant.domain.Cuisine;
import com.example.MVP_MealFit.restaurant.domain.Restaurant;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.List;

public interface RestaurantRepository extends JpaRepository<Restaurant, Long> {

    // 식당명 및 음식 종류로 식당을 검색
    @Query("""
            SELECT r
            FROM Restaurant r
            WHERE (:nameKeyword IS NULL
                        OR r.name LIKE CONCAT('%', :nameKeyword, '%'))
              AND (:cuisine IS NULL
                        OR r.cuisine = :cuisine)
            """)
    Page<Restaurant> searchRestaurants(
            @Param("nameKeyword") String nameKeyword,
            @Param("cuisine") Cuisine cuisine,
            Pageable p);
}
