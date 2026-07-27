package com.example.MVP_MealFit.restaurant.service;

import com.example.MVP_MealFit.restaurant.domain.FoodType;
import com.example.MVP_MealFit.restaurant.domain.FoodTypeSynonym;
import com.example.MVP_MealFit.restaurant.repository.SynonymRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;

import java.util.Locale;
import java.util.Optional;

@Component
@RequiredArgsConstructor
public class SynonymResolver {

    private final SynonymRepository synonymRepository;

    // 검색어를 음식 종류로 변환
    public Optional<FoodType> resolve(String userInput) {

        if (userInput == null || userInput.isBlank()) {
            return Optional.empty();
        }

        String normalized = userInput
                .toLowerCase(Locale.ROOT)
                .replaceAll("\\s+", "");

        return synonymRepository.findByTerm(normalized)
                .map(FoodTypeSynonym::getFoodType);
    }
}
