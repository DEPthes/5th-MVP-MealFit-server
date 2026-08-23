package com.example.MVP_MealFit.member.service;

import com.example.MVP_MealFit.global.email.EmailService;
import com.example.MVP_MealFit.global.exception.BusinessException;
import com.example.MVP_MealFit.global.exception.ErrorCode;
import com.example.MVP_MealFit.member.domain.Member;
import com.example.MVP_MealFit.member.domain.PasswordResetToken;
import com.example.MVP_MealFit.member.repository.MemberRepository;
import com.example.MVP_MealFit.member.repository.PasswordResetTokenRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;

@Service
@RequiredArgsConstructor
public class PasswordResetService {

    private static final long TOKEN_EXPIRATION_MINUTES = 30;

    private final MemberRepository memberRepository;
    private final PasswordResetTokenRepository passwordResetTokenRepository;
    private final PasswordEncoder passwordEncoder;
    private final EmailService emailService;

    /**
     * 비밀번호 재설정 이메일 요청
     */
    @Transactional
    public void requestReset(String email) {

        memberRepository.findByEmail(email)
                .ifPresent(member -> {

                    // 기존 재설정 토큰 제거
                    passwordResetTokenRepository.deleteByMember(member);

                    // 새로운 토큰 생성
                    PasswordResetToken resetToken =
                            new PasswordResetToken(
                                    member,
                                    LocalDateTime.now()
                                            .plusMinutes(TOKEN_EXPIRATION_MINUTES)
                            );

                    passwordResetTokenRepository.save(resetToken);

                    // 이메일 발송
                    emailService.sendPasswordResetEmail(
                            member.getEmail(),
                            resetToken.getToken()
                    );
                });
    }

    /**
     * 비밀번호 재설정
     */
    @Transactional
    public void resetPassword(
            String token,
            String newPassword
    ) {

        PasswordResetToken resetToken =
                passwordResetTokenRepository
                        .findByToken(token)
                        .orElseThrow(() ->
                                new BusinessException(
                                        ErrorCode.INVALID_PASSWORD_RESET_TOKEN
                                )
                        );

        if (!resetToken.isUsable()) {
            throw new BusinessException(
                    ErrorCode.INVALID_PASSWORD_RESET_TOKEN
            );
        }

        Member member = resetToken.getMember();

        // 새 비밀번호 암호화
        String encodedPassword =
                passwordEncoder.encode(newPassword);

        // 기존 Member의 비밀번호 변경 메서드 사용
        member.changePassword(encodedPassword);

        // 토큰 일회성 처리
        resetToken.use();
    }
}