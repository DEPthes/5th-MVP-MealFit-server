package com.example.MVP_MealFit.member.domain;

import com.example.MVP_MealFit.global.common.BaseTimeEntity;
import com.example.MVP_MealFit.global.vo.Nutrition;
import jakarta.persistence.Embedded;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;

import java.math.BigDecimal;
import java.time.LocalDateTime;

@Entity
public class NutritionTarget extends BaseTimeEntity {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Embedded
    private Nutrition target;

    private Long sourceInbodyId;

    private LocalDateTime calculatedAt;

    protected NutritionTarget() {
        // JPA 기본 생성자
    }

    public NutritionTarget(Nutrition target, Long sourceInbodyId, LocalDateTime calculatedAt) {
        this.target = target;
        this.sourceInbodyId = sourceInbodyId;
        this.calculatedAt = calculatedAt;
    }

    /**
     * 한 끼 기준 영양치를 계산
     * 하루 목표치(target)를 하루 세 끼(3)로 균등 분배한 값이며,
     * recommendation 패키지가 메뉴 추천 시 비교 기준으로 사용한다.
     * 모든 필드(calories, carbohydrate, protein, fat, sodium)에 동일하게 1/3 규칙을 적용해 일관성을 유지함.
     */

    public Nutrition perMeal() {
        return Nutrition.official(
                target.getCalories() / 3,
                divideByThree(target.getCarbohydrate()),
                divideByThree(target.getProtein()),
                divideByThree(target.getFat()),
                divideByThree(target.getSodium())
        );
    }
    public boolean isBasedOn(Long inbodyId) {
        return sourceInbodyId != null && sourceInbodyId.equals(inbodyId);
    }

    private BigDecimal divideByThree(BigDecimal value) {
        if (value == null) {
            return null;
        }
        return value.divide(BigDecimal.valueOf(3), 2, java.math.RoundingMode.HALF_UP);
    }

    public Long getId() { return id; }
    public Nutrition getTarget() { return target; }
    public Long getSourceInbodyId() { return sourceInbodyId; }
    public LocalDateTime getCalculatedAt() { return calculatedAt; }
}
