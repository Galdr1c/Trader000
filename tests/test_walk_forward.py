from __future__ import annotations

import json

from src.backtesting.walk_forward import (
    WalkForwardOptimizer,
    generate_windows,
)


def test_generate_windows_are_chronological_and_non_overlapping() -> None:
    windows = generate_windows(total_size=30, train_size=10, test_size=5)

    assert windows == [
        (0, 10, 10, 15),
        (5, 15, 15, 20),
        (10, 20, 20, 25),
        (15, 25, 25, 30),
    ]
    assert all(train_end <= test_start for _, train_end, test_start, _ in windows)


def test_optimizer_selects_best_eligible_training_parameters() -> None:
    calls = []

    def runner(candles, parameters):
        calls.append((len(candles), parameters["min_signal_score"]))
        score = parameters["min_signal_score"]
        return {
            "trades": 5,
            "net_profit_pct": score,
            "sharpe_ratio": score,
            "max_drawdown_pct": 2.0,
        }

    report = WalkForwardOptimizer(runner).run(
        candles=list(range(20)),
        parameter_grid={"min_signal_score": [7.0, 9.0]},
        train_size=10,
        test_size=5,
        min_trades=2,
    )

    assert report["windows"][0]["selected_parameters"] == {"min_signal_score": 9.0}
    assert report["windows"][0]["out_of_sample"]["sharpe_ratio"] == 9.0
    assert calls[0][0] == 10


def test_optimizer_filters_candidates_below_minimum_trades() -> None:
    def runner(candles, parameters):
        score = parameters["min_signal_score"]
        return {
            "trades": 1 if score == 9.0 else 4,
            "net_profit_pct": score,
            "sharpe_ratio": score,
            "max_drawdown_pct": 2.0,
        }

    report = WalkForwardOptimizer(runner).run(
        candles=list(range(15)),
        parameter_grid={"min_signal_score": [7.0, 9.0]},
        train_size=10,
        test_size=5,
        min_trades=2,
    )

    assert report["windows"][0]["selected_parameters"] == {"min_signal_score": 7.0}


def test_optimizer_records_failed_window_without_losing_report() -> None:
    def runner(candles, parameters):
        raise RuntimeError("backtest failed")

    report = WalkForwardOptimizer(runner).run(
        candles=list(range(15)),
        parameter_grid={"min_signal_score": [8.0]},
        train_size=10,
        test_size=5,
    )

    assert report["windows"][0]["status"] == "failed"
    assert "backtest failed" in report["windows"][0]["error"]
    assert report["summary"]["completed_windows"] == 0


def test_optimizer_aggregates_only_out_of_sample_metrics() -> None:
    def runner(candles, parameters):
        is_test_window = len(candles) == 5
        return {
            "trades": 2 if is_test_window else 100,
            "net_profit_pct": 3.0 if is_test_window else 99.0,
            "sharpe_ratio": 1.0 if is_test_window else 50.0,
            "max_drawdown_pct": 4.0 if is_test_window else 1.0,
        }

    report = WalkForwardOptimizer(runner).run(
        candles=list(range(20)),
        parameter_grid={"min_signal_score": [8.0]},
        train_size=10,
        test_size=5,
    )

    assert report["summary"]["trades"] == 4
    assert report["summary"]["average_net_profit_pct"] == 3.0
    assert report["summary"]["average_sharpe_ratio"] == 1.0
    assert report["summary"]["max_drawdown_pct"] == 4.0


def test_optimizer_writes_json_report_atomically(tmp_path) -> None:
    def runner(candles, parameters):
        return {
            "trades": 2,
            "net_profit_pct": 1.0,
            "sharpe_ratio": 0.5,
            "max_drawdown_pct": 3.0,
        }

    output = tmp_path / "report.json"
    report = WalkForwardOptimizer(runner).run(
        candles=list(range(15)),
        parameter_grid={"min_signal_score": [8.0]},
        train_size=10,
        test_size=5,
        output_path=output,
    )

    assert json.loads(output.read_text(encoding="utf-8")) == report
    assert not output.with_suffix(".json.tmp").exists()
