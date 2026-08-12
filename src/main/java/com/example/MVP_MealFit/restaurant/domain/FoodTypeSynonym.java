package com.example.MVP_MealFit.restaurant.domain;

import jakarta.persistence.*;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.Immutable;

@Entity
@Getter
@Immutable
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@Table(name = "food_type_synonym")
public class FoodTypeSynonym {

    // 동의어 PK
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(insertable = false, updatable = false)
    private Long id;

    // 검색어 표면형
    @Column(nullable = false, unique = true, insertable = false, updatable = false)
    private String term;

    // 매핑 대상 음식 종류
    @Enumerated(EnumType.STRING)
    @Column(nullable = false, insertable = false, updatable = false)
    private FoodType foodType;
}
