package com.example.MVP_MealFit.member.domain;

public enum ExerciseIntensity {
    LOW(1, "저강도"),
    MEDIUM(2, "중강도"),
    HIGH(3, "고강도");

    private final int score;
    private final String displayName;

    ExerciseIntensity(int score, String displayName) {
        this.score = score;
        this.displayName = displayName;
    }

    public int getScore() {
        return score;
    }

    public String getDisplayName() {
        return displayName;
    }
}
