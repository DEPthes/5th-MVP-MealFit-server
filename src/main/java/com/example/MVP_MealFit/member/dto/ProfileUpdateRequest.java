package com.example.MVP_MealFit.member.dto;

import com.example.MVP_MealFit.member.domain.ActivityLevel;
import com.example.MVP_MealFit.member.domain.Goal;
import jakarta.validation.constraints.Positive;

public class ProfileUpdateRequest {

    private String nickname;

    @Positive
    private Double height;

    private ActivityLevel activityLevel;

    private Goal goal;

    protected ProfileUpdateRequest() {
    }

    public String getNickname() { return nickname; }
    public Double getHeight() { return height; }
    public ActivityLevel getActivityLevel() { return activityLevel; }
    public Goal getGoal() { return goal; }
}
