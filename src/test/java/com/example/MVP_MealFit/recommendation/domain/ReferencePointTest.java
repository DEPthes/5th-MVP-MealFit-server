package com.example.MVP_MealFit.recommendation.domain;

import com.example.MVP_MealFit.restaurant.domain.Restaurant;
import org.junit.jupiter.api.Test;

import java.lang.reflect.Constructor;
import java.lang.reflect.Field;

import static org.assertj.core.api.Assertions.assertThat;

class ReferencePointTest {

    @Test
    void MAIN_GATE는_distanceToMainGate_컬럼값을_읽는다() throws Exception {
        Restaurant restaurant = restaurantWithDistances(150, 300);

        assertThat(ReferencePoint.MAIN_GATE.distanceMetersTo(restaurant)).isEqualTo(150);
    }

    @Test
    void BACK_GATE는_distanceToBackGate_컬럼값을_읽는다() throws Exception {
        Restaurant restaurant = restaurantWithDistances(150, 300);

        assertThat(ReferencePoint.BACK_GATE.distanceMetersTo(restaurant)).isEqualTo(300);
    }

    @Test
    void 거리_컬럼값이_없으면_null을_반환한다() throws Exception {
        Restaurant restaurant = restaurantWithDistances(null, null);

        assertThat(ReferencePoint.MAIN_GATE.distanceMetersTo(restaurant)).isNull();
        assertThat(ReferencePoint.BACK_GATE.distanceMetersTo(restaurant)).isNull();
    }

    // Restaurant는 크롤러 전용 @Immutable 엔티티라 생성자가 protected이고 세터가 없다 —
    // 테스트에서만 리플렉션으로 생성·필드 주입을 한다.
    private Restaurant restaurantWithDistances(Integer toMainGate, Integer toBackGate) throws Exception {
        Constructor<Restaurant> constructor = Restaurant.class.getDeclaredConstructor();
        constructor.setAccessible(true);
        Restaurant restaurant = constructor.newInstance();
        setField(restaurant, "distanceToMainGate", toMainGate);
        setField(restaurant, "distanceToBackGate", toBackGate);
        return restaurant;
    }

    private void setField(Object target, String fieldName, Object value) throws Exception {
        Field field = Restaurant.class.getDeclaredField(fieldName);
        field.setAccessible(true);
        field.set(target, value);
    }
}
