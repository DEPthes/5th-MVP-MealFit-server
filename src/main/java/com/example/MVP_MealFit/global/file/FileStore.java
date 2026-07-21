package com.example.MVP_MealFit.global.file;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.io.Resource;
import org.springframework.core.io.UrlResource;
import org.springframework.stereotype.Component;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.net.MalformedURLException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.UUID;

@Component
public class FileStore {

    private final Path rootPath;

    public FileStore(@Value("${file.root-path}") String rootPath) {
        this.rootPath = Path.of(rootPath);
    }

    public String store(MultipartFile file, String subDir) {
        try {
            Path dir = rootPath.resolve(subDir);
            Files.createDirectories(dir);

            String extension = extractExtension(file.getOriginalFilename());
            String storedFilename = UUID.randomUUID() + (extension.isEmpty() ? "" : "." + extension);

            Path targetPath = dir.resolve(storedFilename);
            file.transferTo(targetPath);

            return subDir + "/" + storedFilename;
        } catch (IOException e) {
            throw new UncheckedIOException("파일 저장에 실패했습니다.", e);
        }
    }

    public Resource load(String storedPath) {
        try {
            Path filePath = rootPath.resolve(storedPath);
            return new UrlResource(filePath.toUri());
        } catch (MalformedURLException e) {
            throw new IllegalArgumentException("잘못된 파일 경로입니다: " + storedPath, e);
        }
    }

    public void delete(String storedPath) {
        try {
            Path filePath = rootPath.resolve(storedPath);
            Files.deleteIfExists(filePath);
        } catch (IOException e) {
            throw new UncheckedIOException("파일 삭제에 실패했습니다.", e);
        }
    }

    private String extractExtension(String filename) {
        if (filename == null || !filename.contains(".")) {
            return "";
        }
        return filename.substring(filename.lastIndexOf('.') + 1).toLowerCase();
    }
}