"""Registry + param-schema contract tests for the swing strategies."""

from stocks.services.strategies.registry import (
    DEFAULT_STRATEGY_ID,
    get_strategy,
    list_strategies,
    strategy_meta,
)


def test_registry_lists_swing_strategies():
    ids = [s.id for s in list_strategies()]
    for expected in ("minervini", "high52", "weinstein", "momentum", "dual"):
        assert expected in ids
    assert DEFAULT_STRATEGY_ID in ids


def test_get_strategy_roundtrip_and_unknown():
    s = get_strategy("minervini")
    assert s is not None and s.name and s.version
    assert get_strategy("does_not_exist") is None


def test_param_schema_has_typed_defaults():
    s = get_strategy("minervini")
    schema = s.param_schema
    assert "use_market_filter" in schema and schema["use_market_filter"]["type"] == "boolean"
    assert "timeframe" in schema and schema["timeframe"]["type"] == "string"
    assert "stop_atr_mult" in schema and schema["stop_atr_mult"]["type"] == "number"
    for spec in schema.values():
        assert "default" in spec and "group" in spec


def test_resolve_params_coerces_types():
    s = get_strategy("minervini")
    p = s.resolve_params({"stop_atr_mult": "2.5", "use_market_filter": "false", "ma_fast_days": "40"})
    assert p["stop_atr_mult"] == 2.5
    assert p["use_market_filter"] is False
    assert p["ma_fast_days"] == 40


def test_make_force_market_ok_disables_filter():
    s = get_strategy("minervini")
    strat = s.make(force_market_ok=True)
    assert strat.parameters["use_market_filter"] is False


def test_strategy_meta_serializable_keys():
    meta = strategy_meta(get_strategy("weinstein"))
    assert set(meta) >= {"id", "name", "version", "description", "param_schema", "data_needs"}
