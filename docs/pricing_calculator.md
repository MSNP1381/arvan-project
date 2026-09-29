# Arvan Cloud Server Pricing Calculator & Escalation Policy

This document provides complete documentation for the official **Arvan Cloud Server Pricing Calculator** module, API schemas, and customer support escalation protocols.

---

## 1. Overview & Scope

The pricing calculator provides automated, deterministic calculation of official hourly and monthly costs for Arvan Cloud Server resources in **Tomans (تومان)**.

### Resource Classification:
- **Core Calculable Resources** (Supported via `calculate_server_price`):
  - **پردازنده (CPU)**: 1 to N vCPU cores across Basic, Standard, and Premium generations.
  - **حافظه رم (RAM)**: Memory capacity in GB.
  - **دیسک ابری (Cloud Disk)**: High-performance SSD or economical HDD block storage in GB.
  - **ترافیک (Traffic)**: Upload/Download data transfer in GB (region-tiered).
  - **پشتیبان‌گیری (Backup)**: Automated server backup storage in GB.
  - **ایمیج و اسنپ‌شات (Snapshot & Image)**: Snapshot storage capacity in GB.
- **Specialized / Managed Resources** (Escalated via `escalate_to_support`):
  - **دیسک لوکال (Local Disk / Local Storage)**
  - **فایل استوریج (File Storage / NFS)**
  - **نشانی‌های IP عمومی یا اضافه (IPv4 / IPv6 Addresses)**
  - **پردازنده‌های گرافیکی (GPU / NVIDIA AI Processors)**
  - **انتقال رنج آی‌پی اختصاصی (BYOIP - Bring Your Own IP)**

---

## 2. Official Pricing Rates Table (in Tomans)

### 2.1 پردازنده (CPU) - نرخ به ازای هر هسته
| نسل سرور (Tier) | منطقه ایران (ساعتی) | منطقه ایران (ماهانه) | منطقه اروپا (ساعتی) | منطقه اروپا (ماهانه) |
| :--- | :--- | :--- | :--- | :--- |
| **Basic** | ۲۹۲ تومان | ۲۱۰,۰۰۰ تومان | ۳۵۰ تومان | ۲۵۲,۰۰۰ تومان |
| **Standard** | ۳۷۹ تومان | ۲۷۳,۰۰۰ تومان | ۴۵۵ تومان | ۳۲۷,۶۰۰ تومان |
| **Premium** | ۵۵۴ تومان | ۳۹۹,۰۰۰ تومان | ۶۷۸ تومان | ۴۷۸,۸۰۰ تومان |

### 2.2 حافظه رم (RAM) - نرخ به ازای هر گیگابایت
| نسل سرور (Tier) | منطقه ایران (ساعتی) | منطقه ایران (ماهانه) | منطقه اروپا (ساعتی) | منطقه اروپا (ماهانه) |
| :--- | :--- | :--- | :--- | :--- |
| **Basic** | ۲۲۷ تومان | ۱۶۳,۵۰۰ تومان | ۲۷۳ تومان | ۱۹۶,۲۰۰ تومان |
| **Standard** | ۲۹۵ تومان | ۲۱۲,۶۰۰ تومان | ۳۵۴ تومان | ۲۵۵,۱۰۰ تومان |
| **Premium** | ۴۳۲ تومان | ۳۱۰,۷۰۰ تومان | ۵۱۸ تومان | ۳۷۲,۸۰۰ تومان |

### 2.3 دیسک ابری (Cloud Disk) - نرخ به ازای هر گیگابایت
| نوع دیسک (Storage Type) | منطقه ایران (ساعتی) | منطقه ایران (ماهانه) | منطقه اروپا (ساعتی) | منطقه اروپا (ماهانه) |
| :--- | :--- | :--- | :--- | :--- |
| **دیسک SSD** | ۲۱ تومان | ۱۵,۰۰۰ تومان | ۲۵ تومان | ۱۸,۰۰۰ تومان |
| **دیسک HDD** | ۱۰ تومان | ۷,۲۰۰ تومان | ۱۲ تومان | ۸,۷۰۰ تومان |

