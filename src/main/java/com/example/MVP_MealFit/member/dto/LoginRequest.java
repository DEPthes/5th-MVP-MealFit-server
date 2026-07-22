package com.example.MVP_MealFit.member.dto;


import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;

public class LoginRequest{
    @NotBlank
    @Email
    private String email;

    @NotBlank
    private String password;

    protected LoginRequest() {
    }

    public String getEmail() { return email; }
    public String getPassword() { return password; }
}
