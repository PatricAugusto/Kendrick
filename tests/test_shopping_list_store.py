from decimal import Decimal

import pytest

from kendrick_bot.shopping.list_store import (
    InsufficientListedQuantity,
    ShoppingListItem,
    ShoppingListStore,
)
from kendrick_bot.shopping.pantry_store import (
    PantryInvalidQuantity,
    PantryItem,
    PantryItemNotFound,
    PantryStore,
    PantryUnitMismatch,
)


def test_store_keeps_items_after_reopening_database(tmp_path) -> None:
    database_path = tmp_path / "kendrick.sqlite3"
    store = ShoppingListStore(database_path)

    store.add_quantity(123, "Tomates", Decimal("1.25"))
    reopened_store = ShoppingListStore(database_path)

    assert reopened_store.get_items(123) == [
        ShoppingListItem(name="Tomates", quantity=Decimal("1.25"))
    ]


def test_items_are_separate_per_user(tmp_path) -> None:
    store = ShoppingListStore(tmp_path / "kendrick.sqlite3")
    store.add_quantity(123, "arroz", Decimal("2"))

    assert store.get_items(456) == []


def test_add_quantity_accumulates_case_insensitively(tmp_path) -> None:
    store = ShoppingListStore(tmp_path / "kendrick.sqlite3")

    assert store.add_quantity(123, "Tomates", Decimal("1.5")) == Decimal("1.5")
    assert store.add_quantity(123, "tomates", Decimal("2")) == Decimal("3.5")
    assert store.get_items(123) == [
        ShoppingListItem(name="Tomates", quantity=Decimal("3.5"))
    ]


def test_mark_purchased_subtracts_part_of_listed_quantity(tmp_path) -> None:
    store = ShoppingListStore(tmp_path / "kendrick.sqlite3")
    store.add_quantity(123, "tomates", Decimal("3"))

    remaining = store.mark_purchased(123, "TOMATES", Decimal("1.5"))

    assert remaining == Decimal("1.5")
    assert store.get_items(123) == [
        ShoppingListItem(name="tomates", quantity=Decimal("1.5"))
    ]


def test_marking_full_quantity_removes_item(tmp_path) -> None:
    store = ShoppingListStore(tmp_path / "kendrick.sqlite3")
    store.add_quantity(123, "arroz", Decimal("2"))

    assert store.mark_purchased(123, "arroz", Decimal("2")) == Decimal("0")
    assert store.get_items(123) == []


def test_mark_purchased_rejects_quantity_greater_than_listed(tmp_path) -> None:
    store = ShoppingListStore(tmp_path / "kendrick.sqlite3")
    store.add_quantity(123, "arroz", Decimal("2"))

    with pytest.raises(InsufficientListedQuantity):
        store.mark_purchased(123, "arroz", Decimal("3"))

    assert store.get_items(123) == [
        ShoppingListItem(name="arroz", quantity=Decimal("2"))
    ]


def test_mark_purchased_returns_none_for_unknown_item(tmp_path) -> None:
    store = ShoppingListStore(tmp_path / "kendrick.sqlite3")

    assert store.mark_purchased(123, "arroz", Decimal("1")) is None


def test_pantry_persists_stock_and_daily_consumption(tmp_path) -> None:
    database_path = tmp_path / "kendrick.sqlite3"
    store = PantryStore(database_path)
    store.set_stock(123, "Arroz", Decimal("2.5"), "kg")
    store.set_daily_consumption(123, "arroz", Decimal("0.1"), "KG")

    reopened_store = PantryStore(database_path)

    assert reopened_store.get_items(123) == [
        PantryItem(
            name="Arroz",
            quantity=Decimal("2.5"),
            unit="kg",
            daily_consumption=Decimal("0.1"),
        )
    ]


def test_pantry_schema_setup_preserves_existing_shopping_list(tmp_path) -> None:
    database_path = tmp_path / "kendrick.sqlite3"
    shopping_store = ShoppingListStore(database_path)
    shopping_store.add_quantity(123, "arroz", Decimal("1"))

    PantryStore(database_path)

    assert shopping_store.get_items(123) == [
        ShoppingListItem(name="arroz", quantity=Decimal("1"))
    ]


def test_pantry_is_isolated_per_user(tmp_path) -> None:
    store = PantryStore(tmp_path / "kendrick.sqlite3")
    store.set_stock(123, "arroz", Decimal("2"), "kg")

    assert store.get_items(456) == []


def test_pantry_rejects_unit_mismatch_without_changing_saved_data(tmp_path) -> None:
    store = PantryStore(tmp_path / "kendrick.sqlite3")
    store.set_stock(123, "arroz", Decimal("2"), "kg")
    store.set_daily_consumption(123, "arroz", Decimal("0.1"), "kg")

    with pytest.raises(PantryUnitMismatch):
        store.set_stock(123, "arroz", Decimal("3"), "unidades")

    with pytest.raises(PantryUnitMismatch):
        store.set_daily_consumption(123, "arroz", Decimal("1"), "unidades")

    assert store.get_items(123) == [
        PantryItem(
            name="arroz",
            quantity=Decimal("2"),
            unit="kg",
            daily_consumption=Decimal("0.1"),
        )
    ]


def test_pantry_requires_existing_item_before_setting_consumption(tmp_path) -> None:
    store = PantryStore(tmp_path / "kendrick.sqlite3")

    with pytest.raises(PantryItemNotFound):
        store.set_daily_consumption(123, "arroz", Decimal("0.1"), "kg")


@pytest.mark.parametrize(
    ("quantity", "unit"),
    [
        (Decimal("-1"), "kg"),
        (Decimal("NaN"), "kg"),
        (Decimal("1e100"), "kg"),
        (Decimal("0.0000001"), "kg"),
        (Decimal("1"), ""),
        (Decimal("1"), "kg/dia"),
    ],
)
def test_pantry_rejects_invalid_stock_values(
    tmp_path,
    quantity: Decimal,
    unit: str,
) -> None:
    store = PantryStore(tmp_path / "kendrick.sqlite3")

    with pytest.raises((ValueError, PantryInvalidQuantity)):
        store.set_stock(123, "arroz", quantity, unit)


def test_pantry_rejects_zero_daily_consumption(tmp_path) -> None:
    store = PantryStore(tmp_path / "kendrick.sqlite3")
    store.set_stock(123, "arroz", Decimal("2"), "kg")

    with pytest.raises(PantryInvalidQuantity):
        store.set_daily_consumption(123, "arroz", Decimal("0"), "kg")


def test_pantry_accepts_zero_stock_and_removes_item(tmp_path) -> None:
    store = PantryStore(tmp_path / "kendrick.sqlite3")
    store.set_stock(123, "arroz", Decimal("0"), "kg")

    assert store.remove_item(123, "ARROZ")
    assert store.get_items(123) == []
    assert not store.remove_item(123, "arroz")
