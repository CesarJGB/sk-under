"""Formato y unicidad de la identidad de instalación generada."""

from __future__ import annotations

import re

import pytest

from app.native.identity import (
    GeneratedIdentity,
    generate_distro_id,
    generate_identity,
    generate_unique_id,
    is_generated_distro,
    is_generated_unique,
)


def test_generated_distro_is_uuid_v4():
    values = {generate_distro_id() for _ in range(50)}
    assert len(values) == 50
    for value in values:
        assert is_generated_distro(value)
        assert re.fullmatch(
            r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}",
            value,
        )


def test_generated_unique_matches_observed_device_code():
    values = {generate_unique_id() for _ in range(50)}
    assert len(values) == 50
    for value in values:
        assert is_generated_unique(value)
        assert value.startswith("xiaomioutseas_")
        assert len(value) == len("xiaomioutseas_") + 16


def test_generated_pair_has_no_relation_to_another_pair():
    first = generate_identity()
    second = generate_identity()
    assert first != second
    assert isinstance(first, GeneratedIdentity)
    assert is_generated_distro(first.distro_id)
    assert is_generated_unique(first.unique_id)


@pytest.mark.parametrize("prefix", ["", "A", "with space", "x" * 25, "ñ"])
def test_invalid_prefix_is_rejected(prefix):
    with pytest.raises(ValueError):
        generate_unique_id(prefix)


@pytest.mark.parametrize("value", ["", "linux-device", "xiaomioutseas_XYZ", "xiaomioutseas_" + "a" * 15])
def test_invalid_generated_values_are_not_accepted(value):
    assert not is_generated_unique(value)


@pytest.mark.parametrize("value", ["", "not-a-uuid", "12345678-1234-1234-9234-123456789abc"])
def test_non_v4_is_not_treated_as_generated(value):
    assert not is_generated_distro(value)
