package com.example.MVP_MealFit.restaurant.domain;

import com.example.MVP_MealFit.global.common.BaseTimeEntity;
import jakarta.persistence.*;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.Immutable;

import java.time.LocalDateTime;
import java.util.List;

@Entity
@Getter
@Immutable
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@Table(name = "restaurant")
public class Restaurant extends BaseTimeEntity {

    // 식당 PK
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(insertable = false, updatable = false)
    private Long id;

    // 식당명
    @Column(nullable = false, insertable = false, updatable = false)
    private String name;

    // 식당 주소
    @Column(nullable = false, insertable = false, updatable = false)
    private String address;

    // 명지대학교 정문까지의 거리(m)
    @Column(name = "distance_to_main_gate", nullable = false, insertable = false, updatable = false)
    private Integer distanceToMainGate;

    // 명지대학교 후문까지의 거리(m)
    @Column(name = "distance_to_back_gate", nullable = false, insertable = false, updatable = false)
    private Integer distanceToBackGate;

    // 음식 종류
    @Enumerated(EnumType.STRING)
    @Column(nullable = false, insertable = false, updatable = false)
    private Cuisine cuisine;

    // 위도 — 크롤러가 지오코딩해 적재. 지오코딩 실패 시 null
    @Column(insertable = false, updatable = false)
    private Double latitude;

    // 경도 — 크롤러가 지오코딩해 적재. 지오코딩 실패 시 null
    @Column(insertable = false, updatable = false)
    private Double longitude;

    // 크롤링 원본 URL
    @Column(nullable = false, unique = true, insertable = false, updatable = false)
    private String sourceUrl;

    // Python이 마지막으로 적재한 시각
    @Column(nullable = false, insertable = false, updatable = false)
    private LocalDateTime crawledAt;

    // 식당 메뉴 목록
    @OneToMany(mappedBy = "restaurant", fetch = FetchType.LAZY)
    private List<Menu> menus;
}
