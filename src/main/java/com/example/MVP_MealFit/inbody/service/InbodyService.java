package com.example.MVP_MealFit.inbody.service;

import com.example.MVP_MealFit.global.exception.BusinessException;
import com.example.MVP_MealFit.global.exception.ErrorCode;
import com.example.MVP_MealFit.global.file.FileStore;
import com.example.MVP_MealFit.global.file.FileValidator;
import com.example.MVP_MealFit.inbody.domain.Inbody;
import com.example.MVP_MealFit.inbody.dto.InbodyHistoryResponse;
import com.example.MVP_MealFit.inbody.dto.InbodyResponse;
import com.example.MVP_MealFit.inbody.parser.InbodyData;
import com.example.MVP_MealFit.inbody.parser.InbodyParser;
import com.example.MVP_MealFit.inbody.repository.InbodyRepository;
import com.example.MVP_MealFit.member.domain.Member;
import com.example.MVP_MealFit.member.service.MemberService;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.PageRequest;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;

import java.time.LocalDate;
import java.util.List;
import java.util.Optional;

@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class InbodyService {

    private static final String INBODY_DIRECTORY = "inbody";

    private final InbodyRepository inbodyRepository;
    private final MemberService memberService;
    private final FileValidator fileValidator;
    private final FileStore fileStore;
    private final InbodyParser inbodyParser;

    // 인바디 결과지 업로드
    @Transactional
    public InbodyResponse register(Long memberId, MultipartFile file) {

        // 파일 검증
        fileValidator.validate(file);

        // 파일 저장
        String storedPath = fileStore.store(file, INBODY_DIRECTORY);

        try {

            // OCR + 파싱
            InbodyData data = inbodyParser.parse(file);

            // 회원 조회
            Member member = memberService.getMember(memberId);

            // 측정일
            LocalDate measuredAt = data.measuredAt().orElse(LocalDate.now());

            // 엔티티 생성
            Inbody inbody = Inbody.builder()
                    .member(member)
                    .weight(data.weight())
                    .skeletalMuscleMass(data.skeletalMuscleMass())
                    .bodyFatPercentage(data.bodyFatPercentage())
                    .bmr(data.bmr())
                    .measuredAt(measuredAt)
                    .imagePath(storedPath)
                    .originalFilename(file.getOriginalFilename())
                    .fileSize(file.getSize())
                    .build();

            // 저장
            Inbody savedInbody = inbodyRepository.save(inbody);

            return InbodyResponse.from(savedInbody, LocalDate.now());
        } catch (Exception e) {

            // OCR 또는 DB 저장 실패 시 업로드 한 파일 삭제
            fileStore.delete(storedPath);

            throw e;
        }
    }

    // 인바디 이력 조회
    public List<InbodyHistoryResponse> findHistory(Long memberId) {

        memberService.getMember(memberId);

        return inbodyRepository.findHistory(memberId)
                .stream()
                .map(InbodyHistoryResponse::from)
                .toList();
    }

    // Analysis 등 다른 서비스에서 사용하는 내부 메서드
    public Optional<Inbody> findLatestInbody(Long memberId) {
        return inbodyRepository
                .findLatest(memberId, PageRequest.of(0, 1))
                .stream()
                .findFirst();
    }

    // 최신 인바디 조회
    public InbodyResponse findLatest(Long memberId) {
        Inbody latest = findLatestInbody(memberId)
                .orElseThrow(() -> new BusinessException(ErrorCode.INBODY_NOT_FOUND));

        return InbodyResponse.from(latest, LocalDate.now());
    }
}