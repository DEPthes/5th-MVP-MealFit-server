package com.example.MVP_MealFit.analysis.service;

import com.example.MVP_MealFit.analysis.dto.TargetResponse;
import com.example.MVP_MealFit.global.exception.BusinessException;
import com.example.MVP_MealFit.global.exception.ErrorCode;
import com.example.MVP_MealFit.global.vo.Nutrition;
import com.example.MVP_MealFit.inbody.domain.Inbody;
import com.example.MVP_MealFit.inbody.service.InbodyService;
import com.example.MVP_MealFit.member.domain.Member;
import com.example.MVP_MealFit.member.domain.NutritionTarget;
import com.example.MVP_MealFit.member.service.MemberService;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;

@Service
@RequiredArgsConstructor
public class TargetService {

    private final MemberService memberService;
    private final InbodyService inbodyService;
    private final TargetCalculator targetCalculator;

    @Transactional
    public TargetResponse calculateTarget(Long memberId) {
        Member member = memberService.getMember(memberId);
        Inbody inbody = inbodyService.findLatestInbody(memberId)
                .orElseThrow(() -> new BusinessException(ErrorCode.INBODY_NOT_FOUND));

        Nutrition nutrition = targetCalculator.calculate(
                inbody.getBmr(),
                member.getActivityLevel(),
                member.getGoal()
        );

        NutritionTarget target =
                new NutritionTarget(nutrition, inbody.getId(), LocalDateTime.now());
        memberService.saveNutritionTarget(memberId, target);

        return TargetResponse.from(target, false);
    }

    @Transactional(readOnly = true)
    public TargetResponse findTarget(Long memberId) {
        NutritionTarget target = memberService.findNutritionTarget(memberId)
                .orElseThrow(() -> new BusinessException(ErrorCode.TARGET_NOT_READY));

        boolean outdated = inbodyService.findLatestInbody(memberId)
                .map(latest -> !target.isBasedOn(latest.getId()))
                .orElse(false);

        return TargetResponse.from(target, outdated);
    }
}