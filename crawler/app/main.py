"""CLI 진입점.

수동 실행 진입점. 소스·지역을 인자로 받아 크롤 → (8번 시트, 아직 미구현)
파이프라인 호출 순서로 이어진다. 초기에는 사람이 직접 실행한다.

사용 예:
    python -m app.main crawl --source naver --area 강남역 --max-count 30
    python -m app.main crawl --source naver --area 강남역 --keyword 샐러드 \\
        --max-count 3 --headed --delay 2.0 --out out.json
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import json
import logging
import sys
from pathlib import Path

from app.crawler.factory import CrawlerFactory
from app.model.raw import CrawlTarget, RawMenu, RawRestaurant

#: 결과 저장 폴더. 8번 파이프라인(DB 적재)이 아직 없어, 그때까지는 크롤
#: 결과를 눈으로 확인·재사용할 수 있도록 임시로 여기에 JSON을 쌓아둔다.
#: 8번 착수 시 이 저장 로직은 CrawlPipeline.run() 호출로 대체된다.
DEFAULT_OUT_DIR = Path("crawl_results")

#: 실행 로그 폴더. 명령별로 타임스탬프 파일을 남긴다 (콘솔 출력과 별개로,
#: 나중에 스크롤 없이 실패 사유를 그대로 확인·공유할 수 있도록).
LOG_DIR = Path("logs")

logger = logging.getLogger(__name__)


def _configure_logging(command: str) -> Path:
    """콘솔 + 파일에 동시에 로그를 남기도록 구성하고, 로그 파일 경로를 반환한다."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = LOG_DIR / f"{timestamp}_{command}.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_path, encoding="utf-8"),
        ],
    )
    return log_path


