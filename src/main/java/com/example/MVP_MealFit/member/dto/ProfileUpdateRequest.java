package com.example.MVP_MealFit.member.dto;

import com.example.MVP_MealFit.member.domain.ActivityLevel;
import com.example.MVP_MealFit.member.domain.Disease;
import com.example.MVP_MealFit.member.domain.Goal;
import jakarta.validation.constraints.Positive;

import java.util.List;

public class ProfileUpdateRequest {

    private String nickname;

    @Positive
    private Double height;

    private ActivityLevel activityLevel;

    private Goal goal;
    private List<Disease> diseases;

    protected ProfileUpdateRequest() {
    }
    public List<Disease> getDiseases() { return diseases; }
    public String getNickname() { return nickname; }
    public Double getHeight() { return height; }
    public ActivityLevel getActivityLevel() { return activityLevel; }
    public Goal getGoal() { return goal; }
}
