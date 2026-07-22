package com.example.MVP_MealFit.global.exception;

import com.example.MVP_MealFit.global.response.ApiResponse;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.FieldError;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

@RestControllerAdvice
public class GlobalExceptionHandler {

    // 우리가 직접 던진 비즈니스 예외 (DUPLICATE_EMAIL 등)
    @ExceptionHandler(BusinessException.class)
    public ResponseEntity<ApiResponse<Void>> handleBusinessException(BusinessException e) {
        ErrorCode errorCode = e.getErrorCode();
        return ResponseEntity
                .status(errorCode.getStatus())
                .body(ApiResponse.fail(errorCode));
    }

    // @Valid 검증 실패 (SignupRequest 등에서 @NotBlank 위반 시)
    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<ApiResponse<Void>> handleValidationException(MethodArgumentNotValidException e) {
        FieldError fieldError = e.getBindingResult().getFieldError();
        String detailMessage = (fieldError != null)
                ? fieldError.getField() + ": " + fieldError.getDefaultMessage()
                : ErrorCode.INVALID_INPUT.getMessage();

        ApiResponse<Void> response = ApiResponse.fail(ErrorCode.INVALID_INPUT);
        // 필드별 상세 메시지를 넣고 싶으면 ApiResponse에 필드 하나 추가해도 되지만,
        // 지금은 단순하게 ErrorCode 메시지만 반환
        return ResponseEntity
                .status(ErrorCode.INVALID_INPUT.getStatus())
                .body(response);
    }

    // 예상 못한 모든 예외 (마지막 안전망)
    @ExceptionHandler(Exception.class)
    public ResponseEntity<ApiResponse<Void>> handleUnknownException(Exception e) {
        return ResponseEntity
                .status(ErrorCode.INTERNAL_ERROR.getStatus())
                .body(ApiResponse.fail(ErrorCode.INTERNAL_ERROR));
    }
}
