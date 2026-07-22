package com.example.MVP_MealFit.member.dto;

import com.example.MVP_MealFit.member.domain.ActivityLevel;
import com.example.MVP_MealFit.member.domain.Gender;
import com.example.MVP_MealFit.member.domain.Goal;
import com.example.MVP_MealFit.member.domain.Member;

import java.time.LocalDate;

public class MemberResponse {

    private final Long memberId;
    private final String email;
    private final String nickname;
    private final Double height;
    private final Gender gender;
    private final LocalDate birthDate;
    private final ActivityLevel activityLevel;
    private final Goal goal;
    private final boolean hasTarget;

    private MemberResponse(Long memberId, String email, String nickname, Double height,
                           Gender gender, LocalDate birthDate, ActivityLevel activityLevel,
                           Goal goal, boolean hasTarget) {
        this.memberId = memberId;
        this.email = email;
        this.nickname = nickname;
        this.height = height;
        this.gender = gender;
        this.birthDate = birthDate;
        this.activityLevel = activityLevel;
        this.goal = goal;
        this.hasTarget = hasTarget;
    }

    public static MemberResponse from(Member member) {
        return new MemberResponse(
                member.getId(),
                member.getEmail(),
                member.getNickname(),
                member.getHeight(),
                member.getGender(),
                member.getBirthDate(),
                member.getActivityLevel(),
                member.getGoal(),
                member.getNutritionTarget() != null
        );
    }

    public Long getMemberId() { return memberId; }
    public String getEmail() { return email; }
    public String getNickname() { return nickname; }
    public Double getHeight() { return height; }
    public Gender getGender() { return gender; }
    public LocalDate getBirthDate() { return birthDate; }
    public ActivityLevel getActivityLevel() { return activityLevel; }
    public Goal getGoal() { return goal; }
    public boolean isHasTarget() { return hasTarget; }
}