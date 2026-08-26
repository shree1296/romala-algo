"""
End-to-End Live Data Pipeline.

Broker Tick
    ->
WebsocketManager
    ->
TickNormalizer
    ->
LIVE_QUOTES
    ->
Pipeline Consumers
"""

from __future__ import annotations

from backend.market.websocket_manager import (
    WebsocketManager,
)


class LiveDataPipeline:

    def __init__(self):

        self.websocket_manager = (
            WebsocketManager()
        )

    def start(self):

        self.websocket_manager.start()

    def stop(self):

        self.websocket_manager.stop()

    def register_market_consumer(
        self,
        callback,
    ):

        self.websocket_manager.register_consumer(
            callback
        )

    def on_kotak_tick(
        self,
        tick: dict,
    ):

        return (
            self.websocket_manager
            .on_kotak_tick(tick)
        )
