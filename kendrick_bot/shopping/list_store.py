import sqlite3
from contextlib import closing
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path


@dataclass
class ShoppingListItem:
    name: str
    quantity: Decimal


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

    def get_items(self, user_id: int) -> list[ShoppingListItem]:
        self._validate_user_id(user_id)
        with closing(sqlite3.connect(self.database_path)) as connection:
            rows = connection.execute(
                """
                SELECT name, quantity
                FROM shopping_list
                WHERE user_id = ?
                ORDER BY rowid
                """,
                (user_id,),
            ).fetchall()
        return [
            ShoppingListItem(name=name, quantity=Decimal(quantity))
            for name, quantity in rows
        ]

    def add_quantity(
        self,
        user_id: int,
        name: str,
        quantity: Decimal,
    ) -> Decimal:
        self._validate_user_id(user_id)
        if not name.strip():
            raise ValueError("O nome do item não pode ficar vazio.")
        if not quantity.is_finite() or quantity <= 0:
            raise ValueError("A quantidade deve ser um número positivo e finito.")

        item_key = name.casefold()
        with closing(sqlite3.connect(self.database_path)) as connection:
            with connection:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    """
                    SELECT quantity
                    FROM shopping_list
                    WHERE user_id = ? AND item_key = ?
                    """,
                    (user_id, item_key),
                ).fetchone()
                if row is None:
                    total_quantity = quantity
                    connection.execute(
                        """
                        INSERT INTO shopping_list (user_id, item_key, name, quantity)
                        VALUES (?, ?, ?, ?)
                        """,
                        (user_id, item_key, name, str(total_quantity)),
                    )
                else:
                    total_quantity = Decimal(row[0]) + quantity
                    connection.execute(
                        """
                        UPDATE shopping_list
                        SET quantity = ?
                        WHERE user_id = ? AND item_key = ?
                        """,
                        (str(total_quantity), user_id, item_key),
                    )
        return total_quantity

    @staticmethod
    def _validate_user_id(user_id: int) -> None:
        if user_id <= 0:
            raise ValueError("O ID do usuário deve ser positivo.")
