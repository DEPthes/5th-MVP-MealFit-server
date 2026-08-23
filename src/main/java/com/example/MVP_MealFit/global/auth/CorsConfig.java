package com.example.MVP_MealFit.global.auth;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.cors.CorsConfiguration;
import org.springframework.web.cors.CorsConfigurationSource;
import org.springframework.web.cors.UrlBasedCorsConfigurationSource;

import java.util.List;

/**
 * 프론트엔드(브라우저)에서 이 서버의 API를 호출할 수 있도록 허용해주는 설정.
 * 허용할 주소는 application.properties의 app.cors.allowed-origins 또는
 * 환경변수 APP_CORS_ALLOWED_ORIGINS 로 지정한다. (쉼표로 여러 개 구분)
 */
@Configuration
public class CorsConfig {

    private static final List<String> DEFAULT_ORIGINS = List.of(
            "http://localhost:3000",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "https://5th-mvp-mealfit-web.vercel.app",
            // Vercel이 PR마다 만들어주는 미리보기 주소까지 함께 허용
            "https://5th-mvp-mealfit-web-*.vercel.app"
    );

    private final List<String> allowedOrigins;

    public CorsConfig(
            @Value("${app.cors.allowed-origins:}") List<String> allowedOrigins
    ) {
        List<String> normalized = normalize(allowedOrigins);
        this.allowedOrigins = normalized.isEmpty() ? DEFAULT_ORIGINS : normalized;
    }

    /**
     * 브라우저가 보내는 Origin 값에는 끝에 슬래시(/)가 붙지 않는다.
     * 설정에 "http://localhost:5173/" 처럼 슬래시가 들어가 있으면 영원히 매칭되지 않으므로
     * 앞뒤 공백과 끝의 슬래시를 미리 떼어낸다.
     */
    private static List<String> normalize(List<String> origins) {
        if (origins == null) {
            return List.of();
        }
        return origins.stream()
                .filter(origin -> origin != null)
                .map(String::trim)
                .filter(origin -> !origin.isEmpty())
                .map(origin -> origin.endsWith("/") ? origin.substring(0, origin.length() - 1) : origin)
                .toList();
    }

    @Bean
    public CorsConfigurationSource corsConfigurationSource() {
        CorsConfiguration config = new CorsConfiguration();

        // setAllowedOriginPatterns를 쓰면 https://*.vercel.app 같은 와일드카드도 사용 가능
        config.setAllowedOriginPatterns(allowedOrigins);
        config.setAllowedMethods(List.of("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"));
        // "*" 는 프론트가 보낸 요청 헤더를 그대로 허용한다는 뜻 (Content-Type, Authorization 포함)
        config.setAllowedHeaders(List.of("*"));
        config.setExposedHeaders(List.of("Authorization"));
        config.setAllowCredentials(true);
        // 브라우저가 사전 확인(preflight) 결과를 1시간 동안 재사용하도록 해 요청 수를 줄인다.
        config.setMaxAge(3600L);

        UrlBasedCorsConfigurationSource source = new UrlBasedCorsConfigurationSource();
        source.registerCorsConfiguration("/**", config);
        return source;
    }
}
