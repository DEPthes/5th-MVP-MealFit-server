"""app/crawler/parsers.py 단위 테스트. 브라우저 불필요."""

from app.crawler.parsers import dedupe_menus, parse_menu_block, parse_menu_row_text, parse_price
from app.model.raw import RawMenu


class TestParsePrice:
    def test_comma_won(self):
        assert parse_price("9,000원") == 9000

    def test_plain_number(self):
        assert parse_price("9000") == 9000

    def test_number_with_space_and_won(self):
        assert parse_price("9000 원") == 9000

    def test_won_symbol_prefix(self):
        assert parse_price("₩9,000") == 9000

    def test_price_range_uses_first_group(self):
        # 범위 표현까지 다루는 건 8번 파이프라인 몫 — 첫 숫자만 취한다.
        assert parse_price("10,000원~15,000원") == 10000

    def test_none_input(self):
        assert parse_price(None) is None

    def test_empty_string(self):
        assert parse_price("") is None

    def test_no_digits_text(self):
        assert parse_price("가격문의") is None

    def test_zero_token_treated_as_no_price(self):
        assert parse_price("0원") is None

    def test_dash_only(self):
        assert parse_price("-") is None


class TestParseMenuBlock:
    def test_name_and_price(self):
        menu = parse_menu_block("김치찌개 (2인분)", "9,000원")
        assert menu == RawMenu(name="김치찌개 (2인분)", price=9000)

    def test_name_only_no_price(self):
        menu = parse_menu_block("오늘의 특선", "가격문의")
        assert menu == RawMenu(name="오늘의 특선", price=None)

    def test_strips_surrounding_whitespace_and_newlines(self):
        menu = parse_menu_block("  참치김밥\n", "4,500원")
        assert menu.name == "참치김밥"
        assert menu.price == 4500

    def test_none_name_returns_none(self):
        assert parse_menu_block(None, "9,000원") is None

    def test_whitespace_only_name_returns_none(self):
        assert parse_menu_block("   \n  ", "9,000원") is None

    def test_price_text_none_is_allowed(self):
        menu = parse_menu_block("비빔밥", None)
        assert menu == RawMenu(name="비빔밥", price=None)

    def test_returns_raw_menu_instance(self):
        menu = parse_menu_block("냉면", "8000")
        assert isinstance(menu, RawMenu)


class TestParseMenuRowText:
    def test_two_lines_name_then_price(self):
        menu = parse_menu_row_text("김치찌개\n9,000원")
        assert menu == RawMenu(name="김치찌개", price=9000)

    def test_won_symbol_price_line(self):
        menu = parse_menu_row_text("된장찌개\n₩8,500")
        assert menu == RawMenu(name="된장찌개", price=8500)

    def test_single_line_no_price_detected(self):
        # 한 줄뿐이면 가격 줄로 분리하지 않고 전체를 이름으로 본다.
        menu = parse_menu_row_text("오늘의 특선")
        assert menu == RawMenu(name="오늘의 특선", price=None)

    def test_name_containing_digits_not_mistaken_for_price(self):
        menu = parse_menu_row_text("2인분 세트\n가격문의")
        assert menu.name == "2인분 세트"
        assert menu.price is None

    def test_multiple_name_lines_joined(self):
        menu = parse_menu_row_text("런치\nA세트\n12,000원")
        assert menu.name == "런치 A세트"
        assert menu.price == 12000

    def test_sold_out_placeholder_excluded_from_name(self):
        menu = parse_menu_row_text("한우 스테이크\n품절")
        assert menu == RawMenu(name="한우 스테이크", price=None)

    def test_market_price_placeholder_excluded_from_name(self):
        menu = parse_menu_row_text("광어회\n시가")
        assert menu == RawMenu(name="광어회", price=None)

    def test_none_input(self):
        assert parse_menu_row_text(None) is None

    def test_empty_string(self):
        assert parse_menu_row_text("") is None

    def test_whitespace_only(self):
        assert parse_menu_row_text("   \n   ") is None


class TestDedupeMenus:
    def test_exact_duplicate_name_and_price_removed(self):
        menus = [RawMenu(name="김치찌개", price=9000), RawMenu(name="김치찌개", price=9000)]
        result = dedupe_menus(menus)
        assert result == [RawMenu(name="김치찌개", price=9000)]

    def test_same_name_different_price_both_kept(self):
        menus = [RawMenu(name="김치찌개", price=9000), RawMenu(name="김치찌개", price=12000)]
        result = dedupe_menus(menus)
        assert result == menus

    def test_different_names_same_price_both_kept(self):
        menus = [RawMenu(name="김치찌개", price=9000), RawMenu(name="된장찌개", price=9000)]
        result = dedupe_menus(menus)
        assert result == menus

    def test_first_occurrence_order_preserved(self):
        a = RawMenu(name="A", price=1000)
        b = RawMenu(name="B", price=2000)
        result = dedupe_menus([a, b, a])
        assert result == [a, b]

    def test_none_price_duplicates_removed(self):
        menus = [RawMenu(name="시가 메뉴", price=None), RawMenu(name="시가 메뉴", price=None)]
        result = dedupe_menus(menus)
        assert result == [RawMenu(name="시가 메뉴", price=None)]

    def test_empty_list(self):
        assert dedupe_menus([]) == []

    def test_no_duplicates_returns_all(self):
        menus = [RawMenu(name="A", price=1000), RawMenu(name="B", price=2000)]
        assert dedupe_menus(menus) == menus
