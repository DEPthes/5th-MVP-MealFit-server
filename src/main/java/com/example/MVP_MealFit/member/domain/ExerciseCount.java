package com.example.MVP_MealFit.member.domain;

public enum ExerciseCount {
    NONE(0, "주 0회"),
    ONE_TO_TWO(1, "주 1~2회"),
    THREE_TO_FOUR(2, "주 3~4회"),
    FIVE_TO_SIX(3, "주 5~6회");

    private final int score;
    private final String displayName;

    ExerciseCount(int score, String displayName) {
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
