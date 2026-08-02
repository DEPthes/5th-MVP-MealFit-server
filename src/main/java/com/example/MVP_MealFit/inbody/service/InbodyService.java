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
import com.example.MVP_MealFit.analysis.service.TargetCalculator;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.PageRequest;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Optional;
import java.util.stream.Collectors;

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
    private final TargetCalculator targetCalculator;
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

            // 업로드일
            LocalDate uploadedAt = LocalDate.now();

            // 측정일
            LocalDate measuredAt = data.measuredAt().orElse(uploadedAt);

            // 업로드 시점의 목표 단백질 계산 (분석 히스토리용)
            BigDecimal proteinTarget = targetCalculator
                    .calculate(data.bmr(), member.getActivityLevel(), member.getGoal())
                    .getProtein();


            // 엔티티 생성
            Inbody inbody = Inbody.builder()
                    .member(member)
                    .weight(data.weight())
                    .skeletalMuscleMass(data.skeletalMuscleMass())
                    .bodyFatPercentage(data.bodyFatPercentage())
                    .bmr(data.bmr())
                    .visceralFatLevel(data.visceralFatLevel())
                    .inbodyScore(data.inbodyScore())
                    .measuredAt(measuredAt)
                    .uploadedAt(uploadedAt)
                    .imagePath(storedPath)
                    .originalFilename(file.getOriginalFilename())
                    .fileSize(file.getSize())
                    .proteinTarget(proteinTarget)
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

    // Analysis 전용 인바디 조회
    // 같은 측정일(measuredAt)은 가장 마지막에 업로드 한(id가 가장 큰) 기록만 반환
    public List<InbodyHistoryResponse> findAnalysisHistory(Long memberId) {

        memberService.getMember(memberId);

        return inbodyRepository.findHistory(memberId)
                .stream()
                // measuredAt 기준으로 중복 제거 (findHistory가 id DESC 정렬되어 있으므로 첫 번째가 최신 업로드)
                .collect(Collectors.toMap(
                        Inbody::getMeasuredAt,
                        inbody -> inbody,
                        (first, second) -> first,
                        LinkedHashMap::new
                ))
                .values()
                .stream()
                .map(InbodyHistoryResponse::from)
                .toList();
    }
}