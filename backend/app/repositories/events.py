"""Repositorio para la persistencia de eventos en DynamoDB."""

import time
from collections.abc import Callable, Mapping, Sequence
from typing import Any


class UnprocessedEventsError(Exception):
    """Indica que DynamoDB dejó eventos pendientes tras agotar los reintentos."""

    def __init__(self, pending_count: int, attempts: int) -> None:
        self.pending_count = pending_count
        self.attempts = attempts

        super().__init__(
            f"DynamoDB dejó {pending_count} eventos sin procesar "
            f"después de {attempts} intentos."
        )


class EventsRepository:
    """Gestiona la escritura por lotes de eventos en DynamoDB."""

    MAX_BATCH_SIZE = 25

    def __init__(
        self,
        client: Any,
        table_name: str,
        max_retries: int = 5,
        initial_backoff_seconds: float = 0.5,
        max_backoff_seconds: float = 8.0,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not table_name:
            raise ValueError("table_name no puede estar vacío.")

        if max_retries < 0:
            raise ValueError("max_retries no puede ser negativo.")

        if initial_backoff_seconds < 0:
            raise ValueError(
                "initial_backoff_seconds no puede ser negativo."
            )

        if max_backoff_seconds < 0:
            raise ValueError("max_backoff_seconds no puede ser negativo.")

        self.client = client
        self.table_name = table_name
        self.max_retries = max_retries
        self.initial_backoff_seconds = initial_backoff_seconds
        self.max_backoff_seconds = max_backoff_seconds
        self.sleep = sleep

    def save_many(self, events: Sequence[Mapping[str, Any]]) -> None:
        """Guarda eventos en lotes y reintenta los elementos no procesados.

        Args:
            events: Colección de eventos en formato compatible con DynamoDB.

        Raises:
            UnprocessedEventsError: si quedan eventos pendientes al agotar
                los reintentos.
            Exception: si el cliente DynamoDB genera un error.
        """
        if not events:
            return

        for start in range(0, len(events), self.MAX_BATCH_SIZE):
            batch = events[start : start + self.MAX_BATCH_SIZE]
            self._write_batch(batch)

    def _write_batch(
        self,
        events: Sequence[Mapping[str, Any]],
    ) -> None:
        """Escribe un lote y reintenta únicamente los elementos pendientes."""
        pending_items = [
            {"PutRequest": {"Item": dict(event)}}
            for event in events
        ]

        attempts = 0

        while pending_items:
            response = self.client.batch_write_item(
                RequestItems={
                    self.table_name: pending_items,
                }
            )

            unprocessed_items = response.get("UnprocessedItems", {})
            pending_items = unprocessed_items.get(self.table_name, [])

            if not pending_items:
                return

            if attempts >= self.max_retries:
                raise UnprocessedEventsError(
                    pending_count=len(pending_items),
                    attempts=attempts + 1,
                )

            delay = min(
                self.initial_backoff_seconds * (2**attempts),
                self.max_backoff_seconds,
            )

            if delay > 0:
                self.sleep(delay)

            attempts += 1
