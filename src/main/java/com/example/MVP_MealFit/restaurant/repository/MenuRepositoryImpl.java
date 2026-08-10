package com.example.MVP_MealFit.restaurant.repository;

import com.example.MVP_MealFit.restaurant.domain.Cuisine;
import com.example.MVP_MealFit.restaurant.domain.FoodType;
import com.example.MVP_MealFit.restaurant.domain.Menu;
import jakarta.persistence.EntityManager;
import jakarta.persistence.PersistenceContext;
import jakarta.persistence.TypedQuery;
import org.springframework.stereotype.Repository;

import java.math.BigDecimal;
import java.util.ArrayList;
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

    //: 대표식품명 확장에만 적용하는 신뢰도 하한. 낮은 신뢰도로 묶으면 오매칭이 검색에
    //: 그대로 새어나간다(예: LLM 0.80 매칭 "불백정식"→"볶음밥"). 근거는 인수인계 §8-⑦ 실측.
    private static final double MIN_MATCH_CONFIDENCE = 0.85;

    //: 검색어 단어 개수 상한. 그 이상은 무시한다 — 조건이 무한정 길어지는 것을 막는다.
    private static final int MAX_KEYWORD_TOKENS = 5;

    @Override
    public List<Menu> findForRecommendation(
            Cuisine cuisine,
            FoodType selectedFoodType,
            FoodType derivedFoodType,
            List<String> keywordTokens
    ) {
        List<String> tokens = keywordTokens == null
                ? List.of()
                : keywordTokens.stream().limit(MAX_KEYWORD_TOKENS).toList();
        boolean hasKeyword = !tokens.isEmpty();

        StringBuilder jpql = new StringBuilder("""
                SELECT DISTINCT m
                FROM Menu m
                JOIN FETCH m.restaurant r
                LEFT JOIN FETCH m.officialFood o
                LEFT JOIN FETCH m.foodTypes
                WHERE r.cuisine <> :cafeDessert
                    AND (:cuisine IS NULL OR r.cuisine = :cuisine)
                    AND (:selectedFoodType IS NULL OR :selectedFoodType MEMBER OF m.foodTypes)
                """);

        if (hasKeyword || derivedFoodType != null) {
            List<String> orParts = new ArrayList<>();
            if (hasKeyword) {
                orParts.add(tokenMatch(tokens, "REPLACE(m.normalizedName, ' ', '')"));
                orParts.add(tokenMatch(tokens, "REPLACE(m.name, ' ', '')"));
                orParts.add(tokenMatch(tokens, "REPLACE(r.name, ' ', '')"));
                orParts.add("(m.nutrition.confidence >= :minConfidence AND "
                        + tokenMatch(tokens, "REPLACE(o.representativeName, ' ', '')") + ")");
            }
            if (derivedFoodType != null) {
                orParts.add(":derivedFoodType MEMBER OF m.foodTypes");
            }
            jpql.append(" AND (").append(String.join(" OR ", orParts)).append(")");
        }

        TypedQuery<Menu> query = entityManager.createQuery(jpql.toString(), Menu.class)
                .setParameter("cafeDessert", Cuisine.CAFE_DESSERT)
                .setParameter("cuisine", cuisine)
                .setParameter("selectedFoodType", selectedFoodType);

        if (hasKeyword) {
            query.setParameter("minConfidence", BigDecimal.valueOf(MIN_MATCH_CONFIDENCE));
            for (int i = 0; i < tokens.size(); i++) {
                query.setParameter("kw" + i, tokens.get(i));
            }
        }
        if (derivedFoodType != null) {
            query.setParameter("derivedFoodType", derivedFoodType);
        }

        return query.getResultList();
    }

    // 주어진 필드 표현식에 검색어 단어 전부가 포함되는지(AND) 검사하는 JPQL 조각을 만든다.
    private String tokenMatch(List<String> tokens, String fieldExpr) {
        StringBuilder sb = new StringBuilder("(");
        for (int i = 0; i < tokens.size(); i++) {
            if (i > 0) {
                sb.append(" AND ");
            }
            sb.append(fieldExpr).append(" LIKE CONCAT('%', :kw").append(i).append(", '%')");
        }
        return sb.append(")").toString();
    }
}
