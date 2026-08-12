"""파이프라인 설정. .env → 환경변수 → 기본값 순으로 채워진다 (pydantic-settings).

DB 접속 정보 기본값은 Spring application.properties(mealfit_test)와 같은
로컬 인스턴스를 가리킨다. 비밀번호·API 키는 기본값에 넣지 않는다 — 실행 전
환경변수로 넘긴다.
"""

from __future__ import annotations

from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MEALFIT_", env_file=".env", extra="ignore")

    db_host: str = "localhost"
    db_port: int = 3306
    db_name: str = "mealfit_test"
    db_user: str = "root"
    db_password: str = ""

    #: 정규화 사전 위치 (프로젝트 루트 기준 상대경로)
    cuisine_map_path: str = "data/cuisine_map.csv"
    modifier_path: str = "data/modifier.csv"
    excluded_menu_terms_path: str = "data/excluded_menu_terms.csv"
    menu_variant_path: str = "data/menu_variant.csv"

    #: Kakao Local API (주소 검색) REST 키. 비어있으면 지오코딩을 건너뛴다.
    kakao_rest_api_key: str = ""

    #: Phase 3 LLM 매칭(llm_matcher.py) 설정.
    #: 키는 기본값에 넣지 않는다 — 실행 전 MEALFIT_GEMINI_API_KEY로 넘긴다.
    #: (Spring application.properties의 gemini.api-key와 같은 값)
    #: 기본은 로컬(Ollama)이다 — 쿼터·비용이 없고 메뉴 데이터가 밖으로 나가지
    #: 않는다. 클라우드로 바꾸려면 MEALFIT_LLM_PROVIDER=gemini.
    llm_provider: str = "ollama"

    #: 로컬 Ollama. 모델 파일은 F:\AI_Model에 있으므로, 서버를 띄울 때
    #: OLLAMA_MODELS=F:\AI_Model 이 설정돼 있어야 이 모델들이 보인다.
    ollama_base_url: str = "http://localhost:11434"
    #: gemma4:latest(약 9GB)는 5070 Ti 16GB에 통째로 올라가 빠르다.
    #: gemma4:26b(약 16.8GB)는 VRAM을 넘겨 일부가 CPU로 내려가 느리지만 더 정확하다.
    ollama_model: str = "gemma4:latest"
    ollama_num_ctx: int = 8192
    #: 로컬 모델용 배치 크기. 작은 모델일수록 긴 지시문에서 항목을 빠뜨린다.
    llm_local_batch_size: int = 5

    gemini_api_key: str = ""
    #: 모델명은 계정·시점에 따라 달라진다 — `gemini-2.5-flash`는 이 키로 404가
    #: 났다("신규 사용자에게는 더 이상 제공되지 않음"). `-latest` 별칭은 최신
    #: 모델을 따라가므로 중단에 덜 취약하다. 확실한 목록은 `llm-models` 명령으로
    #: 조회하고, 바꿀 때는 MEALFIT_GEMINI_MODEL만 지정하면 된다.
    gemini_model: str = "gemini-flash-latest"
    #: 분당 호출 상한. 무료 쿼터에서 429가 쏟아지는 걸 막는다.
    llm_requests_per_minute: int = 5
    #: 한 요청에 담을 메뉴 수. 호출 수를 1/N로 줄인다.
    llm_batch_size: int = 20

    #: 명지대 정문·후문 좌표. Spring 쪽 ReferencePoint(Java)와 동일한 확정값을
    #: 기본값으로 둔다 — 정문=명지대 정류장, 후문=명지대 도서관(방목학술정보관).
    #: 필요하면 환경변수로 덮어쓸 수 있다.
    gate_main_lat: float | None = 37.579132
    gate_main_lng: float | None = 126.923488
    gate_back_lat: float | None = 37.5807266
    gate_back_lng: float | None = 126.9244188

    @property
    def sqlalchemy_url(self) -> str:
        # 비밀번호에 @·#·: 같은 URL 예약 문자가 들어있으면(예: "p@ss#word")
        # 그대로 이어붙일 때 '@'가 host 구분자로 오인되어 접속 자체가 깨진다.
        # user/password는 반드시 퍼센트 인코딩해서 넣는다.
        user = quote_plus(self.db_user)
        password = quote_plus(self.db_password)
        return (
            f"mysql+pymysql://{user}:{password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}?charset=utf8mb4"
        )


settings = Settings()
