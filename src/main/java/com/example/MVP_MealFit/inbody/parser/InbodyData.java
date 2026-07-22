package com.example.MVP_MealFit.inbody.parser;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.Optional;

public record InbodyData(
        BigDecimal weight,
        BigDecimal skeletalMuscleMass,
        BigDecimal bodyFatPercentage,
        Integer bmr,
        Optional<LocalDate> measuredAt) {
}
