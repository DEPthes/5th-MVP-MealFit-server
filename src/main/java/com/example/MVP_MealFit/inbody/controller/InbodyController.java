package com.example.MVP_MealFit.inbody.controller;

import com.example.MVP_MealFit.global.auth.LoginMember;
import com.example.MVP_MealFit.global.response.ApiResponse;
import com.example.MVP_MealFit.inbody.dto.InbodyHistoryResponse;
import com.example.MVP_MealFit.inbody.dto.InbodyResponse;
import com.example.MVP_MealFit.inbody.service.InbodyService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.responses.ApiResponses;
import io.swagger.v3.oas.annotations.tags.Tag;
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
@Tag(name = "Inbody", description = "인바디 API")
public class InbodyController {

    private final InbodyService inbodyService;

    // 인바디 결과지 업로드
    @PostMapping(consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    @ResponseStatus(HttpStatus.CREATED)
    @Operation(
            summary = "인바디 결과지 업로드",
            description = "인바디 결과지 파일을 업로드하고 OCR 및 파싱을 통해 인바디 데이터를 저장합니다."
    )
    @ApiResponses({
            @io.swagger.v3.oas.annotations.responses.ApiResponse(
                    responseCode = "201",
                    description = "인바디 결과지 업로드 및 저장 성공"
            ),
            @io.swagger.v3.oas.annotations.responses.ApiResponse(
                    responseCode = "400",
                    description = "허용되지 않는 파일 형식입니다."
            ),
            @io.swagger.v3.oas.annotations.responses.ApiResponse(
                    responseCode = "401",
                    description = "인증이 필요합니다."
            ),
            @io.swagger.v3.oas.annotations.responses.ApiResponse(
                    responseCode = "404",
                    description = "존재하지 않는 회원입니다."
            ),
            @io.swagger.v3.oas.annotations.responses.ApiResponse(
                    responseCode = "413",
                    description = "파일 용량이 너무 큽니다."
            ),
            @io.swagger.v3.oas.annotations.responses.ApiResponse(
                    responseCode = "422",
                    description = "인바디 결과에서 필요한 데이터를 추출할 수 없습니다."
            ),
            @io.swagger.v3.oas.annotations.responses.ApiResponse(
                    responseCode = "502",
                    description = "OCR 서버 호출에 실패했습니다."
            ),
            @io.swagger.v3.oas.annotations.responses.ApiResponse(
                    responseCode = "500",
                    description = "OCR 응답을 해석할 수 없거나 서버 오류가 발생했습니다."
            )
    })
    public ApiResponse<InbodyResponse> register(
            @Parameter(hidden = true)
            @LoginMember Long memberId,

            @Parameter(
                    description = "인바디 결과지 파일",
                    required = true
            )
            @RequestParam("file")
            @NotNull MultipartFile file) {

        InbodyResponse response = inbodyService.register(memberId, file);

        return ApiResponse.ok(response);
    }

    // 최신 인바디 조회
    @GetMapping("/latest")
    @Operation(
            summary = "최신 인바디 조회",
            description = "로그인한 회원의 가장 최근 인바디 정보를 조회합니다."
    )
    @ApiResponses({
            @io.swagger.v3.oas.annotations.responses.ApiResponse(
                    responseCode = "200",
                    description = "최신 인바디 조회 성공"
            ),
            @io.swagger.v3.oas.annotations.responses.ApiResponse(
                    responseCode = "401",
                    description = "인증이 필요합니다."
            ),
            @io.swagger.v3.oas.annotations.responses.ApiResponse(
                    responseCode = "404",
                    description = "인바디 정보를 찾을 수 없습니다."
            )
    })
    public ApiResponse<InbodyResponse> findLatest(@Parameter(hidden = true)
                                                      @LoginMember Long memberId) {
        InbodyResponse response = inbodyService.findLatest(memberId);

        return ApiResponse.ok(response);
    }

    // 인바디 업로드 이력 조회
    @GetMapping
    @Operation(
            summary = "인바디 업로드 이력 조회",
            description = "로그인한 회원의 인바디 업로드 이력을 조회합니다."
    )
    @ApiResponses({
            @io.swagger.v3.oas.annotations.responses.ApiResponse(
                    responseCode = "200",
                    description = "인바디 업로드 이력 조회 성공"
            ),
            @io.swagger.v3.oas.annotations.responses.ApiResponse(
                    responseCode = "401",
                    description = "인증이 필요합니다."
            ),
            @io.swagger.v3.oas.annotations.responses.ApiResponse(
                    responseCode = "404",
                    description = "존재하지 않는 회원입니다."
            )
    })
    public ApiResponse<List<InbodyHistoryResponse>> findHistory(@Parameter(hidden = true)
                                                                    @LoginMember Long memberId) {
        List<InbodyHistoryResponse> response = inbodyService.findHistory(memberId);

        return ApiResponse.ok(response);
    }
}
