"""Phase 3 — 규칙 캐스케이드가 놓친 메뉴를 LLM에게 물어본다 (D-2).

`matcher.py`의 4단계(EXACT/EDIT/STRUCT/NGRAM)가 **전부 실패한 메뉴만** 대상이다.
캐스케이드에 끼어드는 5번째 단계가 아니라, 그 뒤에 따로 붙는 패스다 — 규칙으로
잡히는 것을 LLM에게 다시 물어볼 이유가 없고, 비용만 든다.

설계에서 중요한 것:

1. **객관식이다.** 자유 생성으로 "이 메뉴의 영양정보는?"이라고 물으면 LLM이
   그럴듯한 숫자를 지어낸다. 여기서는 `Matcher.top_candidates()`가 뽑아둔
   후보 N개를 주고 **번호 하나 또는 "없음"**만 답하게 한다. 답이 후보 목록
   안에 갇혀 있으므로 환각이 구조적으로 불가능하다.

2. **"없음"을 고르기 쉽게 만드는 것이 핵심이다.** 라벨링 35건 실측 결과
   미매칭 메뉴의 **40%는 식약처 DB에 애초에 정답이 없었다**. LLM도 그만큼
   기권해야 정상이고, 억지로 고르면 틀린 영양 수치가 사용자에게 그대로
   노출된다. 그래서 프롬프트가 기권을 반복해서 허용하고, `llm-validate`가
   "정답 없음(0)으로 라벨링된 행을 LLM도 없음이라 하는지"를 따로 채점한다.

3. **한 번에 여러 메뉴를 묶어 묻는다(배치).** 메뉴 1건마다 호출하면 179번을
   불러야 하고 무료 쿼터가 즉시 소진된다. 한 요청에 메뉴 20건을 담으면 9번이면
   끝난다. 호출 간격도 `RateLimiter`로 강제한다(기본 분당 5회).

4. **결과는 `menu_alias`에 영구 기록한다.** 매칭 성공뿐 아니라 **"없음"도
   기록한다** — 안 그러면 재실행할 때마다 같은 메뉴를 다시 물어보게 된다.
   정규화명 기준으로 저장하므로, 같은 이름이 여러 식당에 있어도 질문은 1회다.

5. **설정 오류는 즉시 멈춘다.** 모델명이 틀리면(404) 몇 건을 돌든 똑같이
   실패한다. 실제로 404를 179번 반복하며 로그만 채운 적이 있어, 그런 상태는
   첫 응답에서 실행 전체를 중단시킨다(`LlmFatalError`).

제공자는 교체 가능하다(`LlmClient` 프로토콜). 지금은 세 가지가 있다:

- `ollama` — 로컬 Ollama 서버(기본값). 쿼터도 비용도 없어서 호출 제한이 필요
  없고, 데이터가 밖으로 나가지 않는다. 대신 모델이 작아 지시를 덜 정확히
  따르므로 배치를 작게 잡는다.
- `gemini` — 클라우드. 무료 쿼터가 분당·일일로 걸려 `RateLimiter`가 필요하다.
- `fake` — API 없이 배선만 확인하는 대역.
"""

from __future__ import annotations

import csv
import json
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from sqlalchemy import text
from sqlalchemy.orm import Session

# 메뉴 필터(프랜차이즈·카페·지점명) 규칙은 matcher와 **반드시 같아야** 한다.
# 여기서 복붙하면 한쪽만 고쳤을 때 "규칙 38.3% + LLM x%"의 분모가 서로 달라져
# 숫자를 합칠 수 없게 된다. 그래서 같은 패키지 안의 비공개 이름을 그대로 쓴다.
from app.pipeline.matcher import (
    _BRANCH_SUFFIX,
    _CAFE_CUISINE,
    _EXCLUDE_TOKENS,
    _FOOD_CODE_PATTERN,
    _SELECT_MENUS,
    _UPDATE_MENU,
    CONFIDENCE,
    Candidate,
    _contains_brand,
    build_matcher_set,
    load_excluded_brands,
)

logger = logging.getLogger(__name__)

#: 이 패스의 매칭 방법 이름. menu.matched_by / menu_alias.matched_by에 그대로 들어간다.
METHOD = "LLM"

#: Gemini generateContent 엔드포인트. 모델명만 갈아끼우면 된다.
_GEMINI_ENDPOINT = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)

#: 사용 가능한 모델 목록 조회. 모델명은 계정·시점에 따라 달라진다
#: (실제로 `gemini-2.5-flash`가 "신규 사용자에겐 제공 안 됨"으로 404가 났다).
#: 코드에 적힌 기본값을 믿지 말고 `llm-models` 명령으로 확인한다.
_GEMINI_LIST_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models"

#: 응답이 잘리면 답을 못 읽으므로 넉넉히 준다. 답 자체는 메뉴당 한 줄("3: 없음")
#: 이지만, 추론(thinking)을 하는 모델은 그 과정에도 토큰을 쓴다.
_OUTPUT_TOKENS_BASE = 1024
_OUTPUT_TOKENS_PER_ITEM = 64

#: 같은 질문에 항상 같은 답이 나와야 재현·비교가 가능하다.
_TEMPERATURE = 0.0

#: 한 요청에 담을 메뉴 수. 20건이면 179건이 9번의 호출로 끝난다.
#: 너무 키우면 한 번 실패할 때 날아가는 양이 커지고, 모델이 뒤쪽 메뉴를
#: 대충 판단할 위험도 커진다.
DEFAULT_BATCH_SIZE = 20

#: 로컬 모델용 배치 기본값. 클라우드 모델보다 작게 잡는다 — 파라미터 수가
#: 적은 모델은 긴 지시문에서 뒤쪽 항목을 빠뜨리거나 출력 형식을 흐트러뜨린다.
#: 로컬은 호출 수가 늘어도 비용이 0이라 작게 나눠도 손해가 없다.
DEFAULT_LOCAL_BATCH_SIZE = 5

#: 분당 호출 수 상한. 무료 쿼터에서 429가 쏟아지는 걸 막는다.
#: 로컬(Ollama)은 쿼터가 없어 0(무제한)으로 둔다.
DEFAULT_REQUESTS_PER_MINUTE = 5

#: 로컬 Ollama 기본 주소·컨텍스트. 배치 20건이 약 4천 토큰이라 8192면 넉넉하다.
#: 컨텍스트가 모자라면 모델이 앞쪽 지시를 조용히 잘라먹어, 답이 이상해져도
#: 원인이 드러나지 않는다.
DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_OLLAMA_NUM_CTX = 8192

#: 로컬 모델의 출력 한도. 클라우드보다 훨씬 크게 잡는다 — 로컬은 토큰이
#: 공짜인데, 한도가 모자라면 모델이 사고 과정(thinking)만 쓰다가 잘려서
#: 최종 답이 **빈 문자열**로 돌아온다(done_reason=length). 실제로 그렇게
#: 배치 전체가 날아갔다. 한도는 상한일 뿐이라 크게 잡아도 손해가 없다.
_LOCAL_OUTPUT_TOKENS_BASE = 3072
_LOCAL_OUTPUT_TOKENS_PER_ITEM = 128

#: 일시적 오류(쿼터·서버)일 때만 재시도한다.
_RETRY_STATUS = {429, 500, 502, 503, 504}
_MAX_RETRIES = 3
_RETRY_BASE_DELAY = 2.0

