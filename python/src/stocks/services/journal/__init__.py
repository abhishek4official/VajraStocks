"""Trade journal domain (V2.0 spec M3) — the product's memory of decisions.

Logs entries/exits and realized P&L, and computes per-setup auto-review (win rate,
expectancy in R, R distribution) so a trader can answer "did my setups actually work?".
All metrics are computed from logged trades — never fabricated.
"""
