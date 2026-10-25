import pytest

from app.system_info import select_model_for_memory


@pytest.mark.parametrize(
    ("memory_gb", "expected"),
    [
        (4, "tiny"),
        (6.9, "tiny"),
        (7.7, "base"),    # 8 GB Windows PC (part reserved by the system)
        (8, "base"),      # 8 GB Mac
        (13.9, "base"),
        (15.6, "small"),  # 16 GB Windows PC
        (16, "small"),
        (24, "small"),    # 24 GB Mac
        (27.9, "small"),
        (31.6, "turbo"),  # 32 GB Windows PC
        (32, "turbo"),
        (64, "turbo"),
    ],
)
def test_select_model_for_memory(memory_gb: float, expected: str) -> None:
    assert select_model_for_memory(int(memory_gb * 1024**3)) == expected