def build_arg_parser() -> argparse.ArgumentParser:
    """CLI 인자 파서를 구성한다."""
    parser = argparse.ArgumentParser(
        prog="python -m app.main",
        description="MealFit 식당/메뉴 크롤러 CLI",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    crawl_parser = subparsers.add_parser("crawl", help="식당·메뉴 수집 실행")
    crawl_parser.add_argument(
        "--source", required=True, help="수집 소스 식별자 (예: naver)"
    )
    crawl_parser.add_argument("--area", required=True, help="지역 키워드 (예: 강남역)")
    crawl_parser.add_argument("--keyword", default=None, help="추가 검색어 (선택)")
    crawl_parser.add_argument(
        "--max-count", type=int, default=50, dest="max_count", help="수집 상한 (기본 50)"
    )
    crawl_parser.add_argument(
        "--headed",
        action="store_true",
        help="브라우저 창을 띄워 실행한다 (기본은 headless=True, 셀렉터 디버깅용)",
    )
    crawl_parser.add_argument(
        "--delay", type=float, default=1.0, help="요청 간 지연(초). 기본 1.0"
    )
    crawl_parser.add_argument(
        "--out",
        default=None,
        help=(
            "결과를 저장할 JSON 파일 경로. 생략하면 "
            f"{DEFAULT_OUT_DIR}/<source>_<area>_<시각>.json 으로 자동 저장된다."
        ),
    )

    load_parser = subparsers.add_parser("load", help="크롤 결과 JSON을 DB에 적재 (8번 파이프라인)")
    load_parser.add_argument("--input", required=True, help="적재할 crawl_results JSON 파일 경로")
    load_parser.add_argument(
        "--dry-run",
        action="store_true",
        dest="dry_run",
        help="DB에 쓰지 않고 정규화·집계 리포트만 출력한다",
    )

    load_official_food_parser = subparsers.add_parser(
        "load-official-food", help="식약처 음식DB(xlsx)를 official_food 테이블에 적재"
    )
    load_official_food_parser.add_argument(
        "--input", required=True, help="식약처 음식DB xlsx 파일 경로"
    )

    match_parser = subparsers.add_parser(
        "match", help="menu ↔ official_food 매칭 캐스케이드 실행 (Step 3~5)"
    )
    match_parser.add_argument(
        "--apply",
        action="store_true",
        help="매칭 결과를 menu 테이블에 실제로 반영한다 (생략하면 집계만 출력)",
    )
    match_parser.add_argument(
        "--sample",
        type=int,
        default=20,
        help="방법별 매칭 예시·미매칭 예시를 몇 건씩 보여줄지 (기본 20)",
    )
    match_parser.add_argument(
        "--exclude-franchise",
        action="store_true",
        dest="exclude_franchise",
        help=(
            "data/excluded_brands.csv의 브랜드가 이름에 들어간 식당의 메뉴를 "
            "집계에서 통째로 뺀다 (분석용 — 매칭률 숫자가 달라지므로 주의)"
        ),
    )
    match_parser.add_argument(
        "--exclude-cafe",
        action="store_true",
        dest="exclude_cafe",
        help=(
            "cuisine=CAFE_DESSERT인 식당의 메뉴를 집계에서 통째로 뺀다 "
            "(음료는 official_food 범위 밖이라 구조적으로 매칭 불가 — 분석용)"
        ),
    )
    match_parser.add_argument(
        "--exclude-branch",
        action="store_true",
        dest="exclude_branch",
        help=(
            "이름이 '~점'으로 끝나는 식당(프랜차이즈 지점)의 메뉴를 통째로 뺀다. "
            "제외된 식당 목록은 로그에 남는다"
        ),
    )

    export_labels_parser = subparsers.add_parser(
        "export-labels",
        help="미매칭 메뉴 표본을 정답 라벨링용 CSV로 내보낸다 (LLM 검증셋 제작)",
    )
    export_labels_parser.add_argument(
        "--output", default="labeling/unmatched_sample.csv", help="저장할 CSV 경로"
    )
    export_labels_parser.add_argument(
        "--sample", type=int, default=50, dest="sample", help="라벨링할 표본 수 (기본 50)"
    )
    export_labels_parser.add_argument(
        "--candidates",
        type=int,
        default=10,
        help="메뉴 1건당 보여줄 후보 수 (기본 10)",
    )
    export_labels_parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="표본 추출 난수 seed. 같은 값이면 항상 같은 표본이 나온다 (기본 42)",
    )
    export_labels_parser.add_argument(
        "--exclude-franchise", action="store_true", dest="exclude_franchise",
        help="프랜차이즈 매장 메뉴를 표본에서 제외",
    )
    export_labels_parser.add_argument(
        "--exclude-cafe", action="store_true", dest="exclude_cafe",
        help="카페(CAFE_DESSERT) 메뉴를 표본에서 제외",
    )
    export_labels_parser.add_argument(
        "--exclude-branch", action="store_true", dest="exclude_branch",
        help="'~점'으로 끝나는 식당(프랜차이즈 지점)의 메뉴를 표본에서 제외",
    )
    export_labels_parser.add_argument(
        "--fresh",
        action="store_true",
        help=(
            "기존 파일의 라벨을 이어받지 않고 '정답' 칸을 전부 비운 채로 만든다 "
            "(기본은 이어받기. 어느 쪽이든 덮어쓰기 전 사본은 남는다)"
        ),
    )

    export_branches_parser = subparsers.add_parser(
        "export-branches",
        help="이름이 '~점'으로 끝나는 식당을 프랜차이즈 검토용 CSV로 내보낸다",
    )
    export_branches_parser.add_argument(
        "--output", default="labeling/branch_restaurants.csv", help="저장할 CSV 경로"
    )

    find_food_parser = subparsers.add_parser(
        "find-food", help="official_food를 이름 부분일치로 조회 (라벨링 보조)"
    )
    find_food_parser.add_argument("--keyword", required=True, help="검색할 키워드")
    find_food_parser.add_argument(
        "--limit", type=int, default=30, help="최대 출력 건수 (기본 30)"
    )

    llm_match_parser = subparsers.add_parser(
        "llm-match",
        help="규칙 캐스케이드가 못 잡은 메뉴를 LLM에게 객관식으로 물어본다 (Phase 3)",
    )
    llm_match_parser.add_argument(
        "--apply",
        action="store_true",
        help="LLM 매칭 결과를 menu 테이블에 실제로 반영한다 (생략하면 집계만)",
    )
    llm_match_parser.add_argument(
        "--provider",
        default=None,
        help=(
            "LLM 제공자 (ollama | gemini | fake). "
            "생략하면 설정값(MEALFIT_LLM_PROVIDER, 기본 ollama)"
        ),
    )
    llm_match_parser.add_argument(
        "--model",
        default=None,
        help="모델명. 생략하면 MEALFIT_OLLAMA_MODEL(로컬) 또는 MEALFIT_GEMINI_MODEL(클라우드)",
    )
    llm_match_parser.add_argument(
        "--candidates", type=int, default=10, help="메뉴 1건당 보여줄 후보 수 (기본 10)"
    )
    llm_match_parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help=(
            "물어볼 메뉴 이름 수 상한. 0이면 전체 (기본 0). "
            "처음 붙일 때 몇 건만 돌려 답 품질을 눈으로 확인하는 용도"
        ),
    )
    llm_match_parser.add_argument(
        "--batch",
        type=int,
        default=None,
        help=(
            "한 번의 호출에 담을 메뉴 수. 생략하면 설정값(MEALFIT_LLM_BATCH_SIZE, 기본 20). "
            "클수록 호출 수가 줄지만 한 번 실패할 때 날아가는 양도 커진다"
        ),
    )
    llm_match_parser.add_argument(
        "--rpm",
        type=int,
        default=None,
        help=(
            "분당 호출 상한. 생략하면 설정값(MEALFIT_LLM_REQUESTS_PER_MINUTE, 기본 5). "
            "429(쿼터 초과)가 뜨면 낮춘다"
        ),
    )
    llm_match_parser.add_argument(
        "--refresh",
        action="store_true",
        help="menu_alias에 남은 이전 판정을 무시하고 전부 다시 물어본다 (프롬프트를 고쳤을 때)",
    )
    llm_match_parser.add_argument(
        "--sample", type=int, default=20, help="매칭·기권 예시 출력 개수 (기본 20)"
    )
    llm_match_parser.add_argument(
        "--exclude-franchise", action="store_true", dest="exclude_franchise",
        help="프랜차이즈 매장 메뉴를 대상에서 제외",
    )
    llm_match_parser.add_argument(
        "--exclude-cafe", action="store_true", dest="exclude_cafe",
        help="카페(CAFE_DESSERT) 메뉴를 대상에서 제외",
    )
    llm_match_parser.add_argument(
        "--exclude-branch", action="store_true", dest="exclude_branch",
        help="'~점'으로 끝나는 식당의 메뉴를 대상에서 제외",
    )

    llm_validate_parser = subparsers.add_parser(
        "llm-validate",
        help="사람이 라벨링한 CSV로 LLM 판정을 채점한다 (DB를 쓰지 않는다)",
    )
    llm_validate_parser.add_argument(
        "--input", default="labeling/unmatched_sample.csv", help="채점할 라벨링 CSV 경로"
    )
    llm_validate_parser.add_argument(
        "--provider", default=None, help="LLM 제공자 (ollama | gemini | fake)"
    )
    llm_validate_parser.add_argument("--model", default=None, help="모델명")
    llm_validate_parser.add_argument(
        "--candidates", type=int, default=10, help="후보 개수 (export-labels와 동일해야 함, 기본 10)"
    )
    llm_validate_parser.add_argument(
        "--batch", type=int, default=None, help="한 번의 호출에 담을 메뉴 수 (기본 20)"
    )
    llm_validate_parser.add_argument(
        "--rpm", type=int, default=None, help="분당 호출 상한 (기본 5)"
    )

    llm_models_parser = subparsers.add_parser(
        "llm-models",
        help="지금 쓸 수 있는 LLM 모델 목록을 조회한다 (로컬은 받아둔 모델, 클라우드는 호출 가능한 모델)",
    )
    llm_models_parser.add_argument(
        "--provider", default=None, help="LLM 제공자 (ollama | gemini)"
    )

    tag_parser = subparsers.add_parser(
        "tag", help="메뉴에 FoodType을 붙인다 — 검색의 전제조건 (Phase 4)"
    )
    tag_parser.add_argument(
        "--apply",
        action="store_true",
        help="menu_food_type 테이블에 실제로 반영한다 (생략하면 집계만)",
    )
    tag_parser.add_argument(
        "--include-cafe",
        action="store_true",
        dest="include_cafe",
        help="카페(CAFE_DESSERT) 메뉴도 태깅한다 (기본은 제외 — 서비스에 노출하지 않기로 함)",
    )
    tag_parser.add_argument(
        "--show-untagged",
        type=int,
        default=30,
        dest="show_untagged",
        help="태그가 하나도 안 붙은 메뉴를 몇 건 보여줄지 (기본 30). 키워드 보강 대상이다",
    )

    subparsers.add_parser(
        "export-foodtype-map",
        help="식약처 대분류 목록을 읽어 FoodType 대응표 초안을 만든다 (기존 값은 유지)",
    )

    seed_synonyms_parser = subparsers.add_parser(
        "seed-synonyms", help="검색어 동의어 사전을 food_type_synonym에 넣는다"
    )
    seed_synonyms_parser.add_argument(
        "--apply", action="store_true", help="DB에 실제로 반영한다 (생략하면 목록만 출력)"
    )

    score_labels_parser = subparsers.add_parser(
        "score-labels", help="라벨링 CSV의 '정답' 칸을 채점한다"
    )
    score_labels_parser.add_argument("--input", required=True, help="채점할 라벨링 CSV 경로")
    score_labels_parser.add_argument(
        "--candidates", type=int, default=10, help="후보 개수 (export-labels와 동일해야 함, 기본 10)"
    )

    return parser


