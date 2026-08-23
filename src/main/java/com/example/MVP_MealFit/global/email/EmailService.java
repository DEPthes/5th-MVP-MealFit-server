package com.example.MVP_MealFit.global.email;

import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.mail.SimpleMailMessage;
import org.springframework.mail.javamail.JavaMailSender;
import org.springframework.stereotype.Service;

@Service
@RequiredArgsConstructor
public class EmailService {

    private final JavaMailSender mailSender;

    @Value("${spring.mail.username}")
    private String from;

    @Value("${app.password-reset-url}")
    private String passwordResetUrl;

    public void sendPasswordResetEmail(
            String email,
            String token
    ) {

        String resetLink =
                passwordResetUrl + "?token=" + token;

        SimpleMailMessage message =
                new SimpleMailMessage();

        message.setFrom(from);
        message.setTo(email);
        message.setSubject("[MealFit] 비밀번호 재설정");

        message.setText(
                "안녕하세요. MealFit입니다.\n\n"
                        + "비밀번호 재설정을 요청하셨습니다.\n\n"
                        + "아래 링크를 통해 새로운 비밀번호를 설정해주세요.\n\n"
                        + resetLink
                        + "\n\n"
                        + "이 링크는 30분 동안만 유효합니다.\n"
                        + "본인이 요청하지 않았다면 이 메일을 무시해주세요."
        );

        mailSender.send(message);
    }
}