#: 재시도도, 다음 배치로 넘어가는 것도 의미가 없는 상태들. 모델명이 틀렸거나
#: 키가 잘못됐다면 끝까지 똑같이 실패한다 — 첫 응답에서 멈춘다.
_FATAL_STATUS = {400, 401, 403, 404}

#: 연속으로 이만큼의 배치가 실패하면 전체를 중단한다. 쿼터가 소진된 상태에서
#: 남은 배치를 계속 두드려봐야 429만 쌓이고 시간만 간다.
_MAX_CONSECUTIVE_FAILURES = 3

#: 기권 표현. 프롬프트는 "없음"만 요구하지만 모델이 다르게 쓸 수 있어 넓게 받는다.
_ABSTAIN_WORDS = ("없음", "없다", "해당없음", "none", "null", "n/a")

_PROMPT_HEADER = """\
너는 한국 식당의 메뉴명을 식약처 음식DB 항목에 연결하는 검수자다.
아래 메뉴 {count}건을 각각 판정한다.

[판정 기준]
- 판단 질문은 하나다: "이 후보의 영양 수치를 저 메뉴의 영양정보라고 사용자에게
  보여줘도 문제없는가?" 자신 있게 '그렇다'고 답할 수 있을 때만 번호를 고른다.
- 주재료가 다르면 다른 음식이다.
- 조리 형태가 바뀌면 다른 음식이다 (새우튀김 vs 새우튀김롤, 깐쇼새우 vs 깐쇼새우피자).
- 메뉴명 쪽에 수식어만 더 붙은 것은 같은 음식일 수 있다 (왕갈비탕 = 갈비탕, 화룡 양장피 = 양장피).
- 후보 이름 뒤 대괄호는 [식품기원 · 분류]다. **같은 음식이 여러 번 나오면
  기원으로 고른다: 외식(분석함량) > 외식(재료량 기반 산출함량) > 가정식.**
  우리가 값을 붙일 대상은 식당에서 파는 음식이고, 분석함량은 실제로 측정한 값,
  재료량 기반 산출함량은 레시피로 계산한 추정값이다.
- **메뉴가 고기 부위·재료 이름 하나뿐이면(꽃등심·항정살·염통·해삼·뽈살) 반드시
  "없음"이다.** 조리된 요리가 아니라 생재료라서 이 DB에는 해당 항목이 없다.
  `소등심구이` 같은 조리 요리를 대신 고르면 안 된다.
- 후보에 정답이 없는 경우가 매우 흔하다. 실측 결과 이런 메뉴의 약 40%는 식약처
  DB에 애초에 정답이 존재하지 않았다. **애매하면 반드시 "없음"이라고 답한다.**
  억지로 가장 비슷한 것을 고르는 일은 틀린 영양 수치를 사용자에게 보여주는 것이라,
  아무것도 고르지 않는 것보다 나쁘다.
- 메뉴마다 독립적으로 판단한다. 다른 메뉴의 답에 맞출 필요가 없고, 기권이
  몇 개가 되든 상관없다.

[출력 형식]
메뉴 {count}건 전부에 대해 한 줄씩, 아래 형식으로만 답한다. 설명·머리말·빈 줄 금지.
<메뉴번호>: <후보번호 또는 없음>

예시)
1: 3
2: 없음
3: 7
"""

_PROMPT_ITEM = """\
[메뉴 {index}]
메뉴명: {menu_name}
식당: {restaurant}
후보:
{candidate_lines}
"""


class LlmError(RuntimeError):
    """LLM 호출 실패(네트워크·쿼터·응답 형식). 배치 1건만 건너뛰고 계속 진행한다."""


class LlmAnswerError(LlmError):
    """응답은 왔는데 번호로도 기권으로도 읽을 수 없는 경우."""


class LlmFatalError(LlmError):
    """설정 자체가 틀려서 다음 배치로 넘어가도 똑같이 실패할 오류.

    모델명 오타·만료(404), 키 없음·권한 없음(401/403), 잘못된 요청(400).
    실행 전체를 중단시킨다 — 한 건씩 실패로 넘기면 같은 메시지가 수백 줄
    쌓여서 정작 원인이 안 보인다.
    """


class RateLimiter:
    """호출 사이 최소 간격을 강제한다.

    무료 쿼터는 분당 요청 수로 걸리므로, 재시도까지 포함해 "요청을 보내기
    직전"에 항상 이 간격을 지킨다.
    """

    def __init__(self, per_minute: int):
        self.per_minute = per_minute
        self._interval = 60.0 / per_minute if per_minute > 0 else 0.0
        self._last: float | None = None

    def wait(self) -> None:
        if self._interval <= 0:
            return
        if self._last is not None:
            gap = self._interval - (time.monotonic() - self._last)
            if gap > 0:
                logger.info("호출 간격 유지 — %.1f초 대기 (분당 %d회)", gap, self.per_minute)
                time.sleep(gap)
        self._last = time.monotonic()


def _describe_error(response) -> str:
    """오류 응답에서 사람이 읽을 메시지만 뽑는다.

    Gemini 오류 본문은 JSON이 길어서 통째로 찍으면 로그가 뒤덮인다. 정작
    필요한 건 `error.message` 한 줄이다.
    """
    try:
        message = (response.json().get("error") or {}).get("message") or ""
    except Exception:  # noqa: BLE001 - JSON이 아닐 수도 있다
        message = ""
    if not message:
        message = response.text[:300]
    return f"HTTP {response.status_code}: {message[:500]}"


def _retry_after_seconds(response) -> float | None:
    """429 응답이 알려주는 대기 시간(`retryDelay: "27s"`)을 초로 바꾼다."""
    try:
        details = (response.json().get("error") or {}).get("details") or []
    except Exception:  # noqa: BLE001
        return None
    for detail in details:
        if not isinstance(detail, dict):
            continue
        if not str(detail.get("@type", "")).endswith("RetryInfo"):
            continue
        raw = str(detail.get("retryDelay", "")).strip()
        m = re.match(r"^([\d.]+)s$", raw)
        if m:
            return float(m.group(1))
    return None


class LlmClient(Protocol):
    """제공자 무관 인터페이스. 프롬프트 문자열을 주면 답 문자열을 돌려준다.

    Gemini를 다른 제공자로 갈아끼울 때 이 메서드 하나만 맞추면 되도록,
    프롬프트 구성·응답 파싱은 전부 이 바깥(모듈 함수)에 둔다.
    """

    #: 로그·menu_alias에 남길 식별자 (예: "gemini/gemini-flash-latest")
    name: str

    def ask(self, prompt: str, expected_items: int = 1) -> str: ...


