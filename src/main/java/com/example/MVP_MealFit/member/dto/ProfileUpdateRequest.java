package com.example.MVP_MealFit.member.dto;

import com.example.MVP_MealFit.member.domain.ActivityLevel;
import com.example.MVP_MealFit.member.domain.Disease;
import com.example.MVP_MealFit.member.domain.ExerciseCount;
import com.example.MVP_MealFit.member.domain.ExerciseIntensity;
import com.example.MVP_MealFit.member.domain.Goal;
import jakarta.validation.constraints.Positive;

import java.util.List;

public class ProfileUpdateRequest {

    private String nickname;

    @Positive
    private Double height;

    @Positive
    private Double targetWeight;

    private ActivityLevel activityLevel;

    private ExerciseCount exerciseCount;

    private ExerciseIntensity exerciseIntensity;

    private Goal goal;
    private List<Disease> diseases;

    protected ProfileUpdateRequest() {
    }
    public List<Disease> getDiseases() { return diseases; }
    public String getNickname() { return nickname; }
    public Double getHeight() { return height; }
    public Double getTargetWeight() { return targetWeight; }
    public ActivityLevel getActivityLevel() { return activityLevel; }
    public ExerciseCount getExerciseCount() { return exerciseCount; }
    public ExerciseIntensity getExerciseIntensity() { return exerciseIntensity; }
    public Goal getGoal() { return goal; }
}
