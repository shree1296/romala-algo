"""
Basic Kotak live pipeline validation.
"""

from backend.market.live_quotes import (
    get_live_quote,
)

from backend.market.websocket_manager import (
    WebsocketManager,
)


def test_kotak_tick_pipeline():

    manager = WebsocketManager()

    received = []

    manager.register_consumer(
        lambda quote: received.append(quote)
    )

    manager.start()

    raw_tick = {
        "tk": "12345",
        "ts": "TEST_SYMBOL",
        "e": "nse_fo",
        "ltp": "25000.50",
        "oi": "1000",
        "bp": "25000.00",
        "sp": "25001.00",
    }

    quote = manager.on_kotak_tick(
        raw_tick
    )

    assert quote is not None

    assert quote["token"] == "12345"

    assert quote["exchange"] == "nse_fo"

    assert quote["ltp"] == 25000.50

    cached = get_live_quote(
        "nse_fo",
        "12345",
    )

    assert cached is not None

    assert len(received) == 1
