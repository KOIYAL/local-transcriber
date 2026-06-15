import pytest

from app.system_info import select_model_for_memory


@pytest.mark.parametrize(
    ("memory_gb", "expected"),
    [
        (4, "tiny"),
        (7.9, "tiny"),
        (8, "base"),
        (15.9, "base"),
        (16, "small"),
        (31.9, "small"),
        (32, "medium"),
        (64, "medium"),
    ],
)
def test_select_model_for_memory(memory_gb: float, expected: str) -> None:
    assert select_model_for_memory(int(memory_gb * 1024**3)) == expected
