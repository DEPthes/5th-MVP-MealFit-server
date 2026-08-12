package com.example.MVP_MealFit.restaurant.repository;

import com.example.MVP_MealFit.restaurant.domain.Cuisine;
import com.example.MVP_MealFit.restaurant.domain.FoodType;
import com.example.MVP_MealFit.restaurant.domain.Menu;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;

import java.util.List;

public interface MenuRepository extends JpaRepository<Menu, Long>, MenuRepositoryCustom {

    // 음식 종류, 식당 종류, 키워드로 메뉴를 검색
    @Query("""
            SELECT DISTINCT m
            FROM Menu m
            JOIN FETCH m.restaurant r
            LEFT JOIN m.foodTypes ft
            WHERE (:foodType IS NULL
                    OR ft = :foodType)
            AND (:cuisine IS NULL
                    OR r.cuisine = :cuisine)
            AND (:keyword IS NULL
                    OR m.name LIKE CONCAT('%', :keyword, '%'))
            """)
    Page<Menu> searchMenus(Cuisine cuisine, FoodType foodType, String keyword, Pageable p);

    // 추천 후보 메뉴 조회 (구현은 MenuRepositoryImpl에서 수행)
    List<Menu> findAllForRecommendation(Cuisine cuisine, FoodType foodType, int limit);

    // 식당 메뉴 조회
    List<Menu> findByRestaurantId(Long restaurantId);
}
