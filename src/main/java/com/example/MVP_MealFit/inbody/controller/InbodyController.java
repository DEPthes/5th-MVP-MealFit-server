package com.example.MVP_MealFit.inbody.controller;

import com.example.MVP_MealFit.global.auth.LoginMember;
import com.example.MVP_MealFit.global.response.ApiResponse;
import com.example.MVP_MealFit.inbody.dto.InbodyHistoryResponse;
import com.example.MVP_MealFit.inbody.dto.InbodyResponse;
import com.example.MVP_MealFit.inbody.service.InbodyService;
import jakarta.validation.constraints.NotNull;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.util.List;

@RestController
@RequiredArgsConstructor
@RequestMapping("/api/inbodies")
public class InbodyController {

    private final InbodyService inbodyService;

    // 인바디 결과지 업로드
    @PostMapping(consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    @ResponseStatus(HttpStatus.CREATED)
    public ApiResponse<InbodyResponse> register(
            @LoginMember Long memberId,
            @RequestParam("file") @NotNull MultipartFile file) {

        InbodyResponse response = inbodyService.register(memberId, file);

        return ApiResponse.ok(response);
    }

    // 최신 인바디 조회
    @GetMapping("/latest")
    public ApiResponse<InbodyResponse> findLatest(@LoginMember Long memberId) {
        InbodyResponse response = inbodyService.findLatest(memberId);

        return ApiResponse.ok(response);
    }

    // 인바디 업로드 이력 조회
    @GetMapping
    public ApiResponse<List<InbodyHistoryResponse>> findHistory(@LoginMember Long memberId) {
        List<InbodyHistoryResponse> response = inbodyService.findHistory(memberId);

        return ApiResponse.ok(response);
    }
}
