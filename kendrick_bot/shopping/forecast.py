from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class StockForecast:
    expected_use: Decimal
    remaining: Decimal
    shortage: Decimal
    days_of_stock: Decimal


def forecast_stock(
    stock: Decimal | None,
    daily_use: Decimal | None,
    days_until_shop: int,
) -> StockForecast:
    if stock is None or daily_use is None:
        raise ValueError("Estoque e consumo diário são obrigatórios.")
    if stock < 0:
        raise ValueError("O estoque não pode ser negativo.")
    if daily_use <= 0:
        raise ValueError("O consumo diário deve ser maior que zero.")
    if days_until_shop <= 0:
        raise ValueError("Os dias até a próxima compra devem ser maiores que zero.")

    expected_use = daily_use * days_until_shop
    shortage = max(Decimal(0), expected_use - stock)
    remaining = max(Decimal(0), stock - expected_use)
    return StockForecast(
        expected_use=expected_use,
        remaining=remaining,
        shortage=shortage,
        days_of_stock=stock / daily_use,
    )
