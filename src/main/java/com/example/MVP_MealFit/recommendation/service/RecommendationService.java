package com.example.MVP_MealFit.recommendation.service;

import com.example.MVP_MealFit.global.vo.Nutrition;
import com.example.MVP_MealFit.member.domain.Disease;
import com.example.MVP_MealFit.member.domain.NutritionTarget;
import com.example.MVP_MealFit.member.service.MemberService;
import com.example.MVP_MealFit.recommendation.domain.MatchReason;
import com.example.MVP_MealFit.recommendation.domain.NutritionFilter;
import com.example.MVP_MealFit.recommendation.domain.ReferencePoint;
import com.example.MVP_MealFit.recommendation.dto.RecommendationCondition;
import com.example.MVP_MealFit.recommendation.dto.RecommendationResponse;
import com.example.MVP_MealFit.recommendation.dto.RecommendedMenuResponse;
import com.example.MVP_MealFit.restaurant.domain.FoodType;
import com.example.MVP_MealFit.restaurant.domain.Menu;
import com.example.MVP_MealFit.restaurant.domain.OfficialFood;
import com.example.MVP_MealFit.restaurant.domain.Restaurant;
import com.example.MVP_MealFit.restaurant.dto.MenuSearchResponse;
import com.example.MVP_MealFit.restaurant.dto.RestaurantResponse;
import com.example.MVP_MealFit.restaurant.repository.MenuRepository;
import com.example.MVP_MealFit.restaurant.service.SynonymResolver;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageImpl;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.Arrays;
import java.util.Comparator;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Optional;
import java.util.stream.Collectors;

/**
 * 식당 단위 검색 + 추천 (홈·검색 겸용). GET /api/recommendations 하나가 이 서비스를 쓴다.
 * <p>
 * 쿼리 1회로 조건에 맞는 메뉴를 전부 가져온 뒤, 등급(matchReason)·매칭률(matchRate)·
 * 정렬·페이징을 전부 메모리에서 처리한다 — 매칭률이 DB에 없는 계산값이라 DB 정렬이
 * 불가능하기 때문이다. 메뉴 1027건·식당 102건 규모에서만 성립하는 전제다. 데이터가
 * 수만 건이 되면 매칭률을 미리 계산해 저장하거나 후보를 제한하는 방식으로 재설계해야 한다.
 */
