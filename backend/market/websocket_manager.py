"""
Central Websocket Manager.

Owns broker tick ingestion.

Flow:

Broker WebSocket
      |
      v
on_tick()
      |
      v
TickNormalizer
      |
      v
update_live_quote()
      |
      v
registered consumers
"""

from __future__ import annotations

import logging
from typing import Callable, List

from backend.market.live_quotes import update_live_quote
from backend.market.tick_normalizer import TickNormalizer


logger = logging.getLogger(__name__)


class WebsocketManager:

    def __init__(self):

        self.running = False

        self.consumers: List[
            Callable[[dict], None]
        ] = []

    def start(self):

        self.running = True

        logger.info(
            "WebsocketManager started"
        )

    def stop(self):

        self.running = False

        logger.info(
            "WebsocketManager stopped"
        )

    def register_consumer(
        self,
        callback: Callable[[dict], None],
    ):

        if callback not in self.consumers:

            self.consumers.append(
                callback
            )

    def unregister_consumer(
        self,
        callback,
    ):

        if callback in self.consumers:

            self.consumers.remove(
                callback
            )

    def on_kotak_tick(
        self,
        raw_tick: dict,
    ):

        try:

            tick = (
                TickNormalizer
                .normalize_kotak(raw_tick)
            )

            quote = update_live_quote(
                tick
            )

            self._dispatch(
                quote
            )

            return quote

        except Exception:

            logger.exception(
                "Failed processing Kotak tick"
            )

            return None

    def _dispatch(
        self,
        quote: dict,
    ):

        for consumer in list(
            self.consumers
        ):

            try:

                consumer(
                    quote
                )

            except Exception:

                logger.exception(
                    "Live quote consumer failed"
                )
