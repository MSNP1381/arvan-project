---
title: "تنظیمات Routing"
url: "https://docs.arvancloud.ir/fa/cloud-server/network/routing/"
description: "در برخی سناریوها بسته به نیاز، ممکن است یک ابرک به دو یا چند شبکه متصل باشد، که در بیش‌تر سناریوها یکی از شبکه‌ها مربوط به شبکه‌ی عمومی (Public) برای دسترسی به اینترنت است."
---


# تنظیمات Routing

در برخی سناریوها بسته به نیاز، ممکن است یک ابرک به دو یا چند شبکه متصل باشد، که در بیش‌تر سناریوها یکی از شبکه‌ها مربوط به شبکه‌ی عمومی (Public) برای دسترسی به اینترنت است.
از موارد مربوط به Routing، دسترسی ابرک به اینترنت و هم‌چنین دسترسی یک Default Route به آدرس آی‌پی Gateway شبکه‌ی پابلیک در Routing Table سیستم عامل ابرک است. هم‌چنین در برخی موارد، برای شبکه‌های خصوصی که ساخته می‌شوند نیز، بنا به نوع استفاده IP Gateway تعریف می‌شود.
در این حالت اگر ابرک مثلن دو اینترفیس، یکی در شبکه‌ی پابلیک و یکی در شبکه‌ی پرایوت داشته باشد، در Routing Table به‌طور هم‌زمان دو Default Route خواهیم داشت که به‌دلیل مسیریابی اشتباه، دسترسی به اینترنت در ابرک قطع می‌شود.

به‌عنوان نمونه تصویر زیر را ببینیم:

![](https://s3.ir-thr-at1.arvanstorage.ir/arvandocs/cloudserver/network/routing/1.png)

می‌بینید که روی ابرک، پس از اختصاص شبکه‌های مورد نیازمان، دو Default Route ایجاد شده که بر اساس اولویت، مسیریابی دسترسی به شبکه‌ی اینترنت با IP Gateway: 192.168.20.1 است، که اشتباه است و باید حذف شود. فقط Routing Table مربوط به Public Network باید به‌دلیل Permanent کردن تنظیمات روتینگ، اینترفیس مربوط به شبکه‌ی داخلی آن به‌شکل دستی تنظیم شود. لازم است در آن Default Gateway تعیین نشود تا مسیریابی به شبکه‌ی اینترنت به‌درستی از Public Network انجام شود.
از این رو، دو نمونه از تنظیم شبکه‌ی مورد نیاز مربوط به سیستم عامل‌های Ubuntu-18 و Windows-2019 را بررسی می‌کنیم.

## تنظیمات شبکه در سیستم‌عامل Ubuntu 18

ابتدا به ویرایش کانفیگ فایل مربوط به Network Manager اوبونتو 18 یا همان Netplan نیاز داریم. با ویرایش‌گر متنی مورد نظرمان، مثلن با دستور زیر:

```
vim /etc/netplan/50-cloud-init.yaml
```

فایل کانفیگ را باز می‌کنیم و به‌شکل زیر تغییر می‌دهیم:

![](https://s3.ir-thr-at1.arvanstorage.ir/arvandocs/cloudserver/network/routing/2.png)

پس از انجام تغییرات، تنظیمات را ذخیره کرده و از فایل خارج می‌شویم. سپس با دستور زیر تنظیمات را روی سیستم عامل اعمال می‌کنیم:

![](https://s3.ir-thr-at1.arvanstorage.ir/arvandocs/cloudserver/network/routing/3.png)

برای اطمینان پس از انجام تغییرات، دوباره Routing Table را چک می‌کنیم.

![](https://s3.ir-thr-at1.arvanstorage.ir/arvandocs/cloudserver/network/routing/4.png)

همان‌طور که می‌بینید تغییرات به‌درستی در سطح سیستم عامل اعمال شده است.

## تنظیمات شبکه در سیستم‌عامل Windows Server 2019

ابتدا دستور ncpa.cpl را در پنجره‌ی Run وارد می‌کنیم تا وارد صفحه‌ی Network Connections ‌شویم. سپس روی کارت شبکه‌ی مربوط به اینترفیس متصل به شبکه‌ی داخلی خود کلیک راست می‌کنیم و گزینه‌ی Properties را می‌زنیم.

![](https://s3.ir-thr-at1.arvanstorage.ir/arvandocs/cloudserver/network/routing/5.jpg)

در صفحه‌ی بعد ابتدا گزینه‌ی Internet Protocol Version 4 را انتخاب کرده و دوباره روی Properties کلیک می‌کنیم.

![](https://s3.ir-thr-at1.arvanstorage.ir/arvandocs/cloudserver/network/routing/6.jpg)

در صفحه‌ی جدید ابتدا گزینه‌ی Use the following IP address را انتخاب می‌کنیم، سپس IP Address و Subnet Mask مربوط را وارد کرده و Ok را می‌زنیم.

![](https://s3.ir-thr-at1.arvanstorage.ir/arvandocs/cloudserver/network/routing/7.jpg)

برای مشاهده‌ی تغییرات اجراشده، روی کارت شبکه دو بار کلیک می‌کنیم. در صفحه‌ی جدید گزینه‌ی Details را انتخاب می‌کنیم. در صفحه‌ی بعد مشخص می‌شود که تغییرات به‌درستی اعمال شده است، یا خیر.

![](https://s3.ir-thr-at1.arvanstorage.ir/arvandocs/cloudserver/network/routing/8.jpg)
