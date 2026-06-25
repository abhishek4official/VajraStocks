"""Real, reproducible backtest engine (V2.0 spec M2).

Replaces the deleted fabricated backtester. All metrics are pure functions of the inputs;
the engine produces identical output for identical input. No constants masquerade as
results — see metrics.py for the verified building blocks.
"""