### 2.4 بکاپ و اسنپ‌شات - نرخ به ازای هر گیگابایت
| سرویس | منطقه ایران (ساعتی) | منطقه ایران (ماهانه) | منطقه اروپا (ساعتی) | منطقه اروپا (ماهانه) |
| :--- | :--- | :--- | :--- | :--- |
| **پشتیبان‌گیری (Backup)** | ۲۰ تومان | ۱۴,۴۰۰ تومان | ۲۴ تومان | ۱۷,۳۰۰ تومان |
| **ایمیج و اسنپ‌شات (Snapshot)** | ۲۱ تومان | ۱۵,۰۰۰ تومان | ۲۵ تومان | ۱۸,۰۰۰ تومان |

### 2.5 ترافیک مصرفی (Traffic)
- **منطقه ایران**:
  - ترافیک آپلود (Send): **رایگان**
  - ترافیک دانلود (Receive - به صورت پلکانی):
    - ۰ تا ۲۵۰ گیگابایت: **رایگان**
    - ۲۵۰ گیگابایت تا ۱۰ ترابایت: ۱,۸۰۰ تومان / گیگابایت
    - ۱۰ تا ۱۰۰ ترابایت: ۱,۲۰۰ تومان / گیگابایت
    - بیش از ۱۰۰ ترابایت: ۱,۰۵۰ تومان / گیگابایت
- **منطقه اروپا**:
  - مجموع ترافیک آپلود و دانلود به ازای هر سرور:
    - ۰ تا ۱۰ ترابایت: **رایگان**
    - مازاد بر ۱۰ ترابایت: ۳۹۰ تومان / گیگابایت

---

## 3. Python API & Tool Usage

### Calling `calculate_server_cost` Directly
```python
from arvan_project.calculator import calculate_server_cost

# Mandatory: cpu_cores, ram_gb, storage_gb
result = calculate_server_cost(
    cpu_cores=4,
    ram_gb=8,
    storage_gb=80,
    region="iran",        # Optional (default: "iran")
    tier="standard",      # Optional (default: "standard")
    storage_type="ssd",   # Optional (default: "ssd")
    download_traffic_gb=500, # Optional (default: 0.0)
    backup_gb=50,         # Optional (default: 0.0)
    snapshot_gb=20,       # Optional (default: 0.0)
)

print(f"Total Hourly: {result.total_hourly_toman:,} Tomans")
print(f"Total Monthly: {result.total_monthly_toman:,} Tomans")
print(result.format_persian_markdown())
```

### Agent Tool: `calculate_server_price`
The LangChain tool can be invoked by the agent or manually:
```python
from arvan_project.agent.tools import calculate_server_price

report = calculate_server_price.invoke({
    "cpu_cores": 2,
    "ram_gb": 4,
    "storage_gb": 50,
    "region": "iran",
    "tier": "standard",
})
```

---

## 4. Support Escalation Policy (`escalate_to_support`)

For enterprise or specialized components, the AI assistant does not produce automated cost estimates. Instead, it triggers `escalate_to_support`:

```python
from arvan_project.agent.tools import escalate_to_support

escalate_to_support.invoke({
    "service_type": "gpu",
    "details": "مشتری درخواست برآورد هزینه و سهمیه برای سرور با کارت گرافیک NVIDIA A100 دارد.",
})
```

### Escalated Services Checklist:
1. **دیسک لوکال (Local Storage)**
2. **فایل استوریج (File Storage / NFS)**
3. **نشانی‌های IP عمومی یا اضافه (IPv4 / IPv6 addresses)**
4. **سرورهای پردازش گرافیکی (GPU / NVIDIA AI Instances)**
5. **انتقال رنج آی‌پی اختصاصی (BYOIP)**
6. **افزایش سهمیه منابع سازمانی (Quota Increase)**