@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class RecommendationService {

    // 검색어 단어 개수 상한. MenuRepositoryImpl과 같은 값이어야 한다.
    private static final int MAX_KEYWORD_TOKENS = 5;

    // 대표식품명 확장에만 적용하는 신뢰도 하한. MenuRepositoryImpl.MIN_MATCH_CONFIDENCE와
    // 같은 값이어야 한다 — 쿼리가 이미 이 기준으로 걸러왔으므로, 여기서는 matchReason
    // 표시용으로 같은 판정을 재확인한다.
    private static final BigDecimal MIN_MATCH_CONFIDENCE = BigDecimal.valueOf(0.85);

    // FR-012 보행 속도. 명세에 수치가 없어 약 4.5km/h(분당 75m)로 둔다 — UI 시안의
    // 네 값(150m→2분, 300m→4분, 340m→5분, 90m→1분)이 전부 이 계수와 일치한다.
    private static final double WALK_METERS_PER_MINUTE = 75;

    private final MenuRepository menuRepository;
    private final SynonymResolver synonymResolver;
    private final MemberService memberService;
    private final MatchScorer matchScorer;
    private final DiseaseFilter diseaseFilter;

    public Page<RecommendationResponse> search(Long memberId, RecommendationCondition cond, Pageable pageable) {
        List<String> tokens = tokenize(cond.getKeyword());
        FoodType selectedFoodType = cond.getFoodType();

        // 칩으로 이미 세부 종류를 골랐으면 동의어 해석을 하지 않는다 — 사용자가 직접
        // 고른 필터가 우선이다.
        FoodType derivedFoodType = null;
        if (selectedFoodType == null && !tokens.isEmpty()) {
            derivedFoodType = synonymResolver.resolve(cond.getKeyword()).orElse(null);
        }

        List<Menu> menus = menuRepository.findForRecommendation(
                cond.getCuisine(), selectedFoodType, derivedFoodType, tokens);

        NutritionFilter nutritionFilter = cond.getNutritionFilter();
        if (nutritionFilter != null) {
            menus = menus.stream()
                    .filter(m -> nutritionFilter.matches(m.getNutrition()))
                    .toList();
        }

        // FR-010 가격대 필터. 가격 정보가 없는 메뉴는 조건을 만족했는지 알 수 없으므로 제외한다.
        Integer maxPrice = cond.getMaxPrice();
        if (maxPrice != null) {
            menus = menus.stream()
                    .filter(m -> m.getPrice() != null && m.getPrice() <= maxPrice)
                    .toList();
        }

        // FR-012 거리 계산 기준점. 안 보내면 정문(정류장) 기준.
        ReferencePoint referencePoint = cond.getReferencePoint() != null
                ? cond.getReferencePoint() : ReferencePoint.MAIN_GATE;

        // 목표치가 없으면 matchRate·proteinTargetPercent는 전부 null로 폴백한다.
        // POST /api/targets를 한 번도 호출하지 않은 회원도 검색은 정상 동작해야 한다.
        Optional<NutritionTarget> nutritionTarget = memberService.findNutritionTarget(memberId);
        Nutrition perMealTarget = nutritionTarget.map(NutritionTarget::perMeal).orElse(null);
        BigDecimal dailyProteinTarget = nutritionTarget
                .map(t -> t.getTarget().getProtein())
                .orElse(null);
        List<Disease> diseases = memberService.getDiseases(memberId);

        FoodType effectiveDerivedFoodType = derivedFoodType;
        List<ScoredMenu> scoredMenus = menus.stream()
                .map(m -> score(m, tokens, effectiveDerivedFoodType, perMealTarget, dailyProteinTarget, diseases))
                .toList();

        Map<Long, List<ScoredMenu>> byRestaurant = scoredMenus.stream()
                .collect(Collectors.groupingBy(s -> s.menu().getRestaurant().getId()));

        Comparator<ScoredMenu> menuOrder = Comparator
                .<ScoredMenu, Integer>comparing(s -> s.matchReason().ordinal())
                .thenComparing(ScoredMenu::matchRate, Comparator.nullsLast(Comparator.reverseOrder()))
                .thenComparing(s -> s.menu().getName());

        List<RecommendationResponse> cards = byRestaurant.values().stream()
                .map(group -> toCard(group, menuOrder, referencePoint))
                .sorted(cardOrder())
                .toList();

        return paginate(cards, pageable);
    }

    private RecommendationResponse toCard(
            List<ScoredMenu> group, Comparator<ScoredMenu> menuOrder, ReferencePoint referencePoint
    ) {
        List<ScoredMenu> sorted = group.stream().sorted(menuOrder).toList();
        ScoredMenu top = sorted.get(0);
        Restaurant restaurant = top.menu().getRestaurant();

        Integer distanceMeters = referencePoint.distanceMetersTo(restaurant);

        return RecommendationResponse.builder()
                .restaurant(RestaurantResponse.from(restaurant))
                .menus(sorted.stream().map(this::toMenuResponse).toList())
                .matchedMenuCount(sorted.size())
                .matchReason(top.matchReason())
                .topMatchRate(top.matchRate())
                .distanceMeters(distanceMeters)
                .walkingMinutes(distanceMeters == null ? null : walkingMinutes(distanceMeters))
                .distanceBasis(referencePoint.getDisplayName())
                .build();
    }

    // 도보 소요 시간(분), 최소 1분
    private int walkingMinutes(int distanceMeters) {
        return Math.max(1, (int) Math.round(distanceMeters / WALK_METERS_PER_MINUTE));
    }

    private Comparator<RecommendationResponse> cardOrder() {
        return Comparator
                .<RecommendationResponse, Integer>comparing(r -> r.getMatchReason().ordinal())
                .thenComparing(RecommendationResponse::getTopMatchRate, Comparator.nullsLast(Comparator.reverseOrder()))
                .thenComparing(r -> r.getRestaurant().getName());
    }

    private RecommendedMenuResponse toMenuResponse(ScoredMenu s) {
        return RecommendedMenuResponse.builder()
                .menu(MenuSearchResponse.from(s.menu()))
                .matchRate(s.matchRate())
                .proteinTargetPercent(s.proteinTargetPercent())
                .warnings(s.warnings())
                .build();
    }

    private ScoredMenu score(
            Menu menu, List<String> tokens, FoodType derivedFoodType,
            Nutrition perMealTarget, BigDecimal dailyProteinTarget, List<Disease> diseases
    ) {
        MatchReason matchReason = determineMatchReason(menu, tokens, derivedFoodType);
        Double matchRate = matchScorer.score(perMealTarget, menu.getNutrition());
        Integer proteinTargetPercent = proteinTargetPercent(menu.getNutrition(), dailyProteinTarget);
        List<String> warnings = diseaseFilter.warningsFor(diseases, menu.getNutrition());
        return new ScoredMenu(menu, matchReason, matchRate, proteinTargetPercent, warnings);
    }

    // 검색 결과에 이 메뉴가 걸린 이유를 우선순위(메뉴명 > 식당명 > 대표식품명 > 태그) 순으로 판정한다.
    // MenuRepositoryImpl의 쿼리 조건과 동일한 로직이어야 한다 — 쿼리가 반환한 메뉴는
    // 반드시 이 중 하나에 해당한다.
    private MatchReason determineMatchReason(Menu menu, List<String> tokens, FoodType derivedFoodType) {
        if (tokens.isEmpty()) {
            // 홈 화면(검색어 없음) — 관련도가 모두 같아 정렬은 matchRate에만 의존한다.
            return MatchReason.FOOD_TYPE_TAG;
        }
        if (containsAllTokens(menu.getNormalizedName(), tokens) || containsAllTokens(menu.getName(), tokens)) {
            return MatchReason.MENU_NAME;
        }
        if (containsAllTokens(menu.getRestaurant().getName(), tokens)) {
            return MatchReason.RESTAURANT_NAME;
        }

        OfficialFood officialFood = menu.getOfficialFood();
        Nutrition nutrition = menu.getNutrition();
        boolean confidenceOk = nutrition != null && nutrition.getConfidence() != null
                && nutrition.getConfidence().compareTo(MIN_MATCH_CONFIDENCE) >= 0;
        if (officialFood != null && confidenceOk
                && containsAllTokens(officialFood.getRepresentativeName(), tokens)) {
            return MatchReason.REPRESENTATIVE_FOOD;
        }

        // 위 셋에 해당하지 않으면 derivedFoodType(동의어 유추) 태그 매칭뿐이다 —
        // 쿼리 WHERE의 OR 조건 중 이것만 남는다.
        return MatchReason.FOOD_TYPE_TAG;
    }

    private boolean containsAllTokens(String field, List<String> tokens) {
        if (field == null) {
            return false;
        }
        String normalized = field.toLowerCase(Locale.ROOT).replace(" ", "");
        return tokens.stream().allMatch(normalized::contains);
    }

    private List<String> tokenize(String keyword) {
        if (keyword == null || keyword.isBlank()) {
            return List.of();
        }
        String normalized = keyword.trim().toLowerCase(Locale.ROOT);
        return Arrays.stream(normalized.split("\\s+"))
                .filter(t -> !t.isBlank())
                .limit(MAX_KEYWORD_TOKENS)
                .toList();
    }

    // "하루 목표(109g)의 26% 충족" 자리. 일일 목표 대비 이 메뉴의 단백질 비율.
    private Integer proteinTargetPercent(Nutrition menuNutrition, BigDecimal dailyProteinTarget) {
        if (menuNutrition == null || menuNutrition.getProtein() == null
                || dailyProteinTarget == null || dailyProteinTarget.compareTo(BigDecimal.ZERO) <= 0) {
            return null;
        }
        BigDecimal percent = menuNutrition.getProtein()
                .divide(dailyProteinTarget, 4, RoundingMode.HALF_UP)
                .multiply(BigDecimal.valueOf(100));
        return percent.setScale(0, RoundingMode.HALF_UP).intValue();
    }

    private Page<RecommendationResponse> paginate(List<RecommendationResponse> all, Pageable pageable) {
        int start = (int) pageable.getOffset();
        if (start >= all.size()) {
            return new PageImpl<>(List.of(), pageable, all.size());
        }
        int end = Math.min(start + pageable.getPageSize(), all.size());
        return new PageImpl<>(all.subList(start, end), pageable, all.size());
    }

    private record ScoredMenu(
            Menu menu,
            MatchReason matchReason,
            Double matchRate,
            Integer proteinTargetPercent,
            List<String> warnings
    ) {
    }
}
