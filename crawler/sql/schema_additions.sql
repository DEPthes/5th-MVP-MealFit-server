-- MealFit — 크롤러(Python)가 소유하는 스키마 추가분
--
-- Spring의 ddl-auto=update가 만들어주는 것은 "Java 엔티티에 매핑된 것"뿐입니다.
-- 아래는 Java가 모르지만 크롤러가 읽고 쓰는 컬럼·인덱스라, 이 파일이 따로 관리합니다.
-- (app/db.py 주석이 가리키는 파일이 바로 이것입니다.)
--
-- 실행 순서:
--   1) Spring을 한 번 실행해 기본 테이블을 만든다 (ddl-auto=update)
--   2) mysql -u root -p mealfit_test < sql/schema_additions.sql   ← 이 파일
--   3) mysql -u root -p mealfit_test < sql/seed_test_data.sql     (테스트 데이터)
--
-- 여러 번 실행해도 안전합니다 (이미 있으면 건너뜁니다).

SET NAMES utf8mb4;


-- ---------------------------------------------------------------------------
-- 헬퍼: 컬럼/인덱스가 없을 때만 DDL을 실행한다.
-- MySQL 8에는 ADD COLUMN IF NOT EXISTS가 없어서 이 방식을 쓴다.
-- ---------------------------------------------------------------------------

DROP PROCEDURE IF EXISTS mealfit_require_tables;
DROP PROCEDURE IF EXISTS mealfit_add_column;
DROP PROCEDURE IF EXISTS mealfit_drop_column;
DROP PROCEDURE IF EXISTS mealfit_add_unique;

DELIMITER $$

-- 사전 조건 검사. restaurant/menu는 서버 엔티티가 만드는 테이블이라
-- 여기서 만들지 않는다. 없는 상태로 진행하면 ALTER TABLE이 죽으므로,
-- 원인을 알 수 있는 메시지로 먼저 멈춘다.
CREATE PROCEDURE mealfit_require_tables()
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.TABLES
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'restaurant'
    ) OR NOT EXISTS (
        SELECT 1 FROM information_schema.TABLES
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'menu'
    ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT =
            'restaurant/menu 테이블이 없습니다. 서버(Spring)를 한 번 실행해 테이블을 만든 뒤 다시 실행하세요.';
    END IF;
END$$

CREATE PROCEDURE mealfit_add_column(
    IN p_table VARCHAR(64), IN p_column VARCHAR(64), IN p_definition TEXT
)
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = p_table AND COLUMN_NAME = p_column
    ) THEN
        SET @ddl = CONCAT('ALTER TABLE `', p_table, '` ADD COLUMN `', p_column, '` ', p_definition);
        PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;
    END IF;
END$$

CREATE PROCEDURE mealfit_drop_column(IN p_table VARCHAR(64), IN p_column VARCHAR(64))
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = p_table AND COLUMN_NAME = p_column
    ) THEN
        SET @ddl = CONCAT('ALTER TABLE `', p_table, '` DROP COLUMN `', p_column, '`');
        PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;
    END IF;
END$$

CREATE PROCEDURE mealfit_add_unique(
    IN p_table VARCHAR(64), IN p_index VARCHAR(64), IN p_columns TEXT
)
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.STATISTICS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = p_table AND INDEX_NAME = p_index
    ) THEN
        SET @ddl = CONCAT('ALTER TABLE `', p_table, '` ADD UNIQUE KEY `', p_index, '` (', p_columns, ')');
        PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;
    END IF;
END$$
DELIMITER ;

CALL mealfit_require_tables();


-- ---------------------------------------------------------------------------
-- restaurant — 좌표
--
-- 크롤러가 지오코딩해 채우고, 서버는 Restaurant 엔티티에서 읽기 전용으로
-- 노출합니다 (RestaurantResponse.latitude/longitude). 서버가 먼저 뜨면
-- Hibernate가 만들고, 크롤러가 먼저면 여기서 만듭니다 (둘 다 DOUBLE NULL).
-- 이게 없으면 빈 DB에서 크롤러의 INSERT가 깨집니다.
-- ---------------------------------------------------------------------------

CALL mealfit_add_column('restaurant', 'latitude',  'DOUBLE NULL COMMENT ''크롤러 소유 — 지오코딩 결과''');
CALL mealfit_add_column('restaurant', 'longitude', 'DOUBLE NULL COMMENT ''크롤러 소유 — 지오코딩 결과''');


-- ---------------------------------------------------------------------------
-- restaurant — 거리 컬럼 이름 정리
--
-- 초기에는 크롤러가 distance_from_front_gate_m / distance_from_back_gate_m에
-- 썼지만, 서버가 distance_to_main_gate / distance_to_back_gate를 읽으므로
-- 서버 이름으로 통일했습니다. 구 컬럼은 값이 채워진 적이 없어 그냥 버립니다.
--
-- 서버 엔티티가 nullable=false로 선언하지만 여기서는 NULL을 허용합니다 —
-- 좌표를 못 구한 식당은 거리를 계산할 수 없기 때문입니다.
-- ---------------------------------------------------------------------------

CALL mealfit_add_column('restaurant', 'distance_to_main_gate', 'INT NULL COMMENT ''명지대 정문(정류장)까지 직선거리(m)''');
CALL mealfit_add_column('restaurant', 'distance_to_back_gate', 'INT NULL COMMENT ''명지대 후문(도서관)까지 직선거리(m)''');

CALL mealfit_drop_column('restaurant', 'distance_from_front_gate_m');
CALL mealfit_drop_column('restaurant', 'distance_from_back_gate_m');


