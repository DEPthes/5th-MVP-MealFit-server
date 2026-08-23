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

    private final List<String> allowedOrigins;

    public CorsConfig(
            @Value("${app.cors.allowed-origins:http://localhost:3000,http://localhost:5173}")
            List<String> allowedOrigins
    ) {
        this.allowedOrigins = allowedOrigins;
    }

    @Bean
    public CorsConfigurationSource corsConfigurationSource() {
        CorsConfiguration config = new CorsConfiguration();

        // setAllowedOriginPatterns를 쓰면 https://*.vercel.app 같은 와일드카드도 사용 가능
        config.setAllowedOriginPatterns(allowedOrigins);
        config.setAllowedMethods(List.of("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"));
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
