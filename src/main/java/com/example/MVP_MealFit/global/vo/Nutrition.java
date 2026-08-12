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

    @Column(name = "nutrition_sodium", precision = 8, scale = 2)
    private BigDecimal sodium;

    @Enumerated(EnumType.STRING)
    @Column(name = "nutrition_source", length = 20)
    private NutritionSource source;

    @Column(name = "nutrition_confidence", precision = 4, scale = 3)
    private BigDecimal confidence;

    protected Nutrition() {
        // JPA 기본 생성자
    }

    private Nutrition(Integer calories, BigDecimal carbohydrate, BigDecimal protein,
                      BigDecimal fat, BigDecimal sodium, NutritionSource source, BigDecimal confidence) {
        this.calories = calories;
        this.carbohydrate = carbohydrate;
        this.protein = protein;
        this.fat = fat;
        this.sodium = sodium;
        this.source = source;
        this.confidence = confidence;
    }

    // 공식 데이터 (confidence 없음, sodium 없음 )
    public static Nutrition official(Integer calories, BigDecimal carbohydrate,
                                     BigDecimal protein, BigDecimal fat) {
        return new Nutrition(calories, carbohydrate, protein, fat, null, NutritionSource.OFFICIAL, null);
    }

    // 공식 데이터 (confidence 없음, sodium 있음)
    public static Nutrition official(Integer calories, BigDecimal carbohydrate,
                                     BigDecimal protein, BigDecimal fat, BigDecimal sodium) {
        return new Nutrition(calories, carbohydrate, protein, fat, sodium, NutritionSource.OFFICIAL, null);
    }

    // AI 추정 데이터 (confidence 있음, sodium 없음 )
    public static Nutrition estimated(Integer calories, BigDecimal carbohydrate,
                                      BigDecimal protein, BigDecimal fat, BigDecimal confidence) {
        return new Nutrition(calories, carbohydrate, protein, fat, null, NutritionSource.ESTIMATED, confidence);
    }

    // AI 추정 데이터 (confidence 있음, sodium 있음)
    public static Nutrition estimated(Integer calories, BigDecimal carbohydrate,
                                      BigDecimal protein, BigDecimal fat, BigDecimal sodium, BigDecimal confidence) {
        return new Nutrition(calories, carbohydrate, protein, fat, sodium, NutritionSource.ESTIMATED, confidence);
    }

    public Integer getCalories() { return calories; }
    public BigDecimal getCarbohydrate() { return carbohydrate; }
    public BigDecimal getProtein() { return protein; }
    public BigDecimal getFat() { return fat; }
    public BigDecimal getSodium() { return sodium; }
    public NutritionSource getSource() { return source; }
    public BigDecimal getConfidence() { return confidence; }
}
