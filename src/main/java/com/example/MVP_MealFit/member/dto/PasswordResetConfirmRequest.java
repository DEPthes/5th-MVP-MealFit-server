package com.example.MVP_MealFit.member.dto;

import jakarta.validation.constraints.NotBlank;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class PasswordResetConfirmRequest {

    @NotBlank
    private String token;

    @NotBlank
    private String newPassword;
}