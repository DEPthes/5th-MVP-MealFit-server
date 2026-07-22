package com.example.MVP_MealFit.member.domain;

import com.example.MVP_MealFit.global.common.BaseTimeEntity;
import jakarta.persistence.CascadeType;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.OneToOne;

import java.time.LocalDate;
import java.time.Period;

@Entity
public class Member extends BaseTimeEntity {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(unique = true, nullable = false)
    private String email;

    @Column(nullable = false)
    private String password;

    @Column(nullable = false)
    private String nickname;

    private Double height;

    @Enumerated(EnumType.STRING)
    private Gender gender;

    private LocalDate birthDate;

    @Enumerated(EnumType.STRING)
    private ActivityLevel activityLevel;

    @Enumerated(EnumType.STRING)
    private Goal goal;

    @OneToOne(cascade = CascadeType.ALL, orphanRemoval = true)
    private NutritionTarget nutritionTarget;

    protected Member() {
        // JPA 기본 생성자
    }
    public Member(String email, String password, String nickname, Double height,
                  Gender gender, LocalDate birthDate, ActivityLevel activityLevel, Goal goal) {
        this.email = email;
        this.password = password;
        this.nickname = nickname;
        this.height = height;
        this.gender = gender;
        this.birthDate = birthDate;
        this.activityLevel = activityLevel;
        this.goal = goal;
    }

    public void updateProfile(String nickname, Double height, ActivityLevel activityLevel, Goal goal) {
        if (nickname != null) {
            this.nickname = nickname;
        }
        if (height != null) {
            this.height = height;
        }
        if (activityLevel != null) {
            this.activityLevel = activityLevel;
        }
        if (goal != null) {
            this.goal = goal;
        }
    }

    public void changePassword(String encodedPassword) {
        this.password = encodedPassword;
    }

    public void assignTarget(NutritionTarget target) {
        this.nutritionTarget = target;
    }

    public int getAge(LocalDate today) {
        return Period.between(birthDate, today).getYears();
    }

    public Long getId() { return id; }
    public String getEmail() { return email; }
    public String getPassword() { return password; }
    public String getNickname() { return nickname; }
    public Double getHeight() { return height; }
    public Gender getGender() { return gender; }
    public LocalDate getBirthDate() { return birthDate; }
    public ActivityLevel getActivityLevel() { return activityLevel; }
    public Goal getGoal() { return goal; }
    public NutritionTarget getNutritionTarget() { return nutritionTarget; }
}
