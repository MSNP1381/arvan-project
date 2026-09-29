import pytest
from arvan_project.calculator import (
    calculate_server_cost,
    calculate_traffic_cost,
    CPU_RATES,
    RAM_RATES,
    STORAGE_RATES,
)
from arvan_project.agent.tools import calculate_server_price


def test_calculate_base_server_required_only():
    """Verify that specifying only the 3 mandatory parameters (CPU, RAM, Storage) works correctly."""
    result = calculate_server_cost(
        cpu_cores=2,
        ram_gb=4,
        storage_gb=50,
    )

    # Defaults: iran, standard, ssd
    assert result.region == "iran"
    assert result.tier == "standard"
    assert len(result.items) == 3

    # CPU: 2 cores * 379/hr, 2 * 273,000/mo
    cpu_item = result.items[0]
    assert cpu_item.hourly_toman == 2 * 379.0
    assert cpu_item.monthly_toman == 2 * 273_000.0

    # RAM: 4 GB * 295/hr, 4 * 212,600/mo
    ram_item = result.items[1]
    assert ram_item.hourly_toman == 4 * 295.0
    assert ram_item.monthly_toman == 4 * 212_600.0

    # Storage: 50 GB SSD * 21/hr, 50 * 15,000/mo
    st_item = result.items[2]
    assert st_item.hourly_toman == 50 * 21.0
    assert st_item.monthly_toman == 50 * 15_000.0

    expected_hourly = (2 * 379) + (4 * 295) + (50 * 21)
    expected_monthly = (2 * 273_000) + (4 * 212_600) + (50 * 15_000)
    assert result.total_hourly_toman == expected_hourly
    assert result.total_monthly_toman == expected_monthly


def test_calculate_europe_basic_hdd():
    """Verify Europe region, basic tier, and HDD storage."""
    result = calculate_server_cost(
        cpu_cores=1,
        ram_gb=2,
        storage_gb=100,
        region="europe",
        tier="basic",
        storage_type="hdd",
    )

    assert result.region == "europe"
    assert result.tier == "basic"

    # CPU: 1 * 350/hr, 252,000/mo
    # RAM: 2 * 273/hr = 546/hr, 2 * 196,200 = 392,400/mo
    # HDD: 100 * 12/hr = 1,200/hr, 100 * 8,700 = 870,000/mo
    expected_hourly = 350.0 + 546.0 + 1_200.0
    expected_monthly = 252_000.0 + 392_400.0 + 870_000.0

    assert result.total_hourly_toman == expected_hourly
    assert result.total_monthly_toman == expected_monthly


def test_traffic_calculation_iran_and_europe():
    # Iran: first 250 GB free
    h0, m0 = calculate_traffic_cost("iran", download_gb=200, upload_gb=500)
    assert m0 == 0.0

    # Iran: 500 GB download -> 250 free + 250 * 1800 = 450,000 Toman
    h1, m1 = calculate_traffic_cost("iran", download_gb=500, upload_gb=1000)
    assert m1 == 450_000.0

    # Europe: up to 10 TB free
    he0, me0 = calculate_traffic_cost("europe", download_gb=5_000, upload_gb=4_000)
    assert me0 == 0.0

    # Europe: 12,000 GB total -> 2,000 GB over * 390 = 780,000 Toman
    he1, me1 = calculate_traffic_cost("europe", download_gb=6_000, upload_gb=6_000)
    assert me1 == 2_000 * 390.0


def test_optional_addons_calculation():
    """Verify optional services: Backup and Snapshot."""
    result = calculate_server_cost(
        cpu_cores=4,
        ram_gb=16,
        storage_gb=100,
        region="iran",
        tier="premium",
        backup_gb=50,
        snapshot_gb=20,
    )

    # Backup: 50 * 14,400 = 720,000
    backup_item = next(item for item in result.items if "Backup" in item.name)
    assert backup_item.monthly_toman == 50 * 14_400.0

    # Snapshot: 20 * 15,000 = 300,000
    snapshot_item = next(item for item in result.items if "اسنپ‌شات" in item.name)
    assert snapshot_item.monthly_toman == 20 * 15_000.0

    # Check markdown output contains formatted Persian table
    report = result.format_persian_markdown()
    assert "برآورد هزینه سرور ابری آروان" in report
    assert "مجموع هزینه ماهانه:" in report
    assert "تومان" in report


def test_calculate_server_price_tool_invocation():
    """Verify LangChain tool invocation with required and optional arguments."""
    output = calculate_server_price.invoke({
        "cpu_cores": 2,
        "ram_gb": 4,
        "storage_gb": 40,
        "region": "iran",
        "tier": "standard",
    })
    assert "برآورد هزینه سرور ابری آروان" in output
    assert "پردازنده (CPU)" in output
    assert "حافظه رم (RAM)" in output
    assert "دیسک ابری (SSD)" in output
