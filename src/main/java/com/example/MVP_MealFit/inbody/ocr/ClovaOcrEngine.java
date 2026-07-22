package com.example.MVP_MealFit.inbody.ocr;

import com.example.MVP_MealFit.global.exception.BusinessException;
import com.example.MVP_MealFit.global.exception.ErrorCode;
import lombok.RequiredArgsConstructor;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;
import org.springframework.web.client.RestClient;
import org.springframework.web.multipart.MultipartFile;
import tools.jackson.databind.ObjectMapper;

import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

@Component
@RequiredArgsConstructor
public class ClovaOcrEngine {

    private final RestClient restClient;
    private final ObjectMapper objectMapper;
    private final ClovaOcrProperties properties;

    // CLOVA OCR API를 호출하여 업로드한 인바디 결과지를 OCR 텍스트로 반환
    public ClovaOcrResponse execute(MultipartFile file) {

        try {

            // multipart/form-data 형식의 요청 본문 생성
            MultiValueMap<String, Object> requestBody = new LinkedMultiValueMap<>();

            // CLOVA OCR에서 요구하는 message(JSON) 생성
            Map<String, Object> message = new HashMap<>();

            // OCR API 요청에 필요한 기본 정보 설정
            message.put("version", "V2");                           // 사용할 OCR API 버전
            message.put("requestId", UUID.randomUUID().toString()); // 요청을 구분하기 위한 고유 ID
            message.put("timestamp", System.currentTimeMillis());   // 요청을 보낸 시간

            // OCR 대상으로 업로드 한 파일 정보 추가
            message.put("images",
                    List.of(
                            Map.of(
                                    "format", getExtension(file),
                                    "name", "inbody"
                            )
                    )
            );

            // message 객체를 JSON 문자열로 변환하여 요청에 포함
            requestBody.add(
                    "message",
                    objectMapper.writeValueAsString(message)
            );

            // 업로드 파일
            requestBody.add(
                    "file",
                    new ByteArrayResource(file.getBytes()) {
                        @Override
                        public String getFilename() {
                            return file.getOriginalFilename();
                        }
                    }
            );

            // CLOVA OCR API 호출
            String response = restClient.post()
                    .uri(properties.getInvokeUrl())
                    .header("X-OCR-SECRET", properties.getSecretKey())
                    .contentType(MediaType.MULTIPART_FORM_DATA)
                    .body(requestBody)
                    .retrieve()
                    .body(String.class);

            // OCR 응답(JSON)을 Response DTO로 변환
            return objectMapper.readValue(response, ClovaOcrResponse.class);
        } catch (Exception e) {
            throw new BusinessException(ErrorCode.OCR_FAILED);
        }
    }

    // 업로드 한 파일의 확장자를 반환한다.
    private String getExtension(MultipartFile file) {
        String filename = file.getOriginalFilename();

        if (filename == null || !filename.contains(".")) {
            throw new BusinessException(ErrorCode.FILE_INVALID_TYPE);
        }

        return filename.substring(filename.lastIndexOf(".") + 1);
    }
}
