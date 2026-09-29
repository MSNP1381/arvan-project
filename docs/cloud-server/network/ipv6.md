---
title: "آدرس IPv6"
url: "https://docs.arvancloud.ir/fa/cloud-server/network/ipv6/"
description: "هنگامی که یک ابرک در سرور ابری آروان‌کلاد می‌سازید، به‌شکل پیش‌فرض یک آدرس IPv4 به آن تعلق می‌گیرد تا امکان ارتباط با سرورها و یا سیستم‌های دیگر را داشته باشد. علاوه‌بر این، همه‌ی ابرک‌ها امکان استفاده از IPv6 رایگان را نیز دارند و می‌توانید در حین یا پس از ساخت ابرک، به آن یک IPv6 اضافه کنید."
---


# آدرس IPv6

هنگامی که یک ابرک در سرور ابری آروان‌کلاد می‌سازید، به‌شکل پیش‌فرض یک آدرس IPv4 به آن تعلق می‌گیرد تا امکان ارتباط با سرورها و یا سیستم‌های دیگر را داشته باشد. علاوه‌بر این، همه‌ی ابرک‌ها امکان استفاده از IPv6 رایگان را نیز دارند و می‌توانید در حین یا پس از ساخت ابرک، به آن یک IPv6 اضافه کنید.

با فعال کردن IPv6، هنگام ایجاد ابرک اینترفیس‌های شبکه‌ی آن به‌طور خودکار پیکربندی می‌شوند و بدون نیاز به تنظیمات بیش‌تر به‌شکل دستی، می‌توانید از آن استفاده کنید. به همین دلیل پیشنهاد می‌کنیم برای راه‌اندازی سریع‌تر و پیش‌گیری از خطا در تنظیمات از این گزینه استفاده کنید. با این حال می‌توانید IPv6 را در ابرک‌های موجود در حساب کاربری‌تان و پس از ساخت آن‌ها با پیکربندی دستی فعال کنید.

## فعال‌سازی IPv6 هنگام ساخت ابرک

هنگام ایجاد یک ابرک جدید می‌توانید با طی کردن چند گام‌ ساده، سروری با تنظیمات دل‌خواه بسازید. پس از انتخاب ریجن، سیستم‌عامل، اندازه‌ی ابرک و دیسک آن، در بخش «شبکه» می‌توانید یک IP ورژن ۶ به ابرک جدیدتان اضافه کنید.