def cmd_crawl(
    source: str,
    area: str,
    keyword: str | None,
    max_count: int,
    headless: bool,
    delay: float,
    out: str | None,
) -> int:
    """CrawlerFactory로 소스별 크롤러를 만들어 실행하고 결과를 정리한다.

    Returns:
        프로세스 종료 코드 (성공 시 0).
    """
    target = CrawlTarget(area=area, keyword=keyword, max_count=max_count)
    crawler = CrawlerFactory.create(source, headless=headless, request_delay=delay)

    with crawler as c:
        results = c.crawl(target)

    # 8번 파이프라인(CrawlPipeline.run)이 아직 없어, 여기서는 결과 확인용으로
    # JSON 저장 + 콘솔 요약까지만 한다. 8번 착수 시 아래 자리에 다음을 추가한다:
    #     report = CrawlPipeline(normalizer, enricher, repository).run(results)
    #     print(report)

    total_menus = sum(r.menu_count for r in results)
    print(f"수집 완료: 식당 {len(results)}건, 메뉴 합계 {total_menus}건")
    for r in results:
        print(f"  - {r}")

    # 임시 저장소: 8번 파이프라인이 생기기 전까지는 --out 지정 여부와 관계없이
    # 항상 JSON으로 저장한다. --out을 안 주면 source·area·시각으로 자동 명명.
    if out is None:
        timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_area = area.replace(" ", "_")
        DEFAULT_OUT_DIR.mkdir(parents=True, exist_ok=True)
        out = str(DEFAULT_OUT_DIR / f"{source}_{safe_area}_{timestamp}.json")

    payload = [dataclasses.asdict(r) for r in results]
    with open(out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"저장됨: {out}")

    return 0