class GeminiClient:
    """Gemini generateContent 호출.

    API 키는 쿼리스트링이 아니라 헤더로 보낸다 — 쿼리로 붙이면 요청 URL이
    로그·프록시·예외 메시지에 그대로 남는다.
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        timeout: float = 60.0,
        max_retries: int = _MAX_RETRIES,
        requests_per_minute: int = DEFAULT_REQUESTS_PER_MINUTE,
    ):
        if not api_key:
            raise LlmFatalError(
                "Gemini API 키가 없다. 환경변수 MEALFIT_GEMINI_API_KEY로 넘겨라 "
                "(Spring application.properties의 gemini.api-key와 같은 값)."
            )
        # requests는 이 클라이언트에서만 필요하다. 모듈 최상단에서 import하면
        # --provider fake로 API 없이 파이프라인만 돌려볼 때까지 의존성이 걸린다.
        import requests

        self._requests = requests
        self._api_key = api_key
        self._model = model
        self._timeout = timeout
        self._max_retries = max_retries
        self._limiter = RateLimiter(requests_per_minute)
        self.name = f"gemini/{model}"

    def ask(self, prompt: str, expected_items: int = 1) -> str:
        url = _GEMINI_ENDPOINT.format(model=self._model)
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": _TEMPERATURE,
                "maxOutputTokens": (
                    _OUTPUT_TOKENS_BASE + _OUTPUT_TOKENS_PER_ITEM * max(expected_items, 1)
                ),
            },
        }
        headers = {
            "x-goog-api-key": self._api_key,
            "Content-Type": "application/json",
        }

        last_error = ""
        for attempt in range(1, self._max_retries + 1):
            server_wait: float | None = None
            self._limiter.wait()
            try:
                response = self._requests.post(
                    url, headers=headers, json=payload, timeout=self._timeout
                )
            except Exception as e:  # noqa: BLE001 - 네트워크 예외 종류가 라이브러리마다 달라 통째로 잡는다
                last_error = f"요청 실패: {e}"
            else:
                if response.status_code == 200:
                    return self._extract_text(response.json())

                last_error = _describe_error(response)
                if response.status_code in _FATAL_STATUS:
                    # 모델명·키 문제. 재시도도 다음 배치도 의미가 없다.
                    raise LlmFatalError(last_error)
                if response.status_code not in _RETRY_STATUS:
                    raise LlmError(last_error)
                # 429는 "언제 다시 오라"는 지시를 응답에 담아준다. 그게 있으면
                # 임의의 지수 백오프보다 그쪽을 따르는 편이 정확하다.
                server_wait = _retry_after_seconds(response)

            if attempt < self._max_retries:
                wait = _RETRY_BASE_DELAY * (2 ** (attempt - 1))
                if server_wait is not None:
                    wait = max(wait, server_wait)
                logger.warning(
                    "Gemini 호출 실패(%d/%d) — %.1f초 후 재시도: %s",
                    attempt, self._max_retries, wait, last_error,
                )
                time.sleep(wait)

        raise LlmError(f"재시도 {self._max_retries}회 모두 실패 — {last_error}")

    @staticmethod
    def _extract_text(data: dict) -> str:
        """응답 JSON에서 텍스트만 뽑는다.

        추론 모델은 parts가 여러 개로 쪼개져 오거나 text가 없는 part를 섞어
        보내므로, text가 있는 조각만 이어붙인다.
        """
        candidates = data.get("candidates") or []
        if not candidates:
            # 안전필터 등으로 후보 자체가 없는 경우. 사유를 그대로 올려야
            # "왜 전부 실패하는지"를 로그만 보고 알 수 있다.
            raise LlmAnswerError(f"응답에 candidates 없음: {json.dumps(data)[:300]}")

        first = candidates[0]
        parts = (first.get("content") or {}).get("parts") or []
        chunks = [p["text"] for p in parts if isinstance(p, dict) and p.get("text")]
        merged = "".join(chunks).strip()

        if not merged:
            reason = first.get("finishReason", "?")
            hint = (
                " — 추론 토큰이 한도를 다 써서 답이 비었을 수 있다. "
                "--batch를 줄이거나 _OUTPUT_TOKENS_PER_ITEM을 올려라."
                if reason == "MAX_TOKENS"
                else ""
            )
            raise LlmAnswerError(f"응답 텍스트가 비어있음 (finishReason={reason}){hint}")
        return merged


class OllamaClient:
    """로컬 Ollama 서버 호출 (`/api/chat`).

    쿼터도 비용도 없으므로 `RateLimiter`를 걸지 않는다 — 어차피 로컬 GPU가
    한 번에 하나씩 처리해서 자연히 순차 실행된다.

    로컬 특유의 실패 두 가지를 설정 오류로 분류해 즉시 중단시킨다:
      - 서버가 꺼져 있음(연결 거부) → `ollama serve`
      - 모델을 안 받아둠(404) → `ollama pull <모델>`
    둘 다 배치를 몇 번 더 돌린다고 나아지지 않는다.
    """

    def __init__(
        self,
        model: str,
        base_url: str = DEFAULT_OLLAMA_BASE_URL,
        timeout: float = 600.0,
        num_ctx: int = DEFAULT_OLLAMA_NUM_CTX,
        max_retries: int = 3,
    ):
        if not model:
            raise LlmFatalError(
                "사용할 로컬 모델명이 없다. MEALFIT_OLLAMA_MODEL로 지정하거나 "
                "--model 로 넘겨라 (설치된 목록은 `llm-models` 명령으로 확인)."
            )
        import requests

        self._requests = requests
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._num_ctx = num_ctx
        self._max_retries = max_retries
        #: 추론(thinking)을 끄는 요청 필드를 쓸 수 있는지. 지원하지 않는
        #: 모델·구버전 서버가 400을 주면 한 번만 끄고 그 뒤로는 안 보낸다.
        self._use_think_flag = True
        self.name = f"ollama/{model}"

    def ask(self, prompt: str, expected_items: int = 1) -> str:
        payload = {
            "model": self._model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {
                "temperature": _TEMPERATURE,
                "num_ctx": self._num_ctx,
                "num_predict": (
                    _LOCAL_OUTPUT_TOKENS_BASE
                    + _LOCAL_OUTPUT_TOKENS_PER_ITEM * max(expected_items, 1)
                ),
            },
        }

        last_error = ""
        for attempt in range(1, self._max_retries + 1):
            # 이 작업의 답은 "3: 없음" 한 줄씩이라 사고 과정이 필요 없다.
            # 켜두면 출력 한도를 사고 과정이 다 먹고 정작 답이 비어서 온다.
            if self._use_think_flag:
                payload["think"] = False
            else:
                payload.pop("think", None)

            try:
                response = self._requests.post(
                    f"{self._base_url}/api/chat", json=payload, timeout=self._timeout
                )
            except self._requests.exceptions.ConnectionError as e:
                raise LlmFatalError(
                    f"Ollama 서버에 연결할 수 없다 ({self._base_url}). "
                    "`ollama serve`로 서버를 띄우거나 Ollama 앱을 실행해라. "
                    f"({e.__class__.__name__})"
                ) from e
            except Exception as e:  # noqa: BLE001 - 타임아웃 등은 재시도 대상
                last_error = f"요청 실패: {e}"
            else:
                if response.status_code == 200:
                    return self._extract_text(response.json())
                if response.status_code == 404:
                    raise LlmFatalError(
                        f"모델 '{self._model}'을(를) 찾을 수 없다. "
                        f"`ollama pull {self._model}`로 먼저 받아라 "
                        "(설치된 목록은 `llm-models` 명령)."
                    )
                last_error = _describe_error(response)
                if response.status_code == 400 and self._use_think_flag:
                    # 이 모델(또는 서버 버전)은 think 옵션을 모른다.
                    # 다음 시도부터 빼고 보낸다.
                    self._use_think_flag = False
                    logger.info("think 옵션 미지원 — 빼고 다시 호출한다 (%s)", last_error)
                    continue
                if response.status_code not in _RETRY_STATUS:
                    raise LlmError(last_error)

            if attempt < self._max_retries:
                logger.warning(
                    "Ollama 호출 실패(%d/%d) — %.1f초 후 재시도: %s",
                    attempt, self._max_retries, _RETRY_BASE_DELAY, last_error,
                )
                time.sleep(_RETRY_BASE_DELAY)

        raise LlmError(f"재시도 {self._max_retries}회 모두 실패 — {last_error}")

    @staticmethod
    def _extract_text(data: dict) -> str:
        message = data.get("message") or {}
        content = (message.get("content") or "").strip()
        if content:
            return content

        # 답이 비었을 때 원인을 정확히 짚어준다. thinking 칸에 내용이 있으면
        # "모델이 생각만 하다 끝난 것"이고, 대응 방법이 전혀 다르다.
        reason = data.get("done_reason", "?")
        thinking = (message.get("thinking") or "").strip()
        if thinking:
            raise LlmAnswerError(
                f"모델이 사고 과정에만 토큰을 다 쓰고 답을 못 냈다 (done_reason={reason}). "
                "--batch를 더 줄이거나, 사고 과정이 적은 모델을 써라 "
                f"(사고 과정 앞부분: {thinking[:100]!r})"
            )
        raise LlmAnswerError(
            f"응답 텍스트가 비어있음 (done_reason={reason}). "
            "length면 출력 한도 부족이니 --batch를 줄여라"
        )


class FakeLlmClient:
    """API 없이 파이프라인만 돌려보는 대역.

    기본값은 전부 "없음"이다 — 실패해도 DB에 아무 매칭도 쓰이지 않는 쪽이
    안전한 기본값이기 때문. `answers`를 주면 그 답(배치 응답 전문)을 순서대로
    돌려준다(테스트용).
    """

    def __init__(self, answers: list[str] | None = None):
        self.name = "fake"
        self._answers = list(answers or [])
        self.calls: list[str] = []

    def ask(self, prompt: str, expected_items: int = 1) -> str:
        self.calls.append(prompt)
        if self._answers:
            return self._answers.pop(0)
        return "\n".join(f"{i}: 없음" for i in range(1, max(expected_items, 1) + 1))


#: 로컬 제공자 별칭. `--provider local`로도 쓸 수 있게 한다.
_LOCAL_PROVIDERS = {"ollama", "local"}


def is_local_provider(provider: str) -> bool:
    return provider.strip().lower() in _LOCAL_PROVIDERS


def create_client(
    provider: str,
    api_key: str = "",
    model: str = "",
    requests_per_minute: int = DEFAULT_REQUESTS_PER_MINUTE,
    base_url: str = DEFAULT_OLLAMA_BASE_URL,
    num_ctx: int = DEFAULT_OLLAMA_NUM_CTX,
) -> LlmClient:
    """제공자 이름으로 클라이언트를 만든다."""
    key = provider.strip().lower()
    if key in _LOCAL_PROVIDERS:
        return OllamaClient(model=model, base_url=base_url, num_ctx=num_ctx)
    if key == "gemini":
        return GeminiClient(
            api_key=api_key, model=model, requests_per_minute=requests_per_minute
        )
    if key == "fake":
        return FakeLlmClient()
    raise LlmFatalError(f"알 수 없는 LLM 제공자: {provider!r} (ollama | gemini | fake)")


def list_available_models(
    provider: str,
    api_key: str = "",
    base_url: str = DEFAULT_OLLAMA_BASE_URL,
) -> list[tuple[str, str]]:
    """쓸 수 있는 모델 목록. (모델명, 설명) 튜플.

    모델명은 계정·설치 상태에 따라 달라진다. 코드에 적힌 기본값이 404가 날 때
    무엇으로 바꿔야 하는지는 이 조회가 유일하게 확실한 답이다.
    """
    key = provider.strip().lower()
    if key in _LOCAL_PROVIDERS:
        return _list_ollama_models(base_url)
    if key == "gemini":
        return _list_gemini_models(api_key)
    raise LlmFatalError(f"모델 목록을 조회할 수 없는 제공자: {provider!r}")


def _list_ollama_models(base_url: str, timeout: float = 15.0) -> list[tuple[str, str]]:
    """로컬에 받아둔 Ollama 모델 목록 (`/api/tags`)."""
    import requests

    url = f"{base_url.rstrip('/')}/api/tags"
    try:
        response = requests.get(url, timeout=timeout)
    except requests.exceptions.ConnectionError as e:
        raise LlmFatalError(
            f"Ollama 서버에 연결할 수 없다 ({base_url}). "
            "`ollama serve`로 서버를 띄우거나 Ollama 앱을 실행해라."
        ) from e
    if response.status_code != 200:
        raise LlmFatalError(_describe_error(response))

    out: list[tuple[str, str]] = []
    for model in response.json().get("models") or []:
        name = str(model.get("name", ""))
        size_gb = float(model.get("size") or 0) / (1024**3)
        details = model.get("details") or {}
        note = f"{size_gb:.1f}GB, {details.get('parameter_size', '?')}"
        out.append((name, note))
    return out


def _list_gemini_models(api_key: str, timeout: float = 30.0) -> list[tuple[str, str]]:
    """이 API 키로 generateContent를 쓸 수 있는 Gemini 모델 목록."""
    if not api_key:
        raise LlmFatalError("Gemini API 키가 없다. MEALFIT_GEMINI_API_KEY를 설정해라.")
    import requests

    out: list[tuple[str, str]] = []
    page_token = ""
    while True:
        params = {"pageSize": 100}
        if page_token:
            params["pageToken"] = page_token
        response = requests.get(
            _GEMINI_LIST_ENDPOINT,
            headers={"x-goog-api-key": api_key},
            params=params,
            timeout=timeout,
        )
        if response.status_code != 200:
            raise LlmFatalError(_describe_error(response))

        data = response.json()
        for model in data.get("models") or []:
            methods = model.get("supportedGenerationMethods") or []
            if "generateContent" not in methods:
                continue
            name = str(model.get("name", "")).removeprefix("models/")
            out.append((name, str(model.get("displayName", ""))))

        page_token = data.get("nextPageToken") or ""
        if not page_token:
            break
    return out


# ─────────────────────────────────────────────────────────────
# 프롬프트 구성 · 응답 파싱
# ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class PromptCandidate:
    """프롬프트에 보여줄 후보 1건.

    실운영(`run_llm_match`)은 DB의 `Candidate`에서, 검증(`validate_with_labels`)은
    라벨링 CSV에서 만든다. 두 경로가 **같은 프롬프트**를 만들어야 검증 결과를
    실운영 성능으로 믿을 수 있으므로, 중간에 이 타입을 하나 둔다.
    """

    food_name: str
    food_code: str = ""
    major_category: str = ""
    #: 식품기원("외식"/"가정식" 등). 같은 요리가 기원별로 중복 수록돼 있는데
    #: 이름만 보여주면 모델이 고를 근거가 없다 — 실제로 `족발`·`골뱅이무침_소면`
    #: 에서 사람은 외식 항목을, 모델은 다른 항목을 골랐다.
    origin: str = ""


@dataclass(frozen=True)
class PromptItem:
    """한 요청에 담기는 메뉴 1건 (메뉴 + 그 메뉴의 후보 목록)."""

    menu_name: str
    restaurant_name: str
    candidates: list[PromptCandidate]


def to_prompt_candidates(candidates: list[Candidate]) -> list[PromptCandidate]:
    return [
        PromptCandidate(
            food_name=c.food_name,
            food_code=c.food_code,
            major_category=c.major_category,
            origin=c.origin,
        )
        for c in candidates
    ]


def build_batch_prompt(items: list[PromptItem]) -> str:
    """메뉴 여러 건을 한 요청에 담는 객관식 프롬프트.

    식당명을 같이 주는 이유: `얼큰깨비어묵`처럼 브랜드 작명이 섞인 메뉴는
    업종 맥락이 있어야 판단이 선다(라벨링 인사이트 3).
    """
    blocks = [_PROMPT_HEADER.format(count=len(items))]
    for index, item in enumerate(items, start=1):
        lines = []
        for i, c in enumerate(item.candidates, start=1):
            # 라벨링 CSV에서 온 후보는 이름 안에 이미 [기원 · 대분류]가 붙어
            # 있으므로 중복해서 붙이지 않는다.
            tags = [t for t in (c.origin, c.major_category) if t]
            suffix = f" [{' · '.join(tags)}]" if tags and "[" not in c.food_name else ""
            lines.append(f"  {i}. {c.food_name}{suffix}")
        blocks.append(
            _PROMPT_ITEM.format(
                index=index,
                menu_name=item.menu_name,
                restaurant=item.restaurant_name or "(알 수 없음)",
                candidate_lines="\n".join(lines),
            )
        )
    return "\n".join(blocks)


#: "1: 3", "1) 없음", "1 - 7" 등을 받아들인다. 모델이 형식을 조금씩 흘려도
#: 답을 버리지 않기 위함.
_ANSWER_LINE = re.compile(r"^\s*(\d+)\s*[:.)\-]\s*(.+?)\s*$")

#: 답 부분에서 첫 번째 정수를 찾는다. "3번", "후보 3" 같은 군더더기 허용.
_NUMBER_PATTERN = re.compile(r"\d+")


def parse_choice(raw: str, candidate_count: int) -> int | None:
    """답 한 칸을 후보 번호(1~N) 또는 None(기권)으로 해석한다.

    범위 밖 숫자는 오류로 올린다 — 후보가 10개인데 12를 골랐다면 그건 기권이
    아니라 지시를 못 따른 것이고, 조용히 기권으로 접어두면 프롬프트가 망가진
    사실이 통계에 묻힌다.
    """
    answer = (raw or "").strip()
    if not answer:
        raise LlmAnswerError("빈 응답")

    lowered = answer.lower()
    if any(word in lowered for word in _ABSTAIN_WORDS):
        return None

    m = _NUMBER_PATTERN.search(answer)
    if m is None:
        raise LlmAnswerError(f"번호도 기권도 아닌 응답: {answer[:100]!r}")

    number = int(m.group())
    if number == 0:  # 라벨링 표기(0 = 정답 없음)를 그대로 쓴 경우
        return None
    if 1 <= number <= candidate_count:
        return number
    raise LlmAnswerError(
        f"후보 범위(1~{candidate_count}) 밖의 번호: {number} (응답 {answer[:100]!r})"
    )


#: 로컬 추론 모델은 <think>…</think>에 사고 과정을 담아 보낸다. 그 안에도
#: "3: 없음" 같은 문장이 섞여 있어서, 지우지 않으면 최종 답 대신 중간 생각을
#: 답으로 읽어버린다.
_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def parse_batch_answers(raw: str, items: list[PromptItem]) -> dict[int, int | None]:
    """배치 응답을 {메뉴번호(1-based): 후보번호 또는 None}으로 푼다.

    빠진 메뉴는 결과에 넣지 않는다 — 조용히 "없음"으로 채우면 모델이 답을
    안 준 것과 기권한 것이 구분되지 않고, 그 상태가 menu_alias에 영구
    기록되어 다시 물어볼 기회조차 사라진다. 빠진 건 실패로 남겨 다음 실행에
    재시도되게 한다.
    """
    body = _THINK_BLOCK.sub("", raw or "")
    if "<think>" in body.lower():
        # 여는 태그만 있고 닫히지 않았다 = 사고 과정을 쓰다가 토큰이 끊긴 것.
        # 최종 답은 아예 나오지 않았으므로 실패로 올려 다음 실행에 재시도한다.
        raise LlmAnswerError(
            "추론(<think>)이 닫히지 않은 채 끊겼다 — 출력 토큰 부족. --batch를 줄여라"
        )

    parsed: dict[int, int | None] = {}
    for line in body.splitlines():
        m = _ANSWER_LINE.match(line)
        if m is None:
            continue
        index = int(m.group(1))
        if not (1 <= index <= len(items)):
            continue
        if index in parsed:
            continue
        try:
            parsed[index] = parse_choice(m.group(2), len(items[index - 1].candidates))
        except LlmAnswerError as e:
            logger.warning("메뉴 %d번 답 해석 실패 — 건너뛴다: %s", index, e)

    if not parsed:
        raise LlmAnswerError(f"응답에서 답을 한 줄도 읽지 못했다: {raw[:200]!r}")
    return parsed


# ─────────────────────────────────────────────────────────────
# menu_alias — LLM 판정 영구 기록 (D-2)
# ─────────────────────────────────────────────────────────────

#: official_food와 마찬가지로 Spring이 모르는 Python 전용 테이블이다.
#: 정규화명이 PK인 이유: 같은 메뉴명이 식당 10곳에 있어도 판정은 하나면 되고,
#: 재실행 때 같은 질문을 다시 하지 않기 위한 캐시 역할도 겸하기 때문.
_CREATE_ALIAS_TABLE = text("""
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
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
""")

#: food_code가 NULL인 행 = "LLM이 없음이라고 판정했다"는 기록이다. 이 행이
#: 있어야 재실행 때 같은 메뉴를 다시 물어보지 않는다.
_UPSERT_ALIAS = text("""
    INSERT INTO menu_alias
        (normalized_name, food_code, matched_by, confidence, model, raw_answer)
    VALUES
        (:normalized_name, :food_code, :matched_by, :confidence, :model, :raw_answer)
    AS new
    ON DUPLICATE KEY UPDATE
        food_code  = new.food_code,
        matched_by = new.matched_by,
        confidence = new.confidence,
        model      = new.model,
        raw_answer = new.raw_answer
