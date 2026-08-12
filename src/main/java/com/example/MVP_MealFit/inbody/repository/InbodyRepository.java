package com.example.MVP_MealFit.inbody.repository;

import com.example.MVP_MealFit.inbody.domain.Inbody;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.List;
import java.util.Optional;

public interface InbodyRepository extends JpaRepository<Inbody, Long> {
    /**
     *  특정 회원의 가장 최근 인바디 기록을 조회
     *  measuredAt 기준 내림차순 정렬 후 Pageable(PageRequest.of(0, 1))을 통해 1건만 조회
     */
    @Query("""
        SELECT i
        FROM Inbody i
        WHERE i.member.id = :memberId
        ORDER BY i.measuredAt DESC, i.id DESC
        """)
    List<Inbody> findLatest(@Param("memberId") Long memberId, Pageable pageable);

    /**
     *  특정 회원의 전체 인바디 기록을 최신순으로 조회
     */
    @Query("""
        SELECT i
        FROM Inbody i
        WHERE i.member.id = :memberId
        ORDER BY i.measuredAt DESC, i.id DESC
        """)
    List<Inbody> findHistory(@Param("memberId") Long memberId);
}
