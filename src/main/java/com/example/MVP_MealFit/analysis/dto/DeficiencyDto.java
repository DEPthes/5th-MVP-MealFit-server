package com.example.MVP_MealFit.analysis.dto;

import com.example.MVP_MealFit.analysis.domain.Deficiency;
import com.example.MVP_MealFit.member.domain.Disease;

import java.util.List;

public record DeficiencyDto(
        int priority,
        String issue,
        List<String> relatedDiseases,
        String description
) {
    public static DeficiencyDto from(Deficiency d, String description) {
        return new DeficiencyDto(
                d.priority(),
                d.issue().getLabel(),
                d.relatedDiseases().stream().map(Disease::name).toList(),
                description
        );
    }
}