def cmd_load(input_path: str, dry_run: bool) -> int:
    """crawl_results JSON을 읽어 정규화 → (dry-run이 아니면) DB 적재까지 수행한다.

    식당 1건 실패는 그 식당만 건너뛰고 나머지는 계속 진행한다.
    """
    from app.pipeline.normalizer import (
        Normalizer,
        SkipRestaurant,
        load_cuisine_map,
        load_excluded_menu_terms,
        load_menu_variants,
    )
    from app.pipeline.writer import WriteReport, _dedupe_menus, write_restaurant
    from app.settings import settings

    with open(input_path, encoding="utf-8") as f:
        raw_payload = json.load(f)

    raws = [
        RawRestaurant(
            name=d["name"],
            address=d["address"],
            raw_category=d["raw_category"],
            source_url=d["source_url"],
            latitude=d.get("latitude"),
            longitude=d.get("longitude"),
            menus=tuple(
                RawMenu(name=m["name"], price=m.get("price"))
                for m in d.get("menus", [])
            ),
        )
        for d in raw_payload
    ]

    # source_url 기준으로 배치 자체의 중복을 먼저 정리한다 (DB의 실제
    # upsert 동작과 dry-run 미리보기 결과를 일치시키기 위함).
    by_url: dict[str, RawRestaurant] = {}
    dup_url_count = 0
    for r in raws:
        if r.source_url in by_url:
            dup_url_count += 1
            continue
        by_url[r.source_url] = r
    raws = list(by_url.values())

    cuisine_map = load_cuisine_map(settings.cuisine_map_path)
    excluded_menu_terms = load_excluded_menu_terms(settings.excluded_menu_terms_path)
    menu_variants = load_menu_variants(settings.menu_variant_path)
    normalizer = Normalizer(cuisine_map, excluded_menu_terms, menu_variants)
    report = WriteReport()

    geocoder = None
    if not dry_run:
        # dry-run은 외부 API를 호출하지 않는다 — 리포트만 미리 볼 때 지오코딩
        # 쿼터를 쓰지 않기 위함. 키가 없으면 실제 적재에서도 좌표는 그대로 비운다.
        from app.pipeline.geocoder import KakaoGeocoder

        if settings.kakao_rest_api_key:
            geocoder = KakaoGeocoder(settings.kakao_rest_api_key)
        else:
            logger.warning(
                "MEALFIT_KAKAO_REST_API_KEY 미설정 — 지오코딩 없이 적재한다 (좌표는 NULL)."
            )

    for raw in raws:
        try:
            nr = normalizer.normalize(raw)
        except SkipRestaurant as e:
            report.add_skip(raw.name, str(e))
            continue

        if dry_run:
            deduped, dup_count = _dedupe_menus(nr.menus)
            report.restaurants_upserted += 1
            report.menus_upserted += len(deduped)
            report.menus_deduped += dup_count
            continue

        from app.db import session_scope

        try:
            with session_scope() as session:
                write_restaurant(session, nr, report, geocoder=geocoder)
        except Exception as e:  # noqa: BLE001 - 식당 1건 실패를 격리하기 위해 광범위하게 잡는다
            report.add_skip(raw.name, f"적재 실패: {e}")

    mode = "[DRY RUN] " if dry_run else ""
    logger.info("%s입력 파일: %s", mode, input_path)
    if dup_url_count:
        logger.info("입력 안 중복 source_url %d건 제거", dup_url_count)
    logger.info("%s", report.summary())
    return 0


