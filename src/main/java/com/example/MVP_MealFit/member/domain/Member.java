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
import jakarta.persistence.*;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

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

    private Double targetWeight;

    @Enumerated(EnumType.STRING)
    private Gender gender;

    private LocalDate birthDate;


    @Enumerated(EnumType.STRING)
    private ExerciseCount exerciseCount;

    @Enumerated(EnumType.STRING)
    private ExerciseIntensity exerciseIntensity;

    @Enumerated(EnumType.STRING)
    private Goal goal;

    @OneToOne(cascade = CascadeType.ALL, orphanRemoval = true)
    private NutritionTarget nutritionTarget;

    @ElementCollection(fetch = FetchType.LAZY)
    @CollectionTable(name = "member_disease", joinColumns = @JoinColumn(name = "member_id"))
    @Enumerated(EnumType.STRING)
    @Column(name = "disease")
    private List<Disease> diseases = new ArrayList<>();

    protected Member() {
        // JPA 기본 생성자
    }
    public Member(String email, String password, String nickname, Double height, Double targetWeight,
                  Gender gender, LocalDate birthDate,
                  ExerciseCount exerciseCount, ExerciseIntensity exerciseIntensity, Goal goal) {
        this.email = email;
        this.password = password;
        this.nickname = nickname;
        this.height = height;
        this.targetWeight = targetWeight;
        this.gender = gender;
        this.birthDate = birthDate;
        this.exerciseCount = exerciseCount;
        this.exerciseIntensity = exerciseIntensity;
        this.goal = goal;
    }

    public void updateProfile(String nickname, Double height, Double targetWeight,
                               ExerciseCount exerciseCount, ExerciseIntensity exerciseIntensity, Goal goal) {
        if (nickname != null) {
            this.nickname = nickname;
        }
        if (height != null) {
            this.height = height;
        }
        if (targetWeight != null) {
            this.targetWeight = targetWeight;
        }
        if (exerciseCount != null) {
            this.exerciseCount = exerciseCount;
        }
        if (exerciseIntensity != null) {
            this.exerciseIntensity = exerciseIntensity;
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

    public void updateDiseases(List<Disease> diseases) {
        this.diseases.clear();
        this.diseases.addAll(diseases);
    }

    public List<Disease> getDiseases() {
        return Collections.unmodifiableList(diseases);
    }

    public Long getId() { return id; }
    public String getEmail() { return email; }
    public String getPassword() { return password; }
    public String getNickname() { return nickname; }
    public Double getHeight() { return height; }
    public Double getTargetWeight() { return targetWeight; }
    public Gender getGender() { return gender; }
    public LocalDate getBirthDate() { return birthDate; }
    public ExerciseCount getExerciseCount() { return exerciseCount; }
    public ExerciseIntensity getExerciseIntensity() { return exerciseIntensity; }
    public Goal getGoal() { return goal; }
    public NutritionTarget getNutritionTarget() { return nutritionTarget; }
}