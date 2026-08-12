package com.example.MVP_MealFit.restaurant.domain;

import com.example.MVP_MealFit.global.vo.Nutrition;
import com.example.MVP_MealFit.global.vo.NutritionSource;
import jakarta.persistence.*;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.Immutable;

import java.util.HashSet;
import java.util.Set;

@Entity
@Getter
@Immutable
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@Table(name = "menu")
public class Menu {

    // 메뉴 PK
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(insertable = false, updatable = false)
    private Long id;

    // 소속 식당
    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "restaurant_id", nullable = false, insertable = false, updatable = false)
    private Restaurant restaurant;

    // 원본 메뉴명
    @Column(nullable = false, insertable = false, updatable = false)
    private String name;

    // 정규화된 메뉴명
    @Column(nullable = false, insertable = false, updatable = false)
    private String normalizedName;

    // 메뉴 가격
    @Column(insertable = false, updatable = false)
    private Integer price;

    // 메뉴 음식 종류
    @ElementCollection(fetch = FetchType.EAGER)
    @CollectionTable(
            name = "menu_food_type",
            joinColumns = @JoinColumn(name = "menu_id")
    )
    @Enumerated(EnumType.STRING)
    @Column(name = "food_type")
    private Set<FoodType> foodTypes = new HashSet<>();

    // 메뉴 영양 정보
    @Embedded
    private Nutrition nutrition;

    // 식약처 매칭 결과 (대표식품명 검색용). 매칭 안 된 메뉴는 null
    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "official_food_code", referencedColumnName = "food_code",
            insertable = false, updatable = false)
    private OfficialFood officialFood;

    // 해당 음식 종류를 포함하는지 확인
    public boolean hasFoodType(FoodType type) {
        return foodTypes.contains(type);
    }

    // 영양 정보의 신뢰도 확인
    public boolean isNutritionReliable(double minConfidence) {
        if (nutrition == null) {
            return false;
        }

        // 공공 데이터는 항상 신뢰
        if (nutrition.getSource() == NutritionSource.OFFICIAL) {
            return true;
        }

        // AI 추정 데이터는 confidence 기준으로 판단
        return nutrition.getConfidence() != null && nutrition.getConfidence().doubleValue() >= minConfidence;
    }
}