def cmd_load_official_food(input_path: str) -> int:
    """식약처 음식DB xlsx를 official_food 테이블에 적재한다 (Step 2)."""
    from app.db import session_scope
    from app.pipeline.normalizer import load_menu_variants
    from app.pipeline.official_food import load_official_food
    from app.settings import settings

    menu_variants = load_menu_variants(settings.menu_variant_path)
    with session_scope() as session:
        report = load_official_food(input_path, session, menu_variants)

    logger.info("입력 파일: %s", input_path)
    logger.info("%s", report.summary())
    return 0


def cmd_match(
    apply: bool,
    sample: int,
    exclude_franchise: bool = False,
    exclude_cafe: bool = False,
    exclude_branch: bool = False,
) -> int:
    """menu 전체에 매칭 캐스케이드를 돌린다 (Step 3~5).

    --apply 없이 실행하면 DB를 건드리지 않고 방법별 매칭 건수만 집계한다.
    매칭 결과가 맞는지는 사람이 눈으로 봐야 하므로 방법별 예시도 함께 찍는다.
    """
    from app.db import session_scope
    from app.pipeline.matcher import CONFIDENCE, run_match

    with session_scope() as session:
        report, results = run_match(
            session,
            apply=apply,
            sample_size=sample,
            exclude_franchise=exclude_franchise,
            exclude_cafe=exclude_cafe,
            exclude_branch=exclude_branch,
        )

    mode = "" if apply else "[집계만 — DB 미반영] "
    logger.info("%s%s", mode, report.summary())

    # 지점명 규칙은 "본점"을 쓰는 개인 식당까지 걸어버릴 수 있어, 무엇이
    # 빠졌는지 사람이 직접 확인할 수 있도록 전체 목록을 남긴다.
    if report.excluded_branch_restaurants:
        logger.info(
            "[제외된 지점명 식당] %d곳", len(report.excluded_branch_restaurants)
        )
        for restaurant_name in report.excluded_branch_restaurants:
            logger.info("    %s", restaurant_name)

    # 방법별로 실제 어떤 짝이 맺어졌는지 몇 건씩 보여준다. 특히 NGRAM은
    # 오매칭이 섞이기 쉬운 단계라 반드시 눈으로 확인해야 한다.
    for method in CONFIDENCE:
        examples = [r for r in results if r.matched_by == method][:sample]
        if not examples:
            continue
        logger.info("[%s] 예시 %d건", method, len(examples))
        for r in examples:
            logger.info("    %s  →  %s", r.normalized_name, r.food_name)

    if report.unmatched_names:
        # 매칭 예시(위 for문)는 --sample로 자르지만, 미매칭은 다음 단계(LLM)의
        # 작업 목록 그 자체라 자르지 않고 전부 로그 파일에 남긴다.
        logger.info("[미매칭] 전체 %d건", len(report.unmatched_names))
        for name in report.unmatched_names:
            logger.info("    %s", name)

    if report.brand_unmatched_names:
        # 위 목록과 분리한다 — 이쪽은 "식약처에 그 브랜드의 그 메뉴가 없다"는
        # 뜻이라, 정규화나 LLM으로 풀 문제가 아니다.
        logger.info(
            "[브랜드 미매칭] %d건 — 해당 브랜드 식약처 항목에 없는 메뉴",
            len(report.brand_unmatched_names),
        )
        for name in report.brand_unmatched_names:
            logger.info("    %s", name)

    return 0


def cmd_export_labels(
    output: str,
    sample: int,
    candidates: int,
    seed: int,
    exclude_franchise: bool,
    exclude_cafe: bool,
    exclude_branch: bool = False,
    fresh: bool = False,
) -> int:
    """미매칭 메뉴 표본을 정답 라벨링용 CSV로 내보낸다."""
    from app.db import session_scope
    from app.pipeline.matcher import export_label_sheet

    with session_scope() as session:
        count = export_label_sheet(
            session,
            output_path=output,
            sample_size=sample,
            candidate_count=candidates,
            exclude_franchise=exclude_franchise,
            exclude_cafe=exclude_cafe,
            exclude_branch=exclude_branch,
            seed=seed,
            keep_answers=not fresh,
        )

    logger.info("%d건 저장됨: %s", count, output)
    logger.info(
        "'정답' 칸에 후보 번호(1~%d) / 0(식약처에 정답 없음) / "
        "제외(콤보·주류 등 매칭 대상 자체가 아님)를 적으면 된다.",
        candidates,
    )
    return 0


