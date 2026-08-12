package com.example.MVP_MealFit.member.controller;

import com.example.MVP_MealFit.global.auth.LoginMember;
import com.example.MVP_MealFit.global.response.ApiResponse;
import com.example.MVP_MealFit.member.dto.LoginRequest;
import com.example.MVP_MealFit.member.dto.MemberResponse;
import com.example.MVP_MealFit.member.dto.ProfileUpdateRequest;
import com.example.MVP_MealFit.member.dto.SignupRequest;
import com.example.MVP_MealFit.member.dto.TokenResponse;
import com.example.MVP_MealFit.member.service.MemberService;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/members")
public class MemberController {

    private final MemberService memberService;

    public MemberController(MemberService memberService) {
        this.memberService = memberService;
    }

    @PostMapping("/signup")
    public ResponseEntity<ApiResponse<Long>> signup(@Valid @RequestBody SignupRequest request) {
        Long memberId = memberService.signup(request);
        return ResponseEntity.status(HttpStatus.CREATED).body(ApiResponse.ok(memberId));
    }

    @PostMapping("/login")
    public ApiResponse<TokenResponse> login(@Valid @RequestBody LoginRequest request) {
        TokenResponse token = memberService.login(request);
        return ApiResponse.ok(token);
    }

    @GetMapping("/me")
    public ApiResponse<MemberResponse> me(@LoginMember Long memberId) {
        MemberResponse response = memberService.getProfile(memberId);
        return ApiResponse.ok(response);
    }

    @PatchMapping("/me")
    public ApiResponse<Void> updateMe(@LoginMember Long memberId,
                                      @Valid @RequestBody ProfileUpdateRequest request) {
        memberService.updateProfile(memberId, request);
        return ApiResponse.ok();
    }
}