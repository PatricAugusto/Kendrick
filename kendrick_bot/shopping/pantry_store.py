import sqlite3
from contextlib import closing
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path


@dataclass(frozen=True)
class PantryItem:
    name: str
    quantity: Decimal
    unit: str
    daily_consumption: Decimal | None


class PantryItemNotFound(ValueError):
    pass


class PantryUnitMismatch(ValueError):
    pass


class PantryInvalidQuantity(ValueError):
    pass


class PantryInsufficientStock(ValueError):
    def __init__(self, available_quantity: Decimal, unit: str) -> None:
        super().__init__()
        self.available_quantity = available_quantity
        self.unit = unit


class PantryStore:
    def __init__(self, database_path: str | Path | None = None) -> None:
        self.database_path = (
            Path(database_path)
            if database_path is not None
            else Path(__file__).resolve().parents[2] / "kendrick.sqlite3"
        )
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.database_path)) as connection:
            with connection:
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS pantry (
                        user_id INTEGER NOT NULL,
                        item_key TEXT NOT NULL,
                        name TEXT NOT NULL,
                        quantity TEXT NOT NULL,
                        unit TEXT NOT NULL,
                        daily_consumption TEXT,
                        PRIMARY KEY (user_id, item_key)
                    )
                    """
                )

    def get_items(self, user_id: int) -> list[PantryItem]:
        self._validate_user_id(user_id)
        with closing(sqlite3.connect(self.database_path)) as connection:
            rows = connection.execute(
                """
                SELECT name, quantity, unit, daily_consumption
                FROM pantry
                WHERE user_id = ?
                ORDER BY rowid
                """,
                (user_id,),
            ).fetchall()
        return [
            PantryItem(
                name=name,
                quantity=Decimal(quantity),
                unit=unit,
                daily_consumption=(
                    Decimal(daily_consumption)
                    if daily_consumption is not None
                    else None
                ),
            )
            for name, quantity, unit, daily_consumption in rows
        ]

    def set_stock(
        self,
        user_id: int,
        name: str,
        quantity: Decimal,
        unit: str,
    ) -> PantryItem:
        self._validate_user_id(user_id)
        self._validate_item(name)
        self._validate_quantity(quantity, allow_zero=True)
        name = name.strip()
        unit = unit.strip()
        self._validate_unit(unit)
        item_key = name.casefold()

        with closing(sqlite3.connect(self.database_path)) as connection:
            with connection:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    """
                    SELECT name, unit, daily_consumption
                    FROM pantry
                    WHERE user_id = ? AND item_key = ?
                    """,
                    (user_id, item_key),
                ).fetchone()
                if row is None:
                    connection.execute(
                        """
                        INSERT INTO pantry
                            (user_id, item_key, name, quantity, unit, daily_consumption)
                        VALUES (?, ?, ?, ?, ?, NULL)
                        """,
                        (user_id, item_key, name, str(quantity), unit),
                    )
                    item_name = name
                    saved_unit = unit
                else:
                    item_name, saved_unit, daily_consumption = row
                    if saved_unit.casefold() != unit.casefold():
                        raise PantryUnitMismatch
                    connection.execute(
                        """
                        UPDATE pantry
                        SET quantity = ?
                        WHERE user_id = ? AND item_key = ?
                        """,
                        (str(quantity), user_id, item_key),
                    )
        return PantryItem(
            name=item_name,
            quantity=quantity,
            unit=saved_unit,
            daily_consumption=(
                Decimal(daily_consumption)
                if row is not None and daily_consumption is not None
                else None
            ),
        )

    def set_daily_consumption(
        self,
        user_id: int,
        name: str,
        daily_consumption: Decimal,
        unit: str,
    ) -> PantryItem:
        self._validate_user_id(user_id)
        self._validate_item(name)
        self._validate_quantity(daily_consumption, allow_zero=False)
        name = name.strip()
        unit = unit.strip()
        self._validate_unit(unit)
        item_key = name.casefold()

        with closing(sqlite3.connect(self.database_path)) as connection:
            with connection:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    """
                    SELECT name, quantity, unit
                    FROM pantry
                    WHERE user_id = ? AND item_key = ?
                    """,
                    (user_id, item_key),
                ).fetchone()
                if row is None:
                    raise PantryItemNotFound

                item_name, quantity, saved_unit = row
                if saved_unit.casefold() != unit.casefold():
                    raise PantryUnitMismatch
                connection.execute(
                    """
                    UPDATE pantry
                    SET daily_consumption = ?
                    WHERE user_id = ? AND item_key = ?
                    """,
                    (str(daily_consumption), user_id, item_key),
                )
        return PantryItem(
            name=item_name,
            quantity=Decimal(quantity),
            unit=saved_unit,
            daily_consumption=daily_consumption,
        )

    def consume_stock(
        self,
        user_id: int,
        name: str,
        quantity: Decimal,
    ) -> PantryItem:
        self._validate_user_id(user_id)
        self._validate_item(name)
        self._validate_quantity(quantity, allow_zero=False)
        item_key = name.strip().casefold()

        with closing(sqlite3.connect(self.database_path)) as connection:
            with connection:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    """
                    SELECT name, quantity, unit, daily_consumption
                    FROM pantry
                    WHERE user_id = ? AND item_key = ?
                    """,
                    (user_id, item_key),
                ).fetchone()
                if row is None:
                    raise PantryItemNotFound

                item_name, current_quantity, unit, daily_consumption = row
                remaining_quantity = Decimal(current_quantity) - quantity
                if remaining_quantity < 0:
                    raise PantryInsufficientStock(
                        Decimal(current_quantity),
                        unit,
                    )
                connection.execute(
                    """
                    UPDATE pantry
                    SET quantity = ?
                    WHERE user_id = ? AND item_key = ?
                    """,
                    (str(remaining_quantity), user_id, item_key),
                )

        return PantryItem(
            name=item_name,
            quantity=remaining_quantity,
            unit=unit,
            daily_consumption=(
                Decimal(daily_consumption)
                if daily_consumption is not None
                else None
            ),
        )

    def remove_item(self, user_id: int, name: str) -> bool:
        self._validate_user_id(user_id)
        self._validate_item(name)
        name = name.strip()
        item_key = name.casefold()
        with closing(sqlite3.connect(self.database_path)) as connection:
            with connection:
                cursor = connection.execute(
                    """
                    DELETE FROM pantry
                    WHERE user_id = ? AND item_key = ?
                    """,
                    (user_id, item_key),
                )
        return cursor.rowcount > 0

    @staticmethod
    def _validate_user_id(user_id: int) -> None:
        if user_id <= 0:
            raise ValueError("O ID do usuário deve ser positivo.")

    @staticmethod
    def _validate_item(name: str) -> None:
        if not name.strip() or len(name.strip()) > 100 or any(
            ord(character) < 32 for character in name
        ):
            raise ValueError("O nome deve ter de 1 a 100 caracteres válidos.")

    @staticmethod
    def _validate_quantity(quantity: Decimal, *, allow_zero: bool) -> None:
        if (
            not quantity.is_finite()
            or quantity < 0
            or (not allow_zero and quantity == 0)
        ):
            raise PantryInvalidQuantity
        if quantity != 0 and (
            quantity.adjusted() >= 12
            or quantity.as_tuple().exponent < -6
            or len(quantity.as_tuple().digits) > 18
        ):
            raise PantryInvalidQuantity

    @staticmethod
    def _validate_unit(unit: str) -> None:
        if (
            not unit.strip()
            or len(unit.strip()) > 20
            or any(not (character.isalnum() or character in "._-") for character in unit)
        ):
            raise ValueError(
                "A unidade deve ter de 1 a 20 letras, números, ponto, hífen ou sublinhado."
            )
