"""Jesse strategy entry point for the shared SVTR signal engine."""

from __future__ import annotations

from jesse.strategies import Strategy

from src.backtesting.jesse_adapter import SVTRSignalAdapter


class SVTR(Strategy):
    def _evaluation(self):
        ccxt_candles = [
            [timestamp, open_, high, low, close, volume]
            for timestamp, open_, close, high, low, volume in self.candles
        ]
        return SVTRSignalAdapter().evaluate(
            ccxt_candles,
            min_signal_score=float(self.hp.get("min_signal_score", 8.0)),
            adx_threshold=int(self.hp.get("adx_threshold", 25)),
            atr_multiplier=float(self.hp.get("atr_multiplier", 2.5)),
            max_loss_pct=float(self.hp.get("max_loss_pct", 4.0)),
            min_tp=float(self.hp.get("min_tp", 2.0)),
            max_tp=float(self.hp.get("max_tp", 5.5)),
        )

    def should_long(self) -> bool:
        return self._evaluation().direction == "long"

    def should_short(self) -> bool:
        return self._evaluation().direction == "short"

    def go_long(self) -> None:
        evaluation = self._evaluation()
        quantity = self.balance * 0.1 / self.price
        self.buy = quantity, self.price
        self.stop_loss = quantity, evaluation.max_loss_price
        self.take_profit = quantity, self.price * (1 + evaluation.dynamic_tp / 100)

    def go_short(self) -> None:
        evaluation = self._evaluation()
        quantity = self.balance * 0.1 / self.price
        self.sell = quantity, self.price
        self.stop_loss = quantity, evaluation.max_loss_price
        self.take_profit = quantity, self.price * (1 - evaluation.dynamic_tp / 100)

    def should_cancel_entry(self) -> bool:
        return False

    def hyperparameters(self) -> list[dict]:
        return [
            {"name": "min_signal_score", "type": float, "min": 7.0, "max": 10.0, "default": 8.0},
            {"name": "adx_threshold", "type": int, "min": 15, "max": 35, "default": 25},
            {"name": "atr_multiplier", "type": float, "min": 1.5, "max": 4.0, "default": 2.5},
            {"name": "max_loss_pct", "type": float, "min": 1.0, "max": 6.0, "default": 4.0},
            {"name": "min_tp", "type": float, "min": 1.0, "max": 4.0, "default": 2.0},
            {"name": "max_tp", "type": float, "min": 3.0, "max": 8.0, "default": 5.5},
        ]
