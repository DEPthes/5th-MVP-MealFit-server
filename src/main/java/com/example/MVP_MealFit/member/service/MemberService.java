package com.example.MVP_MealFit.member.service;

import java.util.List;
import com.example.MVP_MealFit.global.auth.JwtProvider;
import com.example.MVP_MealFit.global.exception.BusinessException;
import com.example.MVP_MealFit.global.exception.ErrorCode;
import com.example.MVP_MealFit.member.domain.Member;
import com.example.MVP_MealFit.member.domain.NutritionTarget;
import com.example.MVP_MealFit.member.domain.Disease;
import com.example.MVP_MealFit.member.dto.LoginRequest;
import com.example.MVP_MealFit.member.dto.MemberResponse;
import com.example.MVP_MealFit.member.dto.ProfileUpdateRequest;
import com.example.MVP_MealFit.member.dto.SignupRequest;
import com.example.MVP_MealFit.member.dto.TokenResponse;
import com.example.MVP_MealFit.member.repository.MemberRepository;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import lombok.RequiredArgsConstructor;

import java.util.Optional;

@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class MemberService {

    private final MemberRepository memberRepository;
    private final PasswordEncoder passwordEncoder;
    private final JwtProvider jwtProvider;

    @Transactional
    public void updateDiseases(Long memberId, List<Disease> diseases) {
        Member member = getMember(memberId);
        member.updateDiseases(diseases);
    }

    // analysis.ReportService 전용 공개 API — 조회만, Member 엔티티 자체는 노출하지 않음
    public List<Disease> getDiseases(Long memberId) {
        return getMember(memberId).getDiseases();
    }

    public Long signup(SignupRequest req) {
        if (memberRepository.existsByEmail(req.getEmail())) {
            throw new BusinessException(ErrorCode.DUPLICATE_EMAIL);
        }

        String encodedPassword = passwordEncoder.encode(req.getPassword());

        Member member = new Member(
                req.getEmail(),
                encodedPassword,
                req.getNickname(),
                req.getHeight(),
                req.getGender(),
                req.getBirthDate(),
                req.getActivityLevel(),
                req.getGoal()
        );

        return memberRepository.save(member).getId();
    }

    public TokenResponse login(LoginRequest req) {
        Member member = memberRepository.findByEmail(req.getEmail())
                .orElseThrow(() -> new BusinessException(ErrorCode.UNAUTHORIZED));

        if (!passwordEncoder.matches(req.getPassword(), member.getPassword())) {
            throw new BusinessException(ErrorCode.UNAUTHORIZED);
        }

        String accessToken = jwtProvider.createToken(member.getId());

        return new TokenResponse(accessToken, member.getId(), member.getNickname());
    }

    public MemberResponse getProfile(Long memberId) {
        Member member = getMember(memberId);
        return MemberResponse.from(member);
    }

    @Transactional
    public void updateProfile(Long memberId, ProfileUpdateRequest req) {
        Member member = getMember(memberId);
        member.updateProfile(req.getNickname(), req.getHeight(), req.getActivityLevel(), req.getGoal());
    }

    public Member getMember(Long memberId) {
        return memberRepository.findById(memberId)
                .orElseThrow(() -> new BusinessException(ErrorCode.MEMBER_NOT_FOUND));
    }

    @Transactional
    public void saveNutritionTarget(Long memberId, NutritionTarget target) {
        Member member = getMember(memberId);
        member.assignTarget(target);
    }

    public Optional<NutritionTarget> findNutritionTarget(Long memberId) {
        Member member = getMember(memberId);
        return Optional.ofNullable(member.getNutritionTarget());
    }
}