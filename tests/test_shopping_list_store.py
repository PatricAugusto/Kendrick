from decimal import Decimal

from kendrick_bot.shopping.list_store import ShoppingListItem, ShoppingListStore


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
