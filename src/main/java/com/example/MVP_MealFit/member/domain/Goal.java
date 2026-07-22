package com.example.MVP_MealFit.member.domain;

public enum Goal {
    LOSS(-500),
    MAINTAIN(0),
    GAIN(300);

    private final int calorieAdjustment;

    Goal(int calorieAdjustment) {
        this.calorieAdjustment = calorieAdjustment;
    }

    public int getCalorieAdjustment() {
        return calorieAdjustment;
    }
}