def cmd_export_branches(output: str) -> int:
    """'~점'으로 끝나는 식당을 프랜차이즈 검토용 CSV로 내보낸다."""
    from app.db import session_scope
    from app.pipeline.matcher import export_branch_restaurants

    with session_scope() as session:
        count = export_branch_restaurants(session, output_path=output)

    logger.info("%d곳 저장됨: %s", count, output)
    logger.info(
        "프랜차이즈가 맞으면 '브랜드(추정)' 칸을 확인·수정하고, "
        "그 브랜드만 data/excluded_brands.csv로 옮기면 된다."
    )
    return 0


def cmd_find_food(keyword: str, limit: int) -> int:
    """official_food를 이름 부분일치로 조회한다 (라벨링 중 '진짜 없는지' 확인용)."""
    from app.db import session_scope
    from app.pipeline.matcher import find_food

    with session_scope() as session:
        rows = find_food(session, keyword=keyword, limit=limit)

    if not rows:
        logger.info("'%s' 키워드로 official_food에서 찾은 결과가 없음", keyword)
        return 0

    logger.info("'%s' 키워드로 %d건 찾음", keyword, len(rows))
    for food_code, food_name, normalized_name, company_name, serving_basis, origin in rows:
        brand_note = f"  [{company_name}]" if company_name else ""
        basis_note = f"  ({serving_basis})" if serving_basis else ""
        origin_note = f"  <{origin}>" if origin else ""
        logger.info(
            "    %s  (%s)%s%s%s",
            food_name, food_code, basis_note, origin_note, brand_note,
        )
    return 0


def cmd_score_labels(input_path: str, candidates: int) -> int:
    """라벨링 CSV의 '정답' 칸을 채점한다."""
    from app.pipeline.matcher import score_label_sheet

    score = score_label_sheet(input_path, candidate_count=candidates)
    logger.info("입력 파일: %s", input_path)
    logger.info("%s", score.summary(candidates))
    return 0


def _resolve_provider(provider: str | None) -> str:
    from app.settings import settings

    return provider or settings.llm_provider


def _build_llm_client(provider: str | None, model: str | None, rpm: int | None):
    """CLI 인자 → 설정값 순으로 제공자·모델·호출속도를 정해 클라이언트를 만든다.

    모델 기본값은 제공자마다 다르다 — 로컬은 MEALFIT_OLLAMA_MODEL,
    클라우드는 MEALFIT_GEMINI_MODEL.
    """
    from app.pipeline.llm_matcher import create_client, is_local_provider
    from app.settings import settings

    chosen = _resolve_provider(provider)
    default_model = (
        settings.ollama_model if is_local_provider(chosen) else settings.gemini_model
    )
    return create_client(
        provider=chosen,
        api_key=settings.gemini_api_key,
        model=model or default_model,
        requests_per_minute=rpm if rpm is not None else settings.llm_requests_per_minute,
        base_url=settings.ollama_base_url,
        num_ctx=settings.ollama_num_ctx,
    )


def _resolve_batch_size(provider: str | None, batch: int | None) -> int:
    """배치 크기 기본값도 제공자마다 다르다 (로컬은 작게)."""
    from app.pipeline.llm_matcher import is_local_provider
    from app.settings import settings

    if batch is not None:
        return batch
    if is_local_provider(_resolve_provider(provider)):
        return settings.llm_local_batch_size
    return settings.llm_batch_size


def cmd_llm_models(provider: str | None) -> int:
    """지금 쓸 수 있는 모델 목록을 조회한다.

    로컬이면 받아둔 모델, 클라우드면 이 API 키로 호출 가능한 모델이다.
    모델명 404가 났을 때 무엇으로 바꿔야 하는지 확실히 아는 유일한 방법이다.
    """
    from app.pipeline.llm_matcher import LlmError, is_local_provider, list_available_models
    from app.settings import settings

    chosen = _resolve_provider(provider)
    try:
        models = list_available_models(
            chosen, api_key=settings.gemini_api_key, base_url=settings.ollama_base_url
        )
    except LlmError as e:
        print(f"오류: {e}", file=sys.stderr)
        return 1

    logger.info("[%s] 사용 가능한 모델 %d개", chosen, len(models))
    for name, note in models:
        logger.info("    %s  (%s)", name, note)

    env_name = "MEALFIT_OLLAMA_MODEL" if is_local_provider(chosen) else "MEALFIT_GEMINI_MODEL"
    logger.info("쓰고 싶은 모델 지정: $env:%s = '<위 목록 중 하나>'", env_name)
    if is_local_provider(chosen) and not models:
        logger.info(
            "목록이 비어 있으면 서버가 다른 모델 폴더를 보고 있는 것이다. "
            "OLLAMA_MODELS=F:\\AI_Model 을 설정한 뒤 Ollama를 다시 띄워라."
        )
    return 0


