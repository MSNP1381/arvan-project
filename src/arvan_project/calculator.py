from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Literal, Any


RegionType = Literal["iran", "europe"]
TierType = Literal["basic", "standard", "premium"]
StorageType = Literal["ssd", "hdd"]

# --- Pricing Tables (in Tomans) based on ArvanCloud official rates ---

# CPU Pricing: (hourly, monthly) per core
CPU_RATES: Dict[RegionType, Dict[TierType, tuple[float, float]]] = {
    "iran": {
        "basic": (292.0, 210_000.0),
        "standard": (379.0, 273_000.0),
        "premium": (554.0, 399_000.0),
    },
    "europe": {
        "basic": (350.0, 252_000.0),
        "standard": (455.0, 327_600.0),
        "premium": (678.0, 478_800.0),
    },
}

# RAM Pricing: (hourly, monthly) per GB
RAM_RATES: Dict[RegionType, Dict[TierType, tuple[float, float]]] = {
    "iran": {
        "basic": (227.0, 163_500.0),
        "standard": (295.0, 212_600.0),
        "premium": (432.0, 310_700.0),
    },
    "europe": {
        "basic": (273.0, 196_200.0),
        "standard": (354.0, 255_100.0),
        "premium": (518.0, 372_800.0),
    },
}

# Cloud Disk Storage Pricing: (hourly, monthly) per GB
STORAGE_RATES: Dict[RegionType, Dict[StorageType, tuple[float, float]]] = {
    "iran": {
        "ssd": (21.0, 15_000.0),
        "hdd": (10.0, 7_200.0),
    },
    "europe": {
        "ssd": (25.0, 18_000.0),
        "hdd": (12.0, 8_700.0),
    },
}

# Backup Pricing: (hourly, monthly) per GB
BACKUP_RATES: Dict[RegionType, tuple[float, float]] = {
    "iran": (20.0, 14_400.0),
    "europe": (24.0, 17_300.0),
}

# Image & Snapshot Pricing: (hourly, monthly) per GB
SNAPSHOT_RATES: Dict[RegionType, tuple[float, float]] = {
    "iran": (21.0, 15_000.0),
    "europe": (25.0, 18_000.0),
}


@dataclass
class CostItem:
    name: str
    details: str
    hourly_toman: float
    monthly_toman: float


@dataclass
class CalculationResult:
    region: str
    tier: str
    items: List[CostItem] = field(default_factory=list)
    total_hourly_toman: float = 0.0
    total_monthly_toman: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "region": self.region,
            "tier": self.tier,
            "total_hourly_toman": round(self.total_hourly_toman, 2),
            "total_monthly_toman": round(self.total_monthly_toman, 2),
            "items": [
                {
                    "name": item.name,
                    "details": item.details,
                    "hourly_toman": round(item.hourly_toman, 2),
                    "monthly_toman": round(item.monthly_toman, 2),
                }
                for item in self.items
            ],
        }

    def format_persian_markdown(self) -> str:
        """Formats the result into a clean, human-readable Persian Markdown report."""
        region_fa = "ایران (Iran)" if self.region == "iran" else "اروپا (Europe)"
        tier_fa = {
            "basic": "Basic (پایه)",
            "standard": "Standard (استاندارد)",
            "premium": "Premium (پیشرفته)",
        }.get(self.tier, self.tier)

        lines = [
            f"### 🧮 برآورد هزینه سرور ابری آروان ({region_fa} - نسل {tier_fa})",
            "",
            "| ردیف | شرح سرویس / منبع | مشخصات | هزینه ساعتی (تومان) | هزینه ماهانه (تومان) |",
            "| :--- | :--- | :--- | :--- | :--- |",
        ]

        for idx, item in enumerate(self.items, start=1):
            h_str = f"{item.hourly_toman:,.0f}" if item.hourly_toman > 0 else "-"
            m_str = f"{item.monthly_toman:,.0f}" if item.monthly_toman > 0 else "رایگان"
            lines.append(f"| {idx} | {item.name} | {item.details} | {h_str} | {m_str} |")

        lines.extend([
            "",
            "---",
            f"**مجموع هزینه ساعتی:** `{self.total_hourly_toman:,.0f} تومان`",
            f"**مجموع هزینه ماهانه:** `{self.total_monthly_toman:,.0f} تومان`",
        ])

        return "\n".join(lines)


def calculate_traffic_cost(region: RegionType, download_gb: float, upload_gb: float) -> tuple[float, float]:
    """Calculates monthly and hourly traffic costs based on region and transfer volumes."""
    if region == "iran":
        # Upload is free. Download is tiered per month.
        gb = max(0.0, download_gb)
        if gb <= 250:
            monthly = 0.0
        elif gb <= 10_000:
            monthly = (gb - 250) * 1_800.0
        elif gb <= 100_000:
            monthly = (10_000 - 250) * 1_800.0 + (gb - 10_000) * 1_200.0
        else:
            monthly = (
                (10_000 - 250) * 1_800.0
                + (100_000 - 10_000) * 1_200.0
                + (gb - 100_000) * 1_050.0
            )
    else:
        # Europe: Combined traffic per server
        total_gb = max(0.0, download_gb + upload_gb)
        if total_gb <= 10_000:
            monthly = 0.0
        else:
            monthly = (total_gb - 10_000) * 390.0

    # Hourly estimation based on 720 hours/month
    hourly = monthly / 720.0 if monthly > 0 else 0.0
    return hourly, monthly