![](https://arvandocs.s3.ir-thr-at1.arvanstorage.ir/cloudserver/network/ipv6/panel.png)

> توجه داشته باشید برای فعال‌سازی IPv6 باید آدرس IPv4 را هم فعال نگه دارید.

پس از تنظیم گزینه‌های دیگر و بررسی نهایی روی دکمه‌ی «ساخت ابرک»‌ کلیک کنید تا سرور ایجاد و راه‌اندازی شود.

زمانی که سرور ساخته شد،‌ می‌توانید در لیست ابرک‌ها و بخش آدرس IP یا با کلیک روی جزییات ابرک، IPv6 تعلق‌گرفته به شبکه‌ی سرور را مشاهده کنید. این IP نیازی به پیکربندی ندارد و آماده‌ی اتصال است.

![](https://arvandocs.s3.ir-thr-at1.arvanstorage.ir/cloudserver/network/ipv6/instance-ip.png)

## فعال‌سازی IPv6 پس از ساخت ابرک

اگر ابرکی دارید که پیش از این ساخته‌اید می‌خواهید به آن IP ورژن ۶ اضافه کنید، می‌توانید از بخش «IP اینترنتی» در پنل سرور ابری روی دکمه‌ی «افزودن IP اینترنتی» کلیک کرده و IPv6 را انتخاب کنید.

![](https://arvandocs.s3.ir-thr-at1.arvanstorage.ir/cloudserver/network/ipv6/ipv6.png)

هنگامی که IPv6 را روی ابرکی از پیش ساخته‌شده فعال کنید، باید تنظیمات شبکه‌ی آن را به‌شکل دستی در سرور انجام دهید. این تنظیمات، پیکربندی خودکار شبکه را غیرفعال و اطلاعاتی مانند Name Server، آدرس Gateway و آدرس IPv6 را به سرور اضافه می‌کند.

> برای دریافت آدرس Gateway و Subnet در پنل سرور ابری به بخش «شبکه» و سپس «IP اینترنتی» مراجعه کنید.

از طریق کنسول ابرک یا SSH به سرور متصل شوید و بر اساس توزیع سیستم‌عامل‌تان، تنظیمات را تغییر دهید:

* Ubuntu 20.04 و بالاتر
* Debian 10 و بالاتر
* Rocky Linux 8/9 ،CentOS7 و بالاتر

فایل `etc/netplan/50-cloud-init.yaml/` را باز کرده و خطوط زیر را به آن اضافه کنید:

```
network:

version: 2

ethernets:

eth0:

dhcp4: true

mtu: 1500

set-name: eth0

eth1:

accept-ra: false

addresses:

- {your_ipv6_and_subnet}

mtu: 1500

nameservers:

addresses:

- 2606:4700::1111

- 2001:4860:4860::8888

routes:

-   to: ::/0

via: {gateway_address}

set-name: eth1
```

سپس سرویس شبکه را دوباره راه‌اندازی کنید:

```
sudo netplan apply
```

خطوط زیر را به فایل `etc/network/interfaces.d/50-cloud-init/` اضافه کنید:

```
auto eth1

iface eth1 inet6 static

address {your_ipv6_and_subnet}

mtu 1500

post-up route add -A inet6 default gw {gateway_address} || true

pre-down route del -A inet6 default gw {gateway_address} || true
```

سپس سرویس شبکه را دوباره راه‌اندازی کنید:

```
sudo systemctl restart networking
```

فایل `etc/sysconfig/network-scripts/ifcfg-eth1/` را باز کرده و خطوط زیر را به آن اضافه کنید:

```
BOOTPROTO=none

DEVICE=eth1

IPV6ADDR={your_ipv6_and_subnet}

IPV6INIT=yes

IPV6_DEFAULTGW={gateway_address}

ONBOOT=yes

STARTMODE=auto
```

سپس سرور را ریبوت کنید:

```
sudo reboot
```

## بررسی ارتباط IPv6

نکته

برای استفاده از IPv6، هر دو سمت یک Connection باید قابلیت ارسال و دریافت ترافیک IPv6 را داشته باشند. از آن‌جایی که همه‌ی ISPها آدرس‌ IPv6 ارایه نمی‌دهند، ممکن است نتوانید از سیستم خود به آدرس IPv6 ابرک‌تان متصل شوید.

برای بررسی تنظیمات و ارتباط IPv6 می‌توانید IP ورژن ۶ گوگل را از ابرک‌تان پینگ کنید:

```
ping6 2001:4860:4860::8888
```

اگر تنظیمات به‌طور صحیح اعمال شده باشد و IPv6 به‌درستی کار کند باید خروجی‌ای مشابه تصویر زیر دریافت کنید:

![](https://arvandocs.s3.ir-thr-at1.arvanstorage.ir/cloudserver/network/ipv6/ping.png)

## غیرفعال کردن IPv6

برای غیرفعال کردن IPv6 از طریق کنسول یا SSH به سرور متصل شوید و بر اساس توزیع سیستم‌عامل‌تان، تنظیمات را تغییر دهید:

* Ubuntu 20.04 و بالاتر
* Debian 10 و بالاتر
* Rocky Linux 8/9 ،CentOS7 و بالاتر

فایل `etc/netplan/50-cloud-init.yaml/` را باز کرده و خطوط زیر را از آن حذف کنید:

```
network:

version: 2

ethernets:

eth0:

dhcp4: true

mtu: 1500

set-name: eth0

eth1:

accept-ra: false

addresses:

- {your_ipv6_and_subnet}

mtu: 1500

nameservers:

addresses:

- 2606:4700::1111

- 2001:4860:4860::8888

routes:

-   to: ::/0

via: {gateway_address}

set-name: eth1
```

سپس سرویس شبکه را دوباره راه‌اندازی کنید:

```
sudo netplan apply
```

خطوط زیر را از فایل `etc/network/interfaces.d/50-cloud-init/` حذف کنید:

```
auto eth1

iface eth1 inet6 static

address {your_ipv6_and_subnet}

mtu 1500

post-up route add -A inet6 default gw {gateway_address} || true

pre-down route del -A inet6 default gw {gateway_address} || true
```

سپس سرویس شبکه را دوباره راه‌اندازی کنید:

```
sudo systemctl restart networking
```

فایل `etc/sysconfig/network-scripts/ifcfg-eth1/` را حذف و سپس سرور را ریبوت کنید:

```
sudo reboot
```
