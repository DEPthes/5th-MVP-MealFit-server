package com.example.MVP_MealFit.restaurant.repository;

import com.example.MVP_MealFit.restaurant.domain.Cuisine;
import com.example.MVP_MealFit.restaurant.domain.FoodType;
import com.example.MVP_MealFit.restaurant.domain.Menu;
import jakarta.persistence.EntityManager;
import jakarta.persistence.PersistenceContext;
import jakarta.persistence.TypedQuery;
import org.springframework.stereotype.Repository;

import java.util.List;

// 메뉴 Custom Repository 구현체

/**
 * JPQL은 LIMIT 절을 지원하지 않으므로
 * EntityManager와 setMaxResults(limit)를 사용하여
 * 설계서의 findAllForRecommendation()을 구현
 *
 * 즉, 설계서는 변경하지 않고
 * Spring Data JPA의 한계를 보완하기 위한 구현 클래스로 사용하기 위해 만듦
 */
@Repository
public class MenuRepositoryImpl implements MenuRepositoryCustom{

    @PersistenceContext
    private EntityManager entityManager;

    @Override
    public List<Menu> findAllForRecommendation(
            Cuisine cuisine,
            FoodType foodType,
            int limit
    ) {

        String jpql = """
                SELECT DISTINCT m
                FROM Menu m
                JOIN FETCH m.restaurant r
                LEFT JOIN m.foodTypes ft
                WHERE m.nutrition.calories IS NOT NULL
                    AND (:cuisine IS NULL
                          OR r.cuisine = :cuisine)
                    AND (:foodType IS NULL
                          OR ft = :foodType)
                """;

        TypedQuery<Menu> query = entityManager.createQuery(jpql, Menu.class)
                .setParameter("cuisine", cuisine)
                .setParameter("foodType", foodType)
                .setMaxResults(limit);

        return query.getResultList();
    }
}
