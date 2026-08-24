package com.example.MVP_MealFit.member.dto;

import com.example.MVP_MealFit.member.domain.ActivityLevel;
import com.example.MVP_MealFit.member.domain.ExerciseCount;
import com.example.MVP_MealFit.member.domain.ExerciseIntensity;
import com.example.MVP_MealFit.member.domain.Gender;
import com.example.MVP_MealFit.member.domain.Goal;
import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Positive;

import java.time.LocalDate;

public class SignupRequest {

    @NotBlank
    @Email
    private String email;

    @NotBlank
    private String password;

    @NotBlank
    private String nickname;

    @Positive
    private Double height;

    @Positive
    private Double targetWeight;

    @NotNull
    private Gender gender;

    @NotNull
    private LocalDate birthDate;

    @NotNull
    private ActivityLevel activityLevel;

    // 계산 로직에는 아직 연결되지 않아 activityLevel과 달리 선택사항으로 둔다.
    private ExerciseCount exerciseCount;

    private ExerciseIntensity exerciseIntensity;

    @NotNull
    private Goal goal;

    protected SignupRequest() {
        // JSON 역직렬화용
    }

    public String getEmail() { return email; }
    public String getPassword() { return password; }
    public String getNickname() { return nickname; }
    public Double getHeight() { return height; }
    public Double getTargetWeight() { return targetWeight; }
    public Gender getGender() { return gender; }
    public LocalDate getBirthDate() { return birthDate; }
    public ActivityLevel getActivityLevel() { return activityLevel; }
    public ExerciseCount getExerciseCount() { return exerciseCount; }
    public ExerciseIntensity getExerciseIntensity() { return exerciseIntensity; }
    public Goal getGoal() { return goal; }
}