"""크롤러가 산출하는 원시 수집 DTO.

이 모듈의 dataclass들은 7번(수집)과 8번(정규화·적재) 사이의 계약서 역할을 한다.
따라서 다음 원칙을 지킨다.

* **가공하지 않는다.** 소문자화·공백 정리·단위 변환 등 일체의 정규화는
  8번 시트의 ``Normalizer`` 책임이다. 여기서는 소스에서 읽은 원문을 그대로 담는다.
* **검증하지 않는다.** 필수값 누락(상호·주소·URL) 판정 역시 ``Normalizer``가 한다.
  수집 단계에서 예외를 던지면 한 건의 결함이 배치 전체를 중단시킬 수 있다.
* **도메인을 모른다.** ``Cuisine``/``FoodType`` enum, 영양 정보 필드는 존재하지 않는다.
* **불변이다.** ``frozen=True``로 수집 이후 값이 바뀌는 사고를 차단한다.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace


@dataclass(frozen=True, slots=True)
class RawMenu:
    """소스에서 읽은 메뉴 한 줄의 원문."""

    #: 메뉴명 원문. 예) "김치찌개 (2인분)", "런치 A세트"
    name: str

    #: 가격(원). "가격문의"처럼 숫자가 아니거나 파싱 실패 시 None.
    price: int | None = None


@dataclass(frozen=True, slots=True)
class RawRestaurant:
    """크롤러 산출물. Spring의 ``CrawledRestaurant``에 대응한다.

    ``cuisine``·``normalized_name``·``food_types``·``nutrition``처럼 가공이 필요한
    필드는 의도적으로 없다. 전부 8번 파이프라인이 채운다.
    """

    #: 상호 원문
    name: str

    #: 주소 원문
    address: str

    #: 소스의 업종 표기 원문. 예) "한식 > 곱창"
    #: 파이프라인이 이 문자열을 Cuisine enum으로 매핑한다.
    raw_category: str

    #: 원본 상세 URL. restaurant 테이블의 UNIQUE 컬럼이자 upsert 키이므로
    #: 소스 안에서 식당을 유일하게 가리키는 정규 URL이어야 한다.
    #: (조회 시점마다 달라지는 세션 파라미터 등은 소스 구현체가 제거해서 넘긴다)
    source_url: str

    #: 위도. 상세 페이지에서 못 읽으면 None (파이프라인이 주소로 보정)
    latitude: float | None = None

    #: 경도
    longitude: float | None = None

    #: 원시 메뉴 목록. 메뉴 섹션이 없는 식당은 빈 튜플.
    #: frozen dataclass의 불변성을 끝까지 유지하기 위해 list가 아닌 tuple을 쓴다.
    menus: tuple[RawMenu, ...] = field(default_factory=tuple)

    def with_menus(self, menus: list[RawMenu] | tuple[RawMenu, ...]) -> RawRestaurant:
        """메뉴만 교체한 새 인스턴스를 돌려준다.

        상세 페이지 파싱이 '식당 정보 → 메뉴 탭 이동 → 메뉴 파싱' 두 단계로
        나뉘는 소스에서, 먼저 만든 객체에 메뉴를 붙일 때 사용한다.
        frozen dataclass이므로 직접 대입 대신 이 메서드를 쓴다.
        """
        return replace(self, menus=tuple(menus))

    @property
    def menu_count(self) -> int:
        """로그·리포트용 메뉴 개수."""
        return len(self.menus)

    def __str__(self) -> str:  # 로그 가독성용
        return f"{self.name}({self.raw_category}) menus={self.menu_count} <{self.source_url}>"


@dataclass(frozen=True, slots=True)
class CrawlTarget:
    """한 번의 수집 실행이 다룰 대상.

    CLI 인자(``--area``, ``--keyword``, ``--max-count``)가 그대로 매핑된다.
    """

    #: 지역 키워드. 예) "강남역"
    area: str

    #: 추가 검색어(선택). 예) "샐러드"
    keyword: str | None = None

    #: 수집 상한. 과도 수집과 장시간 실행을 막는 안전장치.
    max_count: int = 50

    @property
    def query(self) -> str:
        """소스 검색창에 넣을 문자열. 예) "강남역 샐러드"."""
        return f"{self.area} {self.keyword}" if self.keyword else self.area
