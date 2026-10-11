import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path


@dataclass
class ShoppingListItem:
    name: str
    quantity: Decimal
    unit: str | None = None


class InsufficientListedQuantity(ValueError):
    pass


class ShoppingListUnitMismatch(ValueError):
    pass


@dataclass(frozen=True)
class PurchaseRecord:
    name: str
    quantity: Decimal
    purchased_at: datetime
    unit: str | None = None


class ShoppingListStore:
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
                    CREATE TABLE IF NOT EXISTS shopping_list (
                        user_id INTEGER NOT NULL,
                        item_key TEXT NOT NULL,
                        name TEXT NOT NULL,
                        quantity TEXT NOT NULL,
                        PRIMARY KEY (user_id, item_key)
                    )
                    """
                )
                columns = {
                    row[1]
                    for row in connection.execute(
                        "PRAGMA table_info(shopping_list)"
                    ).fetchall()
                }
                if "unit" not in columns:
                    connection.execute(
                        "ALTER TABLE shopping_list ADD COLUMN unit TEXT"
                    )
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS purchase_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        item_key TEXT NOT NULL,
                        name TEXT NOT NULL,
                        quantity TEXT NOT NULL,
                        unit TEXT,
                        purchased_at TEXT NOT NULL
                    )
                    """
                )
                history_columns = {
                    row[1]
                    for row in connection.execute(
                        "PRAGMA table_info(purchase_history)"
                    ).fetchall()
                }
                if "unit" not in history_columns:
                    connection.execute(
                        "ALTER TABLE purchase_history ADD COLUMN unit TEXT"
                    )
                connection.execute(
                    """
                    CREATE INDEX IF NOT EXISTS
                        idx_purchase_history_user_purchased_at
                    ON purchase_history (user_id, purchased_at DESC)
                    """
                )

    def get_items(self, user_id: int) -> list[ShoppingListItem]:
        self._validate_user_id(user_id)
        with closing(sqlite3.connect(self.database_path)) as connection:
            rows = connection.execute(
                """
                SELECT name, quantity, unit
                FROM shopping_list
                WHERE user_id = ?
                ORDER BY rowid
                """,
                (user_id,),
            ).fetchall()
        return [
            ShoppingListItem(name=name, quantity=Decimal(quantity), unit=unit)
            for name, quantity, unit in rows
        ]

    def add_quantity(
        self,
        user_id: int,
        name: str,
        quantity: Decimal,
        unit: str | None = None,
    ) -> Decimal:
        return self.add_quantities(user_id, [(name, quantity, unit)])[0]

    def add_quantities(
        self,
        user_id: int,
        items: list[tuple[str, Decimal, str | None]],
    ) -> list[Decimal]:
        self._validate_user_id(user_id)
        if not items:
            raise ValueError("É necessário informar ao menos um item.")
        normalized_items = [
            (
                self._validate_name(name),
                self._validate_quantity(quantity),
                self._validate_unit(unit),
            )
            for name, quantity, unit in items
        ]
        totals: list[Decimal] = []
        with closing(sqlite3.connect(self.database_path)) as connection:
            with connection:
                connection.execute("BEGIN IMMEDIATE")
                for name, quantity, unit in normalized_items:
                    item_key = name.casefold()
                    row = connection.execute(
                        """
                        SELECT quantity, unit
                        FROM shopping_list
                        WHERE user_id = ? AND item_key = ?
                        """,
                        (user_id, item_key),
                    ).fetchone()
                    if row is None:
                        total_quantity = quantity
                        connection.execute(
                            """
                            INSERT INTO shopping_list
                                (user_id, item_key, name, quantity, unit)
                            VALUES (?, ?, ?, ?, ?)
                            """,
                            (user_id, item_key, name, str(total_quantity), unit),
                        )
                    else:
                        total_quantity = Decimal(row[0]) + quantity
                        self._validate_quantity(total_quantity)
                        saved_unit = row[1]
                        if (
                            unit is not None
                            and saved_unit is not None
                            and unit.casefold() != saved_unit.casefold()
                        ):
                            raise ShoppingListUnitMismatch
                        resolved_unit = saved_unit if unit is None else unit
                        connection.execute(
                            """
                            UPDATE shopping_list
                            SET quantity = ?, unit = ?
                            WHERE user_id = ? AND item_key = ?
                            """,
                            (str(total_quantity), resolved_unit, user_id, item_key),
                        )
                    totals.append(total_quantity)
        return totals

    def mark_purchased(
        self,
        user_id: int,
        name: str,
        quantity: Decimal,
    ) -> Decimal | None:
        self._validate_user_id(user_id)
        name = self._validate_name(name)
        quantity = self._validate_quantity(quantity)

        item_key = name.casefold()
        with closing(sqlite3.connect(self.database_path)) as connection:
            with connection:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    """
                    SELECT quantity, unit
                    FROM shopping_list
                    WHERE user_id = ? AND item_key = ?
                    """,
                    (user_id, item_key),
                ).fetchone()
                if row is None:
                    return None

                listed_quantity = Decimal(row[0])
                unit = row[1]
                if quantity > listed_quantity:
                    raise InsufficientListedQuantity

                connection.execute(
                    """
                    INSERT INTO purchase_history
                        (user_id, item_key, name, quantity, unit, purchased_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user_id,
                        item_key,
                        name,
                        str(quantity),
                        unit,
                        datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    ),
                )
                remaining_quantity = listed_quantity - quantity
                if remaining_quantity == 0:
                    connection.execute(
                        """
                        DELETE FROM shopping_list
                        WHERE user_id = ? AND item_key = ?
                        """,
                        (user_id, item_key),
                    )
                else:
                    connection.execute(
                        """
                        UPDATE shopping_list
                        SET quantity = ?
                        WHERE user_id = ? AND item_key = ?
                        """,
                        (str(remaining_quantity), user_id, item_key),
                    )
        return remaining_quantity

    def get_history(self, user_id: int, days: int = 30) -> list[PurchaseRecord]:
        self._validate_user_id(user_id)
        if not 1 <= days <= 365:
            raise ValueError("O período do histórico deve estar entre 1 e 365 dias.")
        cutoff = (
            datetime.now(timezone.utc) - timedelta(days=days)
        ).isoformat(timespec="seconds")
        with closing(sqlite3.connect(self.database_path)) as connection:
            rows = connection.execute(
                """
                SELECT name, quantity, purchased_at, unit
                FROM purchase_history
                WHERE user_id = ? AND purchased_at >= ?
                ORDER BY purchased_at DESC, id DESC
                LIMIT 20
                """,
                (user_id, cutoff),
            ).fetchall()
        return [
            PurchaseRecord(
                name=name,
                quantity=Decimal(quantity),
                purchased_at=datetime.fromisoformat(purchased_at),
                unit=unit,
            )
            for name, quantity, purchased_at, unit in rows
        ]

    @staticmethod
    def _validate_name(name: str) -> str:
        normalized = name.strip()
        if (
            not normalized
            or len(normalized) > 100
            or any(ord(character) < 32 for character in normalized)
        ):
            raise ValueError("O nome do item deve ter de 1 a 100 caracteres válidos.")
        return normalized

    @staticmethod
    def _validate_quantity(quantity: Decimal) -> Decimal:
        if (
            not quantity.is_finite()
            or quantity <= 0
            or quantity.adjusted() >= 12
            or quantity.as_tuple().exponent < -6
            or len(quantity.as_tuple().digits) > 18
        ):
            raise ValueError(
                "A quantidade deve ser positiva, menor que 1000000000000 "
                "e ter no máximo seis casas decimais."
            )
        return quantity

    @staticmethod
    def _validate_unit(unit: str | None) -> str | None:
        if unit is None:
            return None
        normalized = unit.strip()
        if (
            not normalized
            or len(normalized) > 20
            or any(
                not (character.isalnum() or character in "._-")
                for character in normalized
            )
        ):
            raise ValueError("A unidade informada é inválida.")
        return normalized

    @staticmethod
    def _validate_user_id(user_id: int) -> None:
        if user_id <= 0:
            raise ValueError("O ID do usuário deve ser positivo.")
