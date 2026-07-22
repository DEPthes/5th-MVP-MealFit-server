package com.example.MVP_MealFit.inbody.ocr;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.client.RestClient;

@Configuration
public class OcrConfig {

    @Bean
    public RestClient restClient() {
        return RestClient.builder().build();
    }
}
