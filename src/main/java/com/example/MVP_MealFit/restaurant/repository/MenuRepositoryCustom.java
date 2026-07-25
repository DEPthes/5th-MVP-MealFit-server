package com.example.MVP_MealFit.restaurant.repository;

import com.example.MVP_MealFit.restaurant.domain.Cuisine;
import com.example.MVP_MealFit.restaurant.domain.FoodType;
import com.example.MVP_MealFit.restaurant.domain.Menu;

import java.util.List;

// 메뉴 Custom Repository

/**
 * MenuRepository의 기본 JpaRepository 기능으로는
 * 추천 후보 조회 시 limit(setMaxResults)을 적용할 수 없어
 * Custom Repository를 추가함
 *
 * 설계서의 Repository 메서드 시그니처
 * findAllForRecommendations(Cuisine, FoodType, int limit)를
 * 그대로 유지하기 위한 인터페이스
 */
public interface MenuRepositoryCustom {

    // 추천 후보 메뉴 조회
    List<Menu> findAllForRecommendation(
            Cuisine cuisine,
            FoodType foodType,
            int limit
    );
}
