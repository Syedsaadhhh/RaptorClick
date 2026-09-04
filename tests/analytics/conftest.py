"""Shared pytest fixtures for the analytics test suite."""

from __future__ import annotations

from decimal import Decimal

import pytest

from raptor.analytics import DEFAULT_CONFIG, analyse
from raptor.analytics.samples import (
    balanced_portfolio,
    concentrated_portfolio,
    empty_portfolio,
    equity_curve,
    levered_portfolio,
    market_neutral_portfolio,
    sample_bids,
)


@pytest.fixture
def config():
    return DEFAULT_CONFIG


@pytest.fixture
def balanced():
    return balanced_portfolio()


@pytest.fixture
def concentrated():
    return concentrated_portfolio()


@pytest.fixture
def levered():
    return levered_portfolio()


@pytest.fixture
def neutral():
    return market_neutral_portfolio()


@pytest.fixture
def empty():
    return empty_portfolio()


@pytest.fixture
def bids():
    return sample_bids()


@pytest.fixture
def curve():
    return equity_curve()


@pytest.fixture
def balanced_report(balanced, bids):
    return analyse(balanced, bids)
