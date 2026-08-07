package com.example.MVP_MealFit.restaurant.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.Immutable;

// 식약처 식품 검색용 읽기 전용 엔티티. 영양정보는 이미 menu에 복사돼 있어 매핑하지 않는다.
@Entity
@Getter
@Immutable
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@Table(name = "official_food")
public class OfficialFood {

    // 식품코드 PK
    @Id
    @Column(name = "food_code", insertable = false, updatable = false)
    private String foodCode;

    // 식품명
    @Column(name = "food_name", insertable = false, updatable = false)
    private String foodName;

    // 대표식품명 — FoodType보다 세밀한 음식 종류 중간 계층 (예: "국밥", "짜장")
    @Column(name = "representative_name", insertable = false, updatable = false)
    private String representativeName;
}