def cmd_llm_match(
    apply: bool,
    provider: str | None,
    model: str | None,
    candidates: int,
    limit: int,
    batch: int | None,
    rpm: int | None,
    refresh: bool,
    sample: int,
    exclude_franchise: bool,
    exclude_cafe: bool,
    exclude_branch: bool,
) -> int:
    """규칙 미매칭 메뉴를 LLM에게 물어본다 (Phase 3).

    --apply 없이도 menu_alias에는 판정이 기록된다. 같은 질문을 반복해서
    호출 비용을 다시 쓰지 않기 위함이며, 다시 묻고 싶으면 --refresh를 쓴다.
    """
    from app.db import session_scope
    from app.pipeline.llm_matcher import LlmError, run_llm_match

    try:
        client = _build_llm_client(provider, model, rpm)
    except LlmError as e:
        print(f"오류: {e}", file=sys.stderr)
        return 1

    with session_scope() as session:
        report, results = run_llm_match(
            session,
            client=client,
            apply=apply,
            candidate_count=candidates,
            limit=limit,
            batch_size=_resolve_batch_size(provider, batch),
            refresh=refresh,
            exclude_franchise=exclude_franchise,
            exclude_cafe=exclude_cafe,
            exclude_branch=exclude_branch,
        )

    mode = "" if apply else "[집계만 — menu 테이블 미반영] "
    logger.info("%s%s", mode, report.summary())

    # 매칭된 짝은 반드시 사람이 눈으로 봐야 한다. LLM 매칭은 규칙 매칭과 달리
    # 왜 그렇게 골랐는지 코드를 읽어서 추적할 수가 없다.
    matched = [r for r in results if r.matched][:sample]
    if matched:
        logger.info("[LLM 매칭] 예시 %d건", len(matched))
        for r in matched:
            note = " (캐시)" if r.from_cache else ""
            logger.info("    %s  →  %s%s", r.normalized_name, r.food_name, note)

    abstained = [r for r in results if r.decided and not r.matched][:sample]
    if abstained:
        logger.info("[없음 판정] 예시 %d건", len(abstained))
        for r in abstained:
            logger.info("    %s", r.normalized_name)

    failed = [r for r in results if r.error]
    if failed:
        # 실패는 menu_alias에 기록되지 않으므로 다음 실행에서 자동으로 재시도된다.
        logger.info("[답 못 받음] %d건 — 다시 실행하면 재시도된다", len(failed))
        for r in failed[:sample]:
            logger.info("    %s: %s", r.normalized_name, r.error)

    return 0


def cmd_llm_validate(
    input_path: str,
    provider: str | None,
    model: str | None,
    candidates: int,
    batch: int | None,
    rpm: int | None,
) -> int:
    """라벨링 CSV로 LLM을 채점한다 (Phase 3 검증)."""
    from app.pipeline.llm_matcher import LlmError, validate_with_labels

    try:
        client = _build_llm_client(provider, model, rpm)
    except LlmError as e:
        print(f"오류: {e}", file=sys.stderr)
        return 1

    report = validate_with_labels(
        input_path,
        client=client,
        candidate_count=candidates,
        batch_size=_resolve_batch_size(provider, batch),
    )
    logger.info("입력 파일: %s / 모델: %s", input_path, client.name)
    logger.info("%s", report.summary())
    return 0


def cmd_tag(apply: bool, include_cafe: bool, show_untagged: int) -> int:
    """메뉴에 FoodType을 붙인다 (Phase 4).

    --apply 없이 먼저 돌려 "태그 0개" 메뉴가 몇 건인지 보는 것을 권한다.
    그 메뉴들은 종류 필터 검색에서 통째로 사라지기 때문이다.
    """
    from app.db import session_scope
    from app.pipeline.tagger import TaggerError, run_tagging

    try:
        with session_scope() as session:
            report = run_tagging(session, apply=apply, include_cafe=include_cafe)
    except TaggerError as e:
        print(f"오류: {e}", file=sys.stderr)
        return 1

    logger.info("%s", report.summary(applied=apply))

    if report.untagged_names:
        shown = report.untagged_names[:show_untagged]
        logger.info(
            "[태그 0개] %d건 중 %d건 — 키워드 사전에 추가할 후보",
            len(report.untagged_names), len(shown),
        )
        for name in shown:
            logger.info("    %s", name)
    return 0


