package com.example.MVP_MealFit.global.file;

import com.example.MVP_MealFit.global.exception.BusinessException;
import com.example.MVP_MealFit.global.exception.ErrorCode;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.multipart.MultipartFile;

import java.util.Arrays;
import java.util.Set;

@Component
public class FileValidator {

    private final Set<String> allowedExtensions;
    private final long maxSizeBytes;

    public FileValidator(
            @Value("${file.allowed-extensions}") String allowedExtensionsRaw,
            @Value("${file.max-size-bytes}") long maxSizeBytes
    ) {
        this.allowedExtensions = Set.of(allowedExtensionsRaw.split(","));
        this.maxSizeBytes = maxSizeBytes;
    }

    public void validate(MultipartFile file) {
        if (file == null || file.isEmpty()) {
            throw new BusinessException(ErrorCode.FILE_INVALID_TYPE);
        }

        String extension = extractExtension(file.getOriginalFilename());
        if (!allowedExtensions.contains(extension)) {
            throw new BusinessException(ErrorCode.FILE_INVALID_TYPE);
        }

        if (file.getSize() > maxSizeBytes) {
            throw new BusinessException(ErrorCode.FILE_TOO_LARGE);
        }
    }

    private String extractExtension(String filename) {
        if (filename == null || !filename.contains(".")) {
            return "";
        }
        return filename.substring(filename.lastIndexOf('.') + 1).toLowerCase();
    }
}