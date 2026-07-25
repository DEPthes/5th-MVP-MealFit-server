package com.example.MVP_MealFit.restaurant.repository;

import com.example.MVP_MealFit.restaurant.domain.FoodTypeSynonym;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;

public interface SynonymRepository extends JpaRepository<FoodTypeSynonym, Long> {

    // 검색어에 해당하는 음식 종류 조회
    Optional<FoodTypeSynonym> findByTerm(String normalizedTerm);
}