def calculate_server_cost(
    # --- REQUIRED (MANDATORY) PARAMETERS ---
    cpu_cores: int | float,
    ram_gb: int | float,
    storage_gb: int | float,
    # --- OPTIONAL PARAMETERS ---
    region: RegionType | str = "iran",
    tier: TierType | str = "standard",
    storage_type: StorageType | str = "ssd",
    download_traffic_gb: float = 0.0,
    upload_traffic_gb: float = 0.0,
    backup_gb: float = 0.0,
    snapshot_gb: float = 0.0,
) -> CalculationResult:
    """Calculates detailed hourly and monthly Arvan Cloud Server costs for core infrastructure.

    Args:
        cpu_cores: Number of CPU cores (Required).
        ram_gb: RAM size in Gigabytes (Required).
        storage_gb: Cloud disk storage size in Gigabytes (Required).
        region: 'iran' or 'europe' (default: 'iran').
        tier: 'basic', 'standard', or 'premium' (default: 'standard').
        storage_type: 'ssd' or 'hdd' (default: 'ssd').
        download_traffic_gb: Estimated monthly download traffic in GB (default: 0).
        upload_traffic_gb: Estimated monthly upload traffic in GB (default: 0).
        backup_gb: Cloud backup storage in GB (default: 0).
        snapshot_gb: Snapshot and image storage in GB (default: 0).

    Returns:
        CalculationResult with breakdown of each cost item and total costs.
    """
    # Validation & Normalization
    reg = str(region).strip().lower()
    if reg not in ("iran", "europe"):
        reg = "iran"
    reg_typed: RegionType = reg  # type: ignore

    t = str(tier).strip().lower()
    if t not in ("basic", "standard", "premium"):
        t = "standard"
    tier_typed: TierType = t  # type: ignore

    st = str(storage_type).strip().lower()
    if st not in ("ssd", "hdd"):
        st = "ssd"
    storage_typed: StorageType = st  # type: ignore

    cpu_val = max(0.0, float(cpu_cores))
    ram_val = max(0.0, float(ram_gb))
    storage_val = max(0.0, float(storage_gb))

    result = CalculationResult(region=reg_typed, tier=tier_typed)

    # 1. CPU (Required)
    cpu_h_rate, cpu_m_rate = CPU_RATES[reg_typed][tier_typed]
    cpu_h = cpu_val * cpu_h_rate
    cpu_m = cpu_val * cpu_m_rate
    result.items.append(
        CostItem(
            name="پردازنده (CPU)",
            details=f"{cpu_val:g} هسته ({tier_typed.capitalize()})",
            hourly_toman=cpu_h,
            monthly_toman=cpu_m,
        )
    )

    # 2. RAM (Required)
    ram_h_rate, ram_m_rate = RAM_RATES[reg_typed][tier_typed]
    ram_h = ram_val * ram_h_rate
    ram_m = ram_val * ram_m_rate
    result.items.append(
        CostItem(
            name="حافظه رم (RAM)",
            details=f"{ram_val:g} گیگابایت ({tier_typed.capitalize()})",
            hourly_toman=ram_h,
            monthly_toman=ram_m,
        )
    )

    # 3. Storage / Cloud Disk (Required)
    st_h_rate, st_m_rate = STORAGE_RATES[reg_typed][storage_typed]
    st_h = storage_val * st_h_rate
    st_m = storage_val * st_m_rate
    result.items.append(
        CostItem(
            name=f"دیسک ابری ({storage_typed.upper()})",
            details=f"{storage_val:g} گیگابایت",
            hourly_toman=st_h,
            monthly_toman=st_m,
        )
    )

    # 4. Traffic (Optional)
    if download_traffic_gb > 0 or upload_traffic_gb > 0:
        tr_h, tr_m = calculate_traffic_cost(reg_typed, download_traffic_gb, upload_traffic_gb)
        traffic_details = (
            f"دانلود: {download_traffic_gb:g}GB | آپلود: {upload_traffic_gb:g}GB"
            if reg_typed == "iran"
            else f"مجموع ترافیک: {download_traffic_gb + upload_traffic_gb:g}GB"
        )
        result.items.append(
            CostItem(
                name="ترافیک مصرفی",
                details=traffic_details,
                hourly_toman=tr_h,
                monthly_toman=tr_m,
            )
        )

    # 5. Backup (Optional)
    if backup_gb > 0:
        bk_h_rate, bk_m_rate = BACKUP_RATES[reg_typed]
        bk_h = backup_gb * bk_h_rate
        bk_m = backup_gb * bk_m_rate
        result.items.append(
            CostItem(
                name="پشتیبان‌گیری (Backup)",
                details=f"{backup_gb:g} گیگابایت",
                hourly_toman=bk_h,
                monthly_toman=bk_m,
            )
        )

    # 6. Snapshot & Image (Optional)
    if snapshot_gb > 0:
        sn_h_rate, sn_m_rate = SNAPSHOT_RATES[reg_typed]
        sn_h = snapshot_gb * sn_h_rate
        sn_m = snapshot_gb * sn_m_rate
        result.items.append(
            CostItem(
                name="ایمیج و اسنپ‌شات",
                details=f"{snapshot_gb:g} گیگابایت",
                hourly_toman=sn_h,
                monthly_toman=sn_m,
            )
        )

    # Calculate Totals
    result.total_hourly_toman = sum(item.hourly_toman for item in result.items)
    result.total_monthly_toman = sum(item.monthly_toman for item in result.items)

    return result