-- ---------------------------------------------------------------------------
-- menu — 매칭 출처
--
-- 어떤 방법으로 식약처 식품과 짝지어졌는지 기록합니다 (규칙 기반 / LLM 모델명 등).
-- 매칭 품질을 사후에 점검할 때 쓰며, 서버는 읽지 않습니다.
-- ---------------------------------------------------------------------------

CALL mealfit_add_column('menu', 'matched_by', 'VARCHAR(64) NULL COMMENT ''매칭 방법 (rule / gemini/모델명 등)''');


-- ---------------------------------------------------------------------------
-- menu — 자연키
--
-- 크롤러의 upsert가 ON DUPLICATE KEY UPDATE로 이 키에 의존합니다.
-- 서버 Menu 엔티티는 uniqueConstraints를 선언하지 않아 Hibernate가 만들지 않습니다.
-- 이게 없으면 재적재할 때마다 같은 메뉴가 중복 삽입됩니다.
-- ---------------------------------------------------------------------------

CALL mealfit_add_unique('menu', 'uk_menu_natural', '`restaurant_id`, `normalized_name`');


-- ---------------------------------------------------------------------------
-- official_food — 식약처 식품 DB
--
-- ⚠️ 순서 함정: 서버 OfficialFood 엔티티는 food_code / food_name /
-- representative_name 3개만 매핑합니다. 빈 DB에서 Spring이 먼저 뜨면
-- Hibernate가 이 테이블을 3개 컬럼짜리로 만들어 버리고, 그 뒤 크롤러의
-- CREATE TABLE IF NOT EXISTS는 아무것도 하지 않아 15개 컬럼 INSERT가 깨집니다.
-- 그래서 나머지 12개 컬럼을 여기서 채워 넣습니다.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS official_food (
    food_code           VARCHAR(30) NOT NULL,
    food_name           VARCHAR(255) NOT NULL,
    normalized_name     VARCHAR(255) COLLATE utf8mb4_bin NOT NULL,
    origin              VARCHAR(50) NULL,
    major_category      VARCHAR(100) NULL,
    calories            INT NULL,
    carbohydrate        DECIMAL(8,2) NULL,
    protein             DECIMAL(8,2) NULL,
    fat                 DECIMAL(8,2) NULL,
    sodium              DECIMAL(8,2) NULL,
    serving_weight_raw  VARCHAR(50) NULL,
    company_name        VARCHAR(100) NULL,
    serving_basis       VARCHAR(10) NULL,
    representative_code VARCHAR(20) NULL,
    representative_name VARCHAR(255) NULL,
    PRIMARY KEY (food_code),
    INDEX idx_normalized (normalized_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Spring이 먼저 만들어 3개 컬럼만 있는 경우를 보정한다.
CALL mealfit_add_column('official_food', 'normalized_name',     'VARCHAR(255) COLLATE utf8mb4_bin NOT NULL DEFAULT ''''');
CALL mealfit_add_column('official_food', 'origin',              'VARCHAR(50) NULL');
CALL mealfit_add_column('official_food', 'major_category',      'VARCHAR(100) NULL');
CALL mealfit_add_column('official_food', 'calories',            'INT NULL');
CALL mealfit_add_column('official_food', 'carbohydrate',        'DECIMAL(8,2) NULL');
CALL mealfit_add_column('official_food', 'protein',             'DECIMAL(8,2) NULL');
CALL mealfit_add_column('official_food', 'fat',                 'DECIMAL(8,2) NULL');
CALL mealfit_add_column('official_food', 'sodium',              'DECIMAL(8,2) NULL');
CALL mealfit_add_column('official_food', 'serving_weight_raw',  'VARCHAR(50) NULL');
CALL mealfit_add_column('official_food', 'company_name',        'VARCHAR(100) NULL');
CALL mealfit_add_column('official_food', 'serving_basis',       'VARCHAR(10) NULL');
CALL mealfit_add_column('official_food', 'representative_code', 'VARCHAR(20) NULL');
CALL mealfit_add_column('official_food', 'representative_name', 'VARCHAR(255) NULL');


-- ---------------------------------------------------------------------------
-- menu_alias — LLM 판정 영구 기록
--
-- 같은 메뉴명을 두 번 묻지 않기 위한 캐시입니다. "매칭 없음" 판정도 기록해서
-- 재실행 시 모델을 다시 호출하지 않습니다. app/pipeline/llm_matcher.py가
-- CREATE TABLE IF NOT EXISTS로 직접 만들지만, 스키마를 한곳에서 보기 위해
-- 여기에도 적어 둡니다.
-- ---------------------------------------------------------------------------

-- 정규화명이 PK인 이유: 같은 메뉴명이 식당 10곳에 있어도 판정은 하나면 되고,
-- 재실행 때 같은 질문을 다시 하지 않기 위한 캐시 역할도 겸하기 때문입니다.
-- food_code가 NULL인 행 = "LLM이 매칭 없음이라고 판정했다"는 기록입니다.
CREATE TABLE IF NOT EXISTS menu_alias (
    normalized_name VARCHAR(255) COLLATE utf8mb4_bin NOT NULL,
    food_code       VARCHAR(30) NULL,
    matched_by      VARCHAR(20) NOT NULL,
    confidence      DECIMAL(3,2) NULL,
    model           VARCHAR(60) NULL,
    raw_answer      VARCHAR(255) NULL,
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                    ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (normalized_name),
    INDEX idx_alias_food_code (food_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- 헬퍼 정리
-- ---------------------------------------------------------------------------

DROP PROCEDURE IF EXISTS mealfit_require_tables;
DROP PROCEDURE IF EXISTS mealfit_add_column;
DROP PROCEDURE IF EXISTS mealfit_drop_column;
DROP PROCEDURE IF EXISTS mealfit_add_unique;