""")

_SELECT_ALIAS = text("SELECT normalized_name, food_code FROM menu_alias")

#: 매칭된 alias에 붙일 식약처 이름. 결과를 사람이 눈으로 볼 때 필요하다.
_SELECT_FOOD_NAME = text("SELECT food_name FROM official_food WHERE food_code = :food_code")


def ensure_alias_table(session: Session) -> None:
    session.execute(_CREATE_ALIAS_TABLE)


def load_alias_cache(session: Session) -> dict[str, str | None]:
    """{정규화명: food_code 또는 None}. None은 "LLM이 없음이라 판정" 기록이다."""
    return {
        str(name): (str(code) if code else None)
        for name, code in session.execute(_SELECT_ALIAS).all()
    }


# ─────────────────────────────────────────────────────────────
# 실행
# ─────────────────────────────────────────────────────────────


@dataclass
class LlmMatchResult:
    normalized_name: str
    menu_name: str
    restaurant_name: str
    menu_ids: list[int]
    food_code: str | None = None
    food_name: str | None = None
    raw_answer: str | None = None
    from_cache: bool = False
    decided: bool = False       # LLM(또는 캐시)이 실제로 판정했는가
    error: str | None = None

    @property
    def matched(self) -> bool:
        return self.food_code is not None


@dataclass
class LlmMatchReport:
    total_menus: int = 0            # 필터 통과한 전체 메뉴 수
    rule_matched_menus: int = 0     # 규칙 캐스케이드가 이미 잡은 메뉴 (LLM 대상 아님)
    brand_skipped_menus: int = 0    # 프랜차이즈 매장 메뉴 (브랜드 경로에서만 다룬다)
    target_menus: int = 0           # LLM 대상 메뉴 (규칙 미매칭)
    target_names: int = 0           # 그 메뉴들의 서로 다른 정규화명 수
    asked_batches: int = 0          # 실제 LLM 호출(요청) 수
    asked_names: int = 0            # 그 요청에 담아 물어본 이름 수
    cached: int = 0                 # menu_alias 재사용으로 묻지 않은 이름 수
    no_candidates: int = 0          # 후보가 하나도 없어 묻지 않은 이름 수
    matched_names: int = 0
    abstained_names: int = 0
    failed_names: int = 0
    matched_menus: int = 0          # 매칭된 이름들이 커버하는 메뉴 건수
    applied_menus: int = 0          # --apply로 실제 UPDATE된 메뉴 건수
    skipped_by_limit: int = 0
    aborted_reason: str | None = None

    def summary(self) -> str:
        lines = [
            f"메뉴 {self.total_menus}건 중 규칙 매칭 {self.rule_matched_menus}건"
            + (f", 프랜차이즈 제외 {self.brand_skipped_menus}건" if self.brand_skipped_menus else "")
            + f", LLM 대상 {self.target_menus}건 (서로 다른 이름 {self.target_names}개)",
            f"LLM 호출 {self.asked_batches}회로 이름 {self.asked_names}개 질의 "
            f"(캐시 재사용 {self.cached}개, 후보 없어 생략 {self.no_candidates}개"
            + (f", --limit로 미처리 {self.skipped_by_limit}개" if self.skipped_by_limit else "")
            + ")",
            f"판정: 매칭 {self.matched_names}개 / 없음 {self.abstained_names}개"
            + (f" / 실패 {self.failed_names}개" if self.failed_names else ""),
        ]
        decided = self.matched_names + self.abstained_names
        if decided:
            abstain_rate = self.abstained_names / decided * 100
            lines.append(
                f"기권률 {abstain_rate:.1f}% — 라벨링 실측 기준선은 40%다. "
                "이보다 크게 낮으면 억지 매칭을 의심해야 한다"
            )
        lines.append(
            f"메뉴 기준 추가 매칭: {self.matched_menus}건"
            + (f" (DB 반영 {self.applied_menus}건)" if self.applied_menus else " [집계만 — DB 미반영]")
        )
        if self.aborted_reason:
            lines.append(f"⚠ 중단됨: {self.aborted_reason}")
            lines.append("  이미 받아둔 판정은 menu_alias에 저장돼 있어, 다시 실행하면 이어서 진행된다.")
        return "\n".join(lines)


@dataclass
class _MenuGroup:
    """같은 정규화명을 쓰는 메뉴들. 질문은 1회, 반영은 전부에."""

    normalized_name: str
    menu_name: str
    restaurant_name: str
    menu_ids: list[int] = field(default_factory=list)


def run_llm_match(
    session: Session,
    client: LlmClient,
    apply: bool = False,
    candidate_count: int = 10,
    limit: int = 0,
    batch_size: int = DEFAULT_BATCH_SIZE,
    refresh: bool = False,
    exclude_franchise: bool = False,
    exclude_cafe: bool = False,
    exclude_branch: bool = False,
) -> tuple[LlmMatchReport, list[LlmMatchResult]]:
    """규칙 미매칭 메뉴를 LLM에게 객관식으로 물어본다.

    apply=False면 DB의 menu는 건드리지 않는다. 다만 **menu_alias 기록은 남긴다** —
    같은 질문을 반복해서 호출 비용을 다시 쓰지 않기 위함이다(`--refresh`로 무시).

    limit>0이면 물어볼 이름을 그만큼으로 제한한다. 처음 붙일 때 몇 건으로 답
    품질을 먼저 눈으로 확인하기 위한 옵션이다.
    """
    ensure_alias_table(session)

    brands = load_excluded_brands()
    menu_rows = session.execute(_SELECT_MENUS).all()
    # 프랜차이즈 메뉴는 브랜드 전용 매처가 이미 처리했을 수 있다. 같은 판단을
    # 써야 이미 매칭된 메뉴를 LLM에게 다시 묻고 덮어쓰는 일이 없다.
    matcher_set = build_matcher_set(
        session,
        brands,
        [] if exclude_franchise else [str(r[3]) for r in menu_rows],
    )
    cache = {} if refresh else load_alias_cache(session)
    logger.info("menu_alias 기존 기록 %d건 (재사용 대상)", len(cache))

    # Fake 클라이언트의 답은 기록하지 않는다. 배선 확인용으로 한 번 돌린 "없음"이
    # 캐시에 박히면, 이후 진짜 모델로 실행해도 전부 캐시 적중으로 건너뛰어
    # "호출 0회, 매칭 0건"이 나온다 — 원인을 찾기 매우 어려운 사고다.
    persist = client.name != "fake"
    if not persist:
        logger.info("fake 제공자 — 판정을 menu_alias에 기록하지 않는다 (배선 확인 전용)")

    report = LlmMatchReport()
    groups: dict[str, _MenuGroup] = {}

    for menu_id, name, normalized_name, restaurant_name, cuisine in menu_rows:
        if exclude_franchise and brands and _contains_brand(str(restaurant_name).lower(), brands):
            continue
        if exclude_branch and _BRANCH_SUFFIX.search(str(restaurant_name)):
            continue
        if exclude_cafe and cuisine == _CAFE_CUISINE:
            continue
        if not normalized_name:
            continue

        report.total_menus += 1
        if matcher_set.match(normalized_name, str(restaurant_name)) is not None:
            report.rule_matched_menus += 1
            continue

        # 프랜차이즈 매장 메뉴는 LLM에게 묻지 않는다. 그 브랜드 항목 안에서
        # 못 찾았다는 건 식약처에 그 메뉴가 없다는 뜻이고, 여기서 더 물어봐야
        # 나올 답은 "일반 요리 후보 중 비슷한 것"뿐이다 — 그건 롯데리아 메뉴에
        # 동네 불고기 수치를 붙이는 것과 같다.
        if matcher_set.brand_of(restaurant_name) is not None:
            report.brand_skipped_menus += 1
            continue

        report.target_menus += 1
        group = groups.get(normalized_name)
        if group is None:
            group = _MenuGroup(
                normalized_name=normalized_name,
                menu_name=name,
                restaurant_name=str(restaurant_name),
            )
            groups[normalized_name] = group
        group.menu_ids.append(menu_id)

    report.target_names = len(groups)

    results: dict[str, LlmMatchResult] = {}
    pending: list[tuple[LlmMatchResult, PromptItem]] = []

    # 1단계 — 물어볼 것만 추린다. 캐시 적중·후보 없음은 호출 없이 여기서 끝난다.
    for group in groups.values():
        result = LlmMatchResult(
            normalized_name=group.normalized_name,
            menu_name=group.menu_name,
            restaurant_name=group.restaurant_name,
            menu_ids=list(group.menu_ids),
        )
        results[group.normalized_name] = result

        if group.normalized_name in cache:
            result.food_code = cache[group.normalized_name]
            result.from_cache = True
            result.decided = True
            report.cached += 1
            continue

        candidates = matcher_set.top_candidates(
            group.normalized_name, group.restaurant_name, limit=candidate_count
        )
        if not candidates:
            # 2-gram 검색이 후보를 하나도 못 만든 경우. 물어볼 선택지가 없으므로
            # 호출하지 않고 "없음"으로 기록한다. 기권률 통계에는 넣지 않는다 —
            # LLM의 판단이 아니라 후보 검색의 한계다.
            report.no_candidates += 1
            if persist:
                _record_alias(session, group.normalized_name, None, client.name, "(후보 없음)")
            continue

        if limit and len(pending) >= limit:
            report.skipped_by_limit += 1
            continue

        pending.append(
            (
                result,
                PromptItem(
                    menu_name=group.menu_name,
                    restaurant_name=group.restaurant_name,
                    candidates=to_prompt_candidates(candidates),
                ),
            )
        )

    session.commit()

    batches = [pending[i : i + batch_size] for i in range(0, len(pending), batch_size)]
    logger.info(
        "LLM 대상 %d건(이름 %d개) → 물어볼 %d개를 %d회 호출로 처리한다. 모델: %s",
        report.target_menus, report.target_names, len(pending), len(batches), client.name,
    )

    # 2단계 — 배치로 묻는다.
    consecutive_failures = 0
    for batch_no, batch in enumerate(batches, start=1):
        items = [item for _, item in batch]
        prompt = build_batch_prompt(items)

        try:
            raw = client.ask(prompt, expected_items=len(items))
            answers = parse_batch_answers(raw, items)
            report.asked_batches += 1
            report.asked_names += len(items)
            consecutive_failures = 0
        except LlmFatalError as e:
            # 설정 오류. 남은 배치를 돌아봐야 같은 실패가 반복될 뿐이다.
            report.aborted_reason = f"설정 오류로 중단 — {e}"
            logger.error("%s", report.aborted_reason)
            break
        except LlmError as e:
            consecutive_failures += 1
            report.failed_names += len(items)
            for result, _ in batch:
                result.error = str(e)
            logger.warning("배치 %d/%d 실패: %s", batch_no, len(batches), e)
            if consecutive_failures >= _MAX_CONSECUTIVE_FAILURES:
                report.aborted_reason = (
                    f"연속 {consecutive_failures}회 실패로 중단 — 쿼터 소진일 가능성이 크다. "
                    "--rpm을 낮추거나 시간을 두고 다시 실행해라"
                )
                logger.error("%s", report.aborted_reason)
                break
            continue

        for position, (result, item) in enumerate(batch, start=1):
            if position not in answers:
                # 모델이 이 메뉴 줄을 빼먹었다. 실패로 남겨 다음 실행에 재시도한다.
                report.failed_names += 1
                result.error = "응답에 이 메뉴의 답이 없음"
                continue

            choice = answers[position]
            result.decided = True
            result.raw_answer = ("없음" if choice is None else str(choice))
            if choice is not None:
                picked = item.candidates[choice - 1]
                result.food_code = picked.food_code
                result.food_name = picked.food_name
            if persist:
                _record_alias(
                    session,
                    result.normalized_name,
                    result.food_code,
                    client.name,
                    result.raw_answer,
                )

        # 배치 하나가 끝날 때마다 커밋한다. 수백 건을 도는 동안 한 번이라도
        # 끊기면(Ctrl+C·네트워크·쿼터 소진) 그때까지 쓴 API 호출이 통째로
        # 날아가기 때문 — 커밋해두면 다음 실행이 캐시를 읽고 이어서 진행한다.
        session.commit()
        logger.info("배치 %d/%d 완료 (%d건 판정)", batch_no, len(batches), len(answers))

    # 3단계 — 판정 결과 집계 및 반영.
    for result in results.values():
        if not result.decided:
            continue
        if result.matched:
            report.matched_names += 1
            report.matched_menus += len(result.menu_ids)
            if result.food_name is None:
                result.food_name = _lookup_food_name(session, result.food_code)
            if apply:
                for menu_id in result.menu_ids:
                    session.execute(
                        _UPDATE_MENU,
                        {
                            "food_code": result.food_code,
                            "matched_by": METHOD,
                            "confidence": CONFIDENCE[METHOD],
                            "menu_id": menu_id,
                        },
                    )
                    report.applied_menus += 1
        else:
            report.abstained_names += 1

    session.commit()
    return report, list(results.values())


def _record_alias(
    session: Session,
    normalized_name: str,
    food_code: str | None,
    model: str,
    raw_answer: str | None,
) -> None:
    session.execute(
        _UPSERT_ALIAS,
        {
            "normalized_name": normalized_name,
            "food_code": food_code,
            "matched_by": METHOD,
            # 기권(없음)에는 confidence를 남기지 않는다 — 매칭이 없으니 신뢰도도 없다.
            "confidence": CONFIDENCE[METHOD] if food_code else None,
            "model": model[:60],
            "raw_answer": raw_answer,
        },
    )


def _lookup_food_name(session: Session, food_code: str) -> str | None:
    row = session.execute(_SELECT_FOOD_NAME, {"food_code": food_code}).first()
    return str(row[0]) if row else None


# ─────────────────────────────────────────────────────────────
# 검증 — 사람이 라벨링한 정답과 LLM 답을 맞춰본다
# ─────────────────────────────────────────────────────────────


@dataclass
class LlmValidationReport:
    """`labeling/unmatched_sample.csv`로 LLM을 채점한 결과.

    가장 중요한 숫자는 정확도가 아니라 **`0`(정답 없음) 행에서의 기권률**이다.
    억지로 고르는 모델은 정확도가 높아 보여도 실제 서비스에서는 틀린 영양
    수치를 뿌리게 된다.
    """

    total_rows: int = 0
    skipped_unlabeled: int = 0
    skipped_excluded: int = 0
    failed: int = 0
    asked_batches: int = 0
    aborted_reason: str | None = None

    # 정답이 후보 안에 있던 행 (라벨 1~N)
    inside_total: int = 0
    inside_correct: int = 0
    inside_wrong: int = 0     # 다른 번호를 고름
    inside_missed: int = 0    # 정답이 있는데 기권

    # 정답이 DB에 없던 행 (라벨 0) — 기권이 정답
    none_total: int = 0
    none_abstained: int = 0
    none_picked: int = 0

    # 정답이 DB엔 있지만 후보 밖이던 행 (라벨 food_code) — 역시 기권이 최선
    outside_total: int = 0
    outside_abstained: int = 0
    outside_picked: int = 0

    wrong_examples: list[str] = field(default_factory=list)

    def summary(self) -> str:
        graded = self.inside_total + self.none_total + self.outside_total
        if graded == 0:
            return (
                "채점된 행이 없다 ('정답' 칸이 비어있거나, 호출이 전부 실패했다)."
                + (f"\n⚠ 중단됨: {self.aborted_reason}" if self.aborted_reason else "")
            )

        lines = [
            f"채점 {graded}건 / LLM 호출 {self.asked_batches}회 "
            f"(전체 {self.total_rows}행 중 미기입 {self.skipped_unlabeled}건, "
            f"제외 {self.skipped_excluded}건"
            + (f", 답 못 받음 {self.failed}건" if self.failed else "")
            + ")",
            "",
            f"[후보 안에 정답 있음] {self.inside_total}건",
        ]
        if self.inside_total:
            acc = self.inside_correct / self.inside_total * 100
            lines += [
                f"  - 정답 맞춤: {self.inside_correct}건 ({acc:.1f}%)",
                f"  - 다른 번호 선택: {self.inside_wrong}건",
                f"  - 기권해버림(놓침): {self.inside_missed}건",
            ]

        lines.append(f"[식약처에 정답 없음(0)] {self.none_total}건  ← 기권이 정답")
        if self.none_total:
            rate = self.none_abstained / self.none_total * 100
            lines += [
                f"  - 없음이라 답함: {self.none_abstained}건 ({rate:.1f}%)",
                f"  - 억지로 고름(오매칭 위험): {self.none_picked}건",
            ]

        lines.append(f"[정답이 후보 밖에 있었음] {self.outside_total}건  ← 기권이 최선")
        if self.outside_total:
            rate = self.outside_abstained / self.outside_total * 100
            lines += [
                f"  - 없음이라 답함: {self.outside_abstained}건 ({rate:.1f}%)",
                f"  - 엉뚱한 후보를 고름: {self.outside_picked}건",
            ]

        false_positive = self.none_picked + self.outside_picked + self.inside_wrong
        lines += [
            "",
            f"오매칭 총계(정답이 아닌 후보를 고른 경우): {false_positive}건",
            "이 숫자가 크면 프롬프트가 기권을 충분히 허용하지 않고 있다는 뜻이다.",
        ]
        if self.wrong_examples:
            lines.append("오답 예시:")
            lines += [f"    {e}" for e in self.wrong_examples]
        if self.aborted_reason:
            lines.append(f"⚠ 중단됨: {self.aborted_reason}")
        return "\n".join(lines)


@dataclass
class _LabelRow:
    """채점 대상 1행. gold는 라벨 원문 그대로 들고 판정 시점에 해석한다."""

    menu_name: str
    gold: str
    item: PromptItem


def validate_with_labels(
    input_path: str | Path,
    client: LlmClient,
    candidate_count: int = 10,
    batch_size: int = DEFAULT_BATCH_SIZE,
    max_examples: int = 20,
) -> LlmValidationReport:
    """라벨링 CSV로 LLM을 채점한다. DB를 쓰지 않는다.

    후보 목록을 DB에서 다시 뽑지 않고 **CSV에 적힌 후보를 그대로** 쓴다.
    사람이 라벨링할 때 본 목록과 LLM이 보는 목록이 같아야 `정답=3`이라는
    라벨이 의미를 갖기 때문이다. 정규화 규칙을 바꿨다면 CSV를 다시
    내보낸(`export-labels`) 뒤에 채점해야 한다.

    실운영(`run_llm_match`)과 **같은 배치 프롬프트**를 쓴다 — 프롬프트가 다르면
    여기서 나온 점수를 실제 성능으로 믿을 수 없다.
    """
    report = LlmValidationReport()

    with open(input_path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    targets: list[_LabelRow] = []
    for row in rows:
        report.total_rows += 1
        gold = (row.get("정답") or "").strip()
        if not gold:
            report.skipped_unlabeled += 1
            continue
        if gold in _EXCLUDE_TOKENS:
            report.skipped_excluded += 1
            continue

        candidates = [
            PromptCandidate(food_name=name, food_code=(row.get(f"코드{i}") or "").strip())
            for i in range(1, candidate_count + 1)
            if (name := (row.get(f"후보{i}") or "").strip())
        ]
        if not candidates:
            report.skipped_excluded += 1
            continue

        # 숫자 라벨인데 후보 범위를 벗어나면 채점할 수 없다 (CSV와 --candidates 불일치).
        if gold.isdigit() and int(gold) > len(candidates):
            report.skipped_excluded += 1
            continue

        targets.append(
            _LabelRow(
                menu_name=row.get("메뉴명", ""),
                gold=gold,
                item=PromptItem(
                    menu_name=row.get("메뉴명", ""),
                    restaurant_name=row.get("식당명", ""),
                    candidates=candidates,
                ),
            )
        )

    batches = [targets[i : i + batch_size] for i in range(0, len(targets), batch_size)]
    logger.info("채점 대상 %d건을 %d회 호출로 물어본다", len(targets), len(batches))

    consecutive_failures = 0
    for batch_no, batch in enumerate(batches, start=1):
        items = [t.item for t in batch]
        try:
            raw = client.ask(build_batch_prompt(items), expected_items=len(items))
            answers = parse_batch_answers(raw, items)
            report.asked_batches += 1
            consecutive_failures = 0
        except LlmFatalError as e:
            report.aborted_reason = f"설정 오류로 중단 — {e}"
            logger.error("%s", report.aborted_reason)
            break
        except LlmError as e:
            consecutive_failures += 1
            report.failed += len(items)
            logger.warning("배치 %d/%d 실패: %s", batch_no, len(batches), e)
            if consecutive_failures >= _MAX_CONSECUTIVE_FAILURES:
                report.aborted_reason = f"연속 {consecutive_failures}회 실패로 중단 — {e}"
                logger.error("%s", report.aborted_reason)
                break
            continue

        for position, target in enumerate(batch, start=1):
            if position not in answers:
                report.failed += 1
                continue
            _grade_one(report, target, answers[position], max_examples)

        logger.info("배치 %d/%d 채점 완료", batch_no, len(batches))

    return report


def _grade_one(
    report: LlmValidationReport,
    target: _LabelRow,
    choice: int | None,
    max_examples: int,
) -> None:
    """라벨 1행 채점. 라벨 종류(숫자 / 0 / food_code)에 따라 기준이 다르다."""
    picked_name = target.item.candidates[choice - 1].food_name if choice else None
    gold = target.gold

    if gold == "0":
        report.none_total += 1
        if choice is None:
            report.none_abstained += 1
        else:
            report.none_picked += 1
            _add_example(
                report, max_examples,
                f"{target.menu_name}: 정답 '없음'인데 {choice}번({picked_name}) 선택",
            )
        return

    if _FOOD_CODE_PATTERN.match(gold):
        report.outside_total += 1
        if choice is None:
            report.outside_abstained += 1
        else:
            report.outside_picked += 1
            _add_example(
                report, max_examples,
                f"{target.menu_name}: 정답은 후보 밖({gold})인데 {choice}번({picked_name}) 선택",
            )
        return

    try:
        gold_number = int(gold)
    except ValueError:
        report.skipped_excluded += 1
        return

    report.inside_total += 1
    if choice == gold_number:
        report.inside_correct += 1
    elif choice is None:
        report.inside_missed += 1
        _add_example(
            report, max_examples, f"{target.menu_name}: 정답 {gold_number}번인데 기권"
        )
    else:
        report.inside_wrong += 1
        _add_example(
            report, max_examples,
            f"{target.menu_name}: 정답 {gold_number}번인데 {choice}번({picked_name}) 선택",
        )


def _add_example(report: LlmValidationReport, max_examples: int, line: str) -> None:
    if len(report.wrong_examples) < max_examples:
        report.wrong_examples.append(line)
