import pytest

from running_agent.metrics import calculate_average


def test_calculate_average():
    result = calculate_average([10, 20, 30])

    assert result == 20


def test_calculate_average_empty_list():
    with pytest.raises(ValueError):
        calculate_average([])