from decimal import Decimal

import pytest

from kendrick_bot.shopping.forecast import forecast_stock


def test_forecast_tomatoes_last_exactly_until_next_shop() -> None:
    forecast = forecast_stock(
        stock=Decimal("3"),
        daily_use=Decimal("1"),
        days_until_shop=3,
    )

    assert forecast.expected_use == Decimal("3")
    assert forecast.remaining == Decimal("0")
    assert forecast.shortage == Decimal("0")
    assert forecast.days_of_stock == Decimal("3")


def test_forecast_calculates_shortage() -> None:
    forecast = forecast_stock(
        stock=Decimal("3"),
        daily_use=Decimal("1"),
        days_until_shop=4,
    )

    assert forecast.expected_use == Decimal("4")
    assert forecast.remaining == Decimal("0")
    assert forecast.shortage == Decimal("1")


def test_forecast_calculates_surplus() -> None:
    forecast = forecast_stock(
        stock=Decimal("5"),
        daily_use=Decimal("1"),
        days_until_shop=3,
    )

    assert forecast.remaining == Decimal("2")
    assert forecast.shortage == Decimal("0")


@pytest.mark.parametrize(
    ("stock", "daily_use", "days_until_shop"),
    [
        (Decimal("-1"), Decimal("1"), 3),
        (Decimal("3"), Decimal("0"), 3),
        (Decimal("3"), Decimal("1"), 0),
    ],
)
def test_forecast_rejects_invalid_values(
    stock: Decimal,
    daily_use: Decimal,
    days_until_shop: int,
) -> None:
    with pytest.raises(ValueError):
        forecast_stock(stock, daily_use, days_until_shop)
