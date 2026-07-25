package com.example.MVP_MealFit.inbody.domain;

import com.example.MVP_MealFit.member.domain.Member;
import jakarta.persistence.*;
import lombok.*;

import java.math.BigDecimal;
import java.time.LocalDate;

@Entity
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@AllArgsConstructor
@Builder
@Table(name = "inbody")
public class Inbody {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    // member_id
    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "member_id", nullable = false)
    private Member member;

    // 체중
    @Column(nullable = false, precision = 6, scale = 2)
    private BigDecimal weight;

    // 골격근량
    @Column(name = "muscle_mass", precision = 6, scale = 2)
    private BigDecimal skeletalMuscleMass;

    // 체지방률
    @Column(name = "body_fat_percentage", precision = 6, scale = 2)
    private BigDecimal bodyFatPercentage;

    // 기초대사량
    @Column(nullable = false)
    private Integer bmr;

    // 인바디 점수
    @Column(name = "inbody_score", nullable = false)
    private Integer inbodyScore;

    // 측정일
    @Column(name = "measured_at", nullable = false)
    private LocalDate measuredAt;

    // 업로드일
    @Column(name = "uploaded_at", nullable = false)
    private LocalDate uploadedAt;

    // OCR 원본 이미지 저장 경로
    @Column(name = "image_path", nullable = false, length = 500)
    private String imagePath;

    // 인바디 결과지 업로드 파일 이름
    @Column(name = "original_filename", nullable = false)
    private String originalFilename;

    // 인바디 결과지 업로드 파일 크기
    @Column(name = "file_size", nullable = false)
    private Long fileSize;

    // 판정 기준 상수
    private static final int STALE_DAYS = 14;

    // 인바디 측정일이 14일을 초과했는지 확인
    public boolean isStale(LocalDate today) {
        return measuredAt.plusDays(STALE_DAYS).isBefore(today);
    }
}