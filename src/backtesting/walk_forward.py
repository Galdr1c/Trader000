"""Chronological walk-forward optimization."""

from __future__ import annotations

import itertools
import json
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any


def generate_windows(
    total_size: int,
    train_size: int,
    test_size: int,
) -> list[tuple[int, int, int, int]]:
    """Return rolling train/test index boundaries without look-ahead."""
    if train_size <= 0 or test_size <= 0:
        raise ValueError("train_size and test_size must be positive")
    windows = []
    train_start = 0
    while train_start + train_size + test_size <= total_size:
        train_end = train_start + train_size
        test_end = train_end + test_size
        windows.append((train_start, train_end, train_end, test_end))
        train_start += test_size
    return windows


def expand_grid(parameter_grid: dict[str, Sequence[Any]]) -> list[dict[str, Any]]:
    """Expand a bounded parameter grid in deterministic key order."""
    keys = list(parameter_grid)
    if not keys:
        return [{}]
    return [
        dict(zip(keys, values, strict=True))
        for values in itertools.product(*(parameter_grid[key] for key in keys))
    ]


class WalkForwardOptimizer:
    def __init__(
        self,
        runner: Callable[[Sequence[Any], dict[str, Any]], dict[str, Any]],
    ) -> None:
        self._runner = runner

    def run(
        self,
        *,
        candles: Sequence[Any],
        parameter_grid: dict[str, Sequence[Any]],
        train_size: int,
        test_size: int,
        objective: str = "sharpe_ratio",
        min_trades: int = 1,
        output_path: Path | None = None,
    ) -> dict[str, Any]:
        results = []
        candidates = expand_grid(parameter_grid)

        for train_start, train_end, test_start, test_end in generate_windows(
            len(candles),
            train_size,
            test_size,
        ):
            window = {
                "train": {"start": train_start, "end": train_end},
                "test": {"start": test_start, "end": test_end},
            }
            try:
                eligible = []
                for parameters in candidates:
                    metrics = self._runner(candles[train_start:train_end], parameters)
                    if int(metrics.get("trades", 0)) >= min_trades:
                        eligible.append((float(metrics.get(objective, 0.0)), parameters, metrics))
                if not eligible:
                    raise ValueError("no parameter candidate met the minimum trade count")

                _, selected, training_metrics = max(eligible, key=lambda item: item[0])
                out_of_sample = self._runner(candles[test_start:test_end], selected)
                window.update({
                    "status": "completed",
                    "selected_parameters": selected,
                    "in_sample": training_metrics,
                    "out_of_sample": out_of_sample,
                })
            except Exception as exc:
                window.update({"status": "failed", "error": str(exc)})
            results.append(window)

        completed = [
            window["out_of_sample"]
            for window in results
            if window["status"] == "completed"
        ]
        count = len(completed)
        summary = {
            "completed_windows": count,
            "failed_windows": len(results) - count,
            "trades": sum(int(item.get("trades", 0)) for item in completed),
            "average_net_profit_pct": (
                sum(float(item.get("net_profit_pct", 0.0)) for item in completed) / count
                if count else 0.0
            ),
            "average_sharpe_ratio": (
                sum(float(item.get("sharpe_ratio", 0.0)) for item in completed) / count
                if count else 0.0
            ),
            "max_drawdown_pct": max(
                (float(item.get("max_drawdown_pct", 0.0)) for item in completed),
                default=0.0,
            ),
        }
        report = {"windows": results, "summary": summary}
        if output_path is not None:
            self._write_report(output_path, report)
        return report

    @staticmethod
    def _write_report(output_path: Path, report: dict[str, Any]) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = output_path.with_suffix(f"{output_path.suffix}.tmp")
        temporary.write_text(
            json.dumps(report, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        temporary.replace(output_path)
