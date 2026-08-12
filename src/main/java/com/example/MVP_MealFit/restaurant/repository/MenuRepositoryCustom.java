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

    /**
     * 검색·추천 조건에 맞는 메뉴를 전부 조회한다 (필터·정렬·페이징은 서비스가 메모리에서 한다).
     * <p>
     * selectedFoodType(칩)은 AND, derivedFoodType(검색어→동의어 유추)는 keyword 조건과 OR로
     * 묶인다 — "고기"를 검색했을 때 MEAT 태그면서 이름에 "고기"가 있는 메뉴만 남으면 삼겹살이
     * 빠지기 때문이다.
     */
    List<Menu> findForRecommendation(
            Cuisine cuisine,
            FoodType selectedFoodType,
            FoodType derivedFoodType,
            List<String> keywordTokens
    );
}
