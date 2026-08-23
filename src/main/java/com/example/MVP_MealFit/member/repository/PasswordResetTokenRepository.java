package com.example.MVP_MealFit.member.repository;

import com.example.MVP_MealFit.member.domain.Member;
import com.example.MVP_MealFit.member.domain.PasswordResetToken;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;

public interface PasswordResetTokenRepository extends JpaRepository<PasswordResetToken, Long> {

    Optional<PasswordResetToken> findByToken(String token);

    void deleteByMember(Member member);
}