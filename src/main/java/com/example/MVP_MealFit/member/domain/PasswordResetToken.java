package com.example.MVP_MealFit.member.domain;

import jakarta.persistence.*;
import lombok.Getter;

import java.time.LocalDateTime;
import java.util.UUID;

@Entity
@Getter
@Table(name = "password_reset_token")
public class PasswordResetToken {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;


    // 비밀번호 재설정용 랜덤 토큰
    @Column(nullable = false, unique = true, length = 100)
    private String token;

    // 토큰을 발급받은 회원
    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "member_id", nullable = false)
    private Member member;

    // 토큰 만료 시각
    @Column(nullable = false)
    private LocalDateTime expiresAt;

    // 이미 사용한 토큰인지 여부
    @Column(nullable = false)
    private boolean used;

    protected PasswordResetToken() {
        // JPA 기본 생성자
    }

    public PasswordResetToken(
            Member member,
            LocalDateTime expiresAt
    ) {
        this.token = UUID.randomUUID().toString();
        this.member = member;
        this.expiresAt = expiresAt;
        this.used = false;
    }

    public boolean isExpired() {
        return LocalDateTime.now().isAfter(expiresAt);
    }

    public boolean isUsable() {
        return !used && !isExpired();
    }

    public void use() {
        this.used = true;
    }
}