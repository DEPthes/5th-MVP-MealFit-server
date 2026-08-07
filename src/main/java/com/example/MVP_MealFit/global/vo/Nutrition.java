package com.example.MVP_MealFit.global.vo;

import jakarta.persistence.Column;
import jakarta.persistence.Embeddable;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;

import java.math.BigDecimal;
@Embeddable
public class Nutrition {

    @Column(name = "nutrition_calories")
    private Integer calories;

    @Column(name = "nutrition_carbohydrate", precision = 8, scale = 2)
    private BigDecimal carbohydrate;

    @Column(name = "nutrition_protein", precision = 8, scale = 2)
    private BigDecimal protein;

    @Column(name = "nutrition_fat", precision = 8, scale = 2)
    private BigDecimal fat;

    @Enumerated(EnumType.STRING)
    @Column(name = "nutrition_source", length = 20)
    private NutritionSource source;

    @Column(name = "nutrition_confidence", precision = 4, scale = 3)
    private BigDecimal confidence;

    @Column(name = "nutrition_sodium", precision = 8, scale = 2)
    private BigDecimal sodium;

    protected Nutrition() {
        // JPA 기본 생성자
    }

    private Nutrition(Integer calories, BigDecimal carbohydrate, BigDecimal protein,
                      BigDecimal fat, NutritionSource source, BigDecimal confidence,
                      BigDecimal sodium) {
        this.calories = calories;
        this.carbohydrate = carbohydrate;
        this.protein = protein;
        this.fat = fat;
        this.source = source;
        this.confidence = confidence;
        this.sodium = sodium;
    }

    // 공식 데이터 (confidence 없음, 나트륨 없음)
    public static Nutrition official(Integer calories, BigDecimal carbohydrate,
                                     BigDecimal protein, BigDecimal fat) {
        return new Nutrition(calories, carbohydrate, protein, fat, NutritionSource.OFFICIAL, null, null);
    }

    // 공식 데이터 + 나트륨 (식당 메뉴 조회용 — menu.nutrition_sodium 매핑)
    public static Nutrition official(Integer calories, BigDecimal carbohydrate,
                                     BigDecimal protein, BigDecimal fat, BigDecimal sodium) {
        return new Nutrition(calories, carbohydrate, protein, fat, NutritionSource.OFFICIAL, null, sodium);
    }

    // AI 추정 데이터 (confidence 있음)
    public static Nutrition estimated(Integer calories, BigDecimal carbohydrate,
                                      BigDecimal protein, BigDecimal fat, BigDecimal confidence) {
        return new Nutrition(calories, carbohydrate, protein, fat, NutritionSource.ESTIMATED, confidence, null);
    }

    public Integer getCalories() { return calories; }
    public BigDecimal getCarbohydrate() { return carbohydrate; }
    public BigDecimal getProtein() { return protein; }
    public BigDecimal getFat() { return fat; }
    public NutritionSource getSource() { return source; }
    public BigDecimal getConfidence() { return confidence; }
    public BigDecimal getSodium() { return sodium; }
}
