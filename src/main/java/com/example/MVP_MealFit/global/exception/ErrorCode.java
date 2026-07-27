package com.example.MVP_MealFit.global.exception;

import org.springframework.http.HttpStatus;

public enum ErrorCode {

    INVALID_INPUT(HttpStatus.BAD_REQUEST, "COMMON_001", "입력값이 올바르지 않습니다."),
    UNAUTHORIZED(HttpStatus.UNAUTHORIZED, "COMMON_002", "인증이 필요합니다."),
    FORBIDDEN(HttpStatus.FORBIDDEN, "COMMON_003", "권한이 없습니다."),
    INTERNAL_ERROR(HttpStatus.INTERNAL_SERVER_ERROR, "COMMON_999", "서버 오류가 발생했습니다."),

    DUPLICATE_EMAIL(HttpStatus.CONFLICT, "MEMBER_001", "이미 가입된 이메일입니다."),
    MEMBER_NOT_FOUND(HttpStatus.NOT_FOUND, "MEMBER_002", "존재하지 않는 회원입니다."),

    OCR_FAILED(HttpStatus.BAD_GATEWAY, "OCR_001", "OCR 서버 호출에 실패했습니다."),
    OCR_PARSE_FAILED(HttpStatus.INTERNAL_SERVER_ERROR, "OCR_002", "OCR 응답을 해석할 수 없습니다."),

    INBODY_PARSE_FAILED(HttpStatus.UNPROCESSABLE_ENTITY, "INBODY_001", "인바디 결과에서 필요한 데이터를 추출할 수 없습니다."),
    INBODY_NOT_FOUND(HttpStatus.NOT_FOUND, "INBODY_002", "인바디 정보를 찾을 수 없습니다."),

    FILE_INVALID_TYPE(HttpStatus.BAD_REQUEST, "FILE_001", "허용되지 않는 파일 형식입니다."),
    FILE_TOO_LARGE(HttpStatus.PAYLOAD_TOO_LARGE, "FILE_002", "파일 용량이 너무 큽니다."),

    TARGET_NOT_READY(HttpStatus.NOT_FOUND, "ANALYSIS_001", "목표 영양치가 아직 산출되지 않았습니다.");

    private final HttpStatus status;
    private final String code;
    private final String message;

    ErrorCode(HttpStatus status, String code, String message) {
        this.status = status;
        this.code = code;
        this.message = message;
    }

    public HttpStatus getStatus() { return status; }
    public String getCode() { return code; }
    public String getMessage() { return message; }
}
