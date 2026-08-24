package com.example.MVP_MealFit.recommendation.domain;

import com.example.MVP_MealFit.global.vo.Nutrition;
import lombok.Getter;

import java.math.BigDecimal;

/**
 * 홈 화면 영양 필터 버튼 (FR-010). 100g당 절대 수치 기준이다 — 사용자 개인 목표와
 * 무관하게 판정한다. 한 번에 하나만 선택된다. 영양정보가 없는 메뉴는 모든 필터에서
 * false — 버튼을 켜면 영양정보 없는 메뉴는 결과에서 제외된다(검색 겸용 엔드포인트의
 * 질환 경고와는 다르다 — 경고는 결과를 남기고 표시만 하지만, 이 필터는 사용자가
 * 명시적으로 고른 조건이라 진짜 제외한다).
 * <p>
 * 임계값 근거는 우리 DB 182건이 아니라 **식약처 DB 전체(16,910건) 분포**로 검증했다 —
 * 182건은 매칭률이 낮아(18%) 밥·면·고기류에 쏠린 편향 표본이다. 식품기원 중 외식
 * 계열(85%)이 식당 메뉴를 다루는 이 서비스와 가장 가까운 모집단이라 그 열을 기준으로
 * 삼았다. FR-010에 칼로리 필터는 없다(목표에 따라 방향이 반대가 되는 값이라 FR-008
 * 기본 정렬에서 이미 처리됨) — 여기 넣지 않는다.
 */
@Getter
public enum NutritionFilter {

    // 단백질 >= 11g/100g — FR-010에 수치 없음 → 식약처 "고단백" 공식 기준(1일 기준치
    // 55g의 20%). 식약처 외식 계열 30.4%, 우리 DB 30건
    HIGH_PROTEIN("고단백") {
        @Override
        public boolean matches(Nutrition n) {
            BigDecimal protein = n == null ? null : n.getProtein();
            return protein != null && protein.compareTo(BigDecimal.valueOf(11)) >= 0;
        }
    },
    // 탄수화물 <= 20g/100g — FR-010 원문은 "1회 제공량 40g 이하"이나 100g당 절대
    // 수치로 통일하며 같은 백분위가 되도록 재산정(식약처 외식 계열 52.7% ≈ FR-010
    // 제공량 기준 51.0%). 우리 DB 110건
    LOW_CARB("저탄수") {
        @Override
        public boolean matches(Nutrition n) {
            BigDecimal carbohydrate = n == null ? null : n.getCarbohydrate();
            return carbohydrate != null && carbohydrate.compareTo(BigDecimal.valueOf(20)) <= 0;
        }
    },
    // 탄수화물 >= 40g/100g — FR-010 원문 "1회 제공량 60g 이상"의 숫자(40)를 100g당
    // 기준에 그대로 채택. 식약처 외식 계열 14.7%로 저탄수보다 훨씬 빡빡하다.
    // ⚠ 우리 DB(182건)에서는 현재 0건 — 100g당 최대 탄수화물이 36.8g이라 아직 못
    // 넘는다. 임계값 문제가 아니라 브랜드 매칭률이 낮아 짜장면 등 고탄수 메뉴가
    // 영양정보와 아직 연결되지 않은 상태다(매칭 늘면 자연히 채워진다)
    HIGH_CARB("고탄수") {
        @Override
        public boolean matches(Nutrition n) {
            BigDecimal carbohydrate = n == null ? null : n.getCarbohydrate();
            return carbohydrate != null && carbohydrate.compareTo(BigDecimal.valueOf(40)) >= 0;
        }
    },
    // 나트륨 <= 120mg/100g — FR-010 명시값. 식약처 외식 계열 32.9%로 필터로서
    // 적절하나, 우리 DB는 7건(3.8%)뿐이다. 이건 임계값이 짜서가 아니라 매칭된
    // 182건이 저나트륨 구간(찜·샐러드류)을 비워둔 표본 편향이다 — 120mg을 그대로 쓴다
    LOW_SODIUM("저나트륨") {
        @Override
        public boolean matches(Nutrition n) {
            BigDecimal sodium = n == null ? null : n.getSodium();
            return sodium != null && sodium.compareTo(BigDecimal.valueOf(120)) <= 0;
        }
    },
    // 지방 <= 3g/100g — FR-010 명시값, 식약처 "저지방" 공식 기준과도 일치.
    // 식약처 외식 계열 36.0%, 우리 DB 83건
    LOW_FAT("저지방") {
        @Override
        public boolean matches(Nutrition n) {
            BigDecimal fat = n == null ? null : n.getFat();
            return fat != null && fat.compareTo(BigDecimal.valueOf(3)) <= 0;
        }
    },
    // 역류성식도염 안전
    // 현재 보유한 영양정보를 기준으로 지방과 나트륨을 함께 제한한다.
    // 지방 <= 5g/100g, 나트륨 <= 400mg/100g
    REFLUX_ESOPHAGITIS_SAFE("역류성식도염 안전") {
        @Override
        public boolean matches(Nutrition n) {
            if (n == null) {
                return false;
            }

            BigDecimal fat = n.getFat();
            BigDecimal sodium = n.getSodium();

            return fat != null
                    && sodium != null
                    && fat.compareTo(BigDecimal.valueOf(5)) <= 0
                    && sodium.compareTo(BigDecimal.valueOf(400)) <= 0;
        }
    };

    private final String displayName;

    NutritionFilter(String displayName) {
        this.displayName = displayName;
    }

    // 영양정보가 없으면 false — 필터를 켜면 그 메뉴는 제외된다.
    public abstract boolean matches(Nutrition n);
}
