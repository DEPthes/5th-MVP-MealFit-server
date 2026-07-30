package com.example.MVP_MealFit.analysis.service;

import com.example.MVP_MealFit.analysis.domain.Deficiency;
import com.example.MVP_MealFit.analysis.dto.DeficiencyDto;
import com.example.MVP_MealFit.analysis.dto.NutritionDto;
import com.example.MVP_MealFit.analysis.dto.ReportResponse;
import com.example.MVP_MealFit.global.exception.BusinessException;
import com.example.MVP_MealFit.global.exception.ErrorCode;
import com.example.MVP_MealFit.inbody.domain.Inbody;
import com.example.MVP_MealFit.inbody.service.InbodyService;
import com.example.MVP_MealFit.member.domain.Disease;
import com.example.MVP_MealFit.member.domain.NutritionTarget;
import com.example.MVP_MealFit.member.service.MemberService;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

/**
 * AI 영양 리포트 (FR-006)
 * 목표 영양치 + 인바디 점수 + 부족 영양소 카드를 조합해 반환.
 * 숫자·카드는 코드로 산출. (AI 요약은 추후 추가)
 */
@Service
@RequiredArgsConstructor
public class ReportService {

    private final MemberService memberService;
    private final InbodyService inbodyService;
    private final DeficiencyResolver deficiencyResolver;
    private final AiClient aiClient;

    @Transactional(readOnly = true)
    public ReportResponse getReport(Long memberId) {
        // 최신 인바디 (점수·기준)
        Inbody inbody = inbodyService.findLatestInbody(memberId)
                .orElseThrow(() -> new BusinessException(ErrorCode.INBODY_NOT_FOUND));

        // 저장된 목표 영양치
        NutritionTarget target = memberService.findNutritionTarget(memberId)
                .orElseThrow(() -> new BusinessException(ErrorCode.TARGET_NOT_READY));

        // 기저질환 → 부족 영양소 카드
        List<Disease> diseases = memberService.getDiseases(memberId);
        List<Deficiency> cards = deficiencyResolver.resolve(diseases);

        String summary = aiClient.summarize(inbody.getInbodyScore(), cards);

        return new ReportResponse(
                inbody.getInbodyScore(),
                NutritionDto.from(target.getTarget()),
                cards.stream().map(DeficiencyDto::from).toList(),
                summary,
                inbody.getId()
        );
    }
}