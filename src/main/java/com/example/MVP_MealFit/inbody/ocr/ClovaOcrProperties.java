package com.example.MVP_MealFit.inbody.ocr;

import lombok.Getter;
import lombok.Setter;
import org.springframework.boot.context.properties.ConfigurationProperties;

@Getter
@Setter
@ConfigurationProperties(prefix = "clova.ocr")
public class ClovaOcrProperties {
    // CLOVA OCR Invoke URL
    private String invokeUrl;

    // CLOVA OCR Secret Key
    private String secretKey;
}
