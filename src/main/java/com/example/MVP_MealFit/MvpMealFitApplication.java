package com.example.MVP_MealFit;

import com.example.MVP_MealFit.inbody.ocr.ClovaOcrProperties;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.EnableConfigurationProperties;

@EnableConfigurationProperties(ClovaOcrProperties.class)
@SpringBootApplication
public class MvpMealFitApplication {

	public static void main(String[] args) {
		SpringApplication.run(MvpMealFitApplication.class, args);
	}

}
