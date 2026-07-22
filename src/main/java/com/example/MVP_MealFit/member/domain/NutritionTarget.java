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

    public Nutrition perMeal() {
        return Nutrition.official(
                target.getCalories() / 3,
                divideByThree(target.getCarbohydrate()),
                divideByThree(target.getProtein()),
                divideByThree(target.getFat())
        );
    }

    public boolean isBasedOn(Long inbodyId) {
        return sourceInbodyId != null && sourceInbodyId.equals(inbodyId);
    }

    private BigDecimal divideByThree(BigDecimal value) {
        return value.divide(BigDecimal.valueOf(3), 2, java.math.RoundingMode.HALF_UP);
    }

    public Long getId() { return id; }
    public Nutrition getTarget() { return target; }
    public Long getSourceInbodyId() { return sourceInbodyId; }
    public LocalDateTime getCalculatedAt() { return calculatedAt; }
}