def cmd_export_foodtype_map() -> int:
    """식약처 대분류 목록으로 대응표 초안을 만든다."""
    from app.db import session_scope
    from app.pipeline.tagger import DEFAULT_MAP_PATH, export_foodtype_map

    with session_scope() as session:
        total, filled = export_foodtype_map(session)

    logger.info("대분류 %d종 중 %d종에 FoodType이 채워짐: %s", total, filled, DEFAULT_MAP_PATH)
    logger.info(
        "비어 있는 줄은 '그 대분류만으로는 종류를 정할 수 없다'는 뜻이다 — "
        "메뉴명 키워드가 대신 처리한다. 억지로 채우면 오분류가 늘어난다."
    )
    return 0


def cmd_seed_synonyms(apply: bool) -> int:
    """검색어 동의어 사전을 DB에 넣는다."""
    from app.db import session_scope
    from app.pipeline.tagger import TaggerError, seed_synonyms

    try:
        with session_scope() as session:
            count, seeds = seed_synonyms(session, apply=apply)
    except TaggerError as e:
        print(f"오류: {e}", file=sys.stderr)
        return 1

    mode = "" if apply else "[집계만 — DB 미반영] "
    logger.info("%s동의어 %d건", mode, count)
    for term, food_type in seeds:
        logger.info("    %s → %s", term, food_type)
    if not apply:
        logger.info("실제로 넣으려면 --apply를 붙여라.")
    return 0


def main(argv: list[str] | None = None) -> int:
    """argparse로 명령·옵션 파싱 후 해당 핸들러 호출. 종료 코드 반환."""
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    log_path = _configure_logging(args.command)
    logger.info("로그 파일: %s", log_path)

    if args.command == "crawl":
        try:
            return cmd_crawl(
                source=args.source,
                area=args.area,
                keyword=args.keyword,
                max_count=args.max_count,
                headless=not args.headed,
                delay=args.delay,
                out=args.out,
            )
        except ValueError as e:
            # 미등록 소스 등 사용자 입력 오류 — 스택트레이스 없이 메시지만 보여준다.
            print(f"오류: {e}", file=sys.stderr)
            return 1

    if args.command == "load":
        return cmd_load(input_path=args.input, dry_run=args.dry_run)

    if args.command == "load-official-food":
        return cmd_load_official_food(input_path=args.input)

    if args.command == "match":
        return cmd_match(
            apply=args.apply,
            sample=args.sample,
            exclude_franchise=args.exclude_franchise,
            exclude_cafe=args.exclude_cafe,
            exclude_branch=args.exclude_branch,
        )

    if args.command == "llm-match":
        return cmd_llm_match(
            apply=args.apply,
            provider=args.provider,
            model=args.model,
            candidates=args.candidates,
            limit=args.limit,
            batch=args.batch,
            rpm=args.rpm,
            refresh=args.refresh,
            sample=args.sample,
            exclude_franchise=args.exclude_franchise,
            exclude_cafe=args.exclude_cafe,
            exclude_branch=args.exclude_branch,
        )

    if args.command == "llm-validate":
        return cmd_llm_validate(
            input_path=args.input,
            provider=args.provider,
            model=args.model,
            candidates=args.candidates,
            batch=args.batch,
            rpm=args.rpm,
        )

    if args.command == "llm-models":
        return cmd_llm_models(provider=args.provider)

    if args.command == "tag":
        return cmd_tag(
            apply=args.apply,
            include_cafe=args.include_cafe,
            show_untagged=args.show_untagged,
        )

    if args.command == "export-foodtype-map":
        return cmd_export_foodtype_map()

    if args.command == "seed-synonyms":
        return cmd_seed_synonyms(apply=args.apply)

    if args.command == "export-branches":
        return cmd_export_branches(output=args.output)

    if args.command == "find-food":
        return cmd_find_food(keyword=args.keyword, limit=args.limit)

    if args.command == "score-labels":
        return cmd_score_labels(input_path=args.input, candidates=args.candidates)

    if args.command == "export-labels":
        return cmd_export_labels(
            output=args.output,
            sample=args.sample,
            candidates=args.candidates,
            seed=args.seed,
            exclude_franchise=args.exclude_franchise,
            exclude_cafe=args.exclude_cafe,
            exclude_branch=args.exclude_branch,
            fresh=args.fresh,
        )

    parser.error(f"알 수 없는 명령: {args.command}")
    return 2  # pragma: no cover - parser.error가 그 전에 SystemExit을 던짐


if __name__ == "__main__":
    raise SystemExit(main())
