import datetime

from stocks.services.validation import ValidationService


def test_validation_clean_data(test_config):
    """Verifies that clean and consistent daily price records pass validation."""
    service = ValidationService(test_config)

    clean_row = {
        "trading_date": datetime.date(2026, 5, 29),
        "open": 100.0,
        "high": 105.0,
        "low": 98.0,
        "close": 102.0,
        "adj_close": 102.0,
        "volume": 100000,
    }

    validated = service.validate_prices("TEST.NS", [clean_row], [])
    assert len(validated) == 1
    assert validated[0] == clean_row


def test_validation_logical_inconsistencies(test_config):
    """Verifies that illogical, negative, and missing parameter records are discarded."""
    service = ValidationService(test_config)

    # 1. Null Close Value
    null_row = {
        "trading_date": datetime.date(2026, 5, 29),
        "open": 100.0,
        "high": 105.0,
        "low": 98.0,
        "close": None,
        "adj_close": 102.0,
        "volume": 100000,
    }

    # 2. Negative Open Price
    negative_row = {
        "trading_date": datetime.date(2026, 5, 29),
        "open": -100.0,
        "high": 105.0,
        "low": 98.0,
        "close": 102.0,
        "adj_close": 102.0,
        "volume": 100000,
    }

    # 3. High Less Than Low
    illogical_high_low = {
        "trading_date": datetime.date(2026, 5, 29),
        "open": 100.0,
        "high": 90.0,
        "low": 98.0,
        "close": 102.0,
        "adj_close": 102.0,
        "volume": 100000,
    }

    # 4. Open Higher than High
    illogical_open = {
        "trading_date": datetime.date(2026, 5, 29),
        "open": 110.0,
        "high": 105.0,
        "low": 98.0,
        "close": 102.0,
        "adj_close": 102.0,
        "volume": 100000,
    }

    validated = service.validate_prices("TEST.NS", [null_row, negative_row, illogical_high_low, illogical_open], [])
    assert len(validated) == 0


def test_validation_anomalies_and_actions(test_config):
    """Verifies that large price shifts are flagged as warnings, but justified when concurrent actions occur."""
    service = ValidationService(test_config)

    row_prev = {
        "trading_date": datetime.date(2026, 5, 28),
        "open": 100.0,
        "high": 105.0,
        "low": 98.0,
        "close": 100.0,
        "adj_close": 100.0,
        "volume": 100000,
    }

    # Simulate a massive 60% price drop (100 -> 40)
    row_curr = {
        "trading_date": datetime.date(2026, 5, 29),
        "open": 40.0,
        "high": 42.0,
        "low": 39.0,
        "close": 40.0,
        "adj_close": 40.0,
        "volume": 100000,
    }

    # Case A: No corporate actions (triggers anomaly spike logs, but keeps record)
    validated = service.validate_prices("TEST.NS", [row_prev, row_curr], [])
    assert len(validated) == 2

    # Case B: Corporate action present (justifies price drop, logs justification event)
    action = {
        "action_date": datetime.date(2026, 5, 29),
        "action_type": "SPLIT",
        "value": 0.4,  # 5:2 split ratio representation
    }
    validated_with_action = service.validate_prices("TEST.NS", [row_prev, row_curr], [action])
    assert len(validated_with_action) == 2
