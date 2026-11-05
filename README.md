# صنوبر ☕

فروشگاه آنلاین قهوه تخصصی. هر لات بعد از ثبت سفارش رست می‌شود و تاریخ رست روی بسته ثبت است.

این ریپو شامل کل سیستم است: سایت فروشگاه، پنل مدیریت رستری، API، پرداخت آنلاین با درگاه‌های ایرانی، ورود با کد یکبارمصرف پیامکی، پشتیبانی تیکتی و اعلان‌های تلگرام.

## امکانات

- **فروشگاه:** فهرست و جزئیات محصول، سبد خرید، تسویه حساب، پیگیری سفارش
- **حساب کاربری:** ثبت‌نام و ورود با رمز یا کد یکبارمصرف (OTP) پیامکی، مدیریت آدرس‌ها
- **پرداخت:** درگاه‌های ZarinPal و BitPay، به‌علاوه یک درگاه آزمایشی (mock) برای توسعه
- **پنل مدیریت:** سفارش‌ها، محصولات، بچ‌های رست، موجودی انبار، کاربران، تنظیمات و تیکت‌های پشتیبانی
- **پشتیبانی:** سیستم تیکت بین مشتری و فروشگاه
- **اعلان‌ها:** پیامک (SMS.ir و Kavenegar)، ایمیل، و فید تلگرام برای سفارش‌ها و خلاصه بازدیدها
- **کارهای زمان‌بندی‌شده:** گزارش روزانه رستری و خلاصه‌های دوره‌ای با Celery Beat

## تکنولوژی‌ها

| بخش | ابزار |
| --- | --- |
| فرانت‌اند | Vue 3، Vite، Pinia، Vue Router، Tailwind CSS 4، Axios |
| بک‌اند | Python 3.12، Django 6، Django REST Framework، SimpleJWT، django-filter |
| صف و زمان‌بندی | Celery، django-celery-beat، Redis |
| پایگاه داده | PostgreSQL |
| استقرار | Docker Compose، Nginx، Gunicorn |
| تست | Vitest و Vue Test Utils (فرانت)، تست‌های Django (بک) |

## ساختار پروژه

```text
senobar/
├── src/                  # فرانت‌اند Vue
│   ├── api/              # فراخوانی‌های API
│   ├── stores/           # استورهای Pinia (با تست‌های *.spec.js)
│   ├── views/            # صفحه‌ها؛ صفحه‌های پنل در views/admin
│   ├── components/
│   └── router/
├── backend/              # بک‌اند Django
│   ├── config/           # تنظیمات، Celery، URLها، health check
│   ├── accounts/         # کاربران، احراز هویت، OTP
│   ├── catalog/          # محصولات، بچ‌ها، موجودی، پیشنهادها
│   ├── orders/           # سفارش و ارسال
│   ├── payments/         # درگاه‌های پرداخت
│   ├── support/          # تیکت‌ها
│   └── notifications/    # پیامک، ایمیل، تلگرام
├── docs/                 # مستندات فنی
├── docker-compose.yml
├── nginx.conf
└── *.sh                  # اسکریپت‌های نگهداری سرور
```

## راه‌اندازی محلی

### پیش‌نیازها

- Node.js 22 یا بالاتر
- Python 3.12
- PostgreSQL و Redis (نصب محلی یا با Docker)

اگر نمی‌خواهید Postgres و Redis را روی سیستم نصب کنید:

```bash
docker run -d --name senobar-db -p 5432:5432 \
  -e POSTGRES_USER=senobar -e POSTGRES_PASSWORD=senobar -e POSTGRES_DB=senobar \
  postgres:16
docker run -d --name senobar-redis -p 6379:6379 redis:7
```

### بک‌اند

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# در .env یک SECRET_KEY بسازید:
python3 -c "import secrets; print(secrets.token_urlsafe(50))"

python manage.py migrate
python manage.py createsuperuser
python manage.py runserver          # http://localhost:8000
```

در حالت توسعه، پیامک و ایمیل در کنسول چاپ می‌شوند (`SMS_BACKEND=console`). کد OTP را از خروجی `runserver` بخوانید.

برای کارهای پس‌زمینه، Celery را در ترمینال‌های جداگانه اجرا کنید:

```bash
celery -A config worker -l info
celery -A config beat -l info
```

اگر نمی‌خواهید ورکر اجرا کنید، `CELERY_TASK_ALWAYS_EAGER=True` بگذارید تا تسک‌ها همان لحظه اجرا شوند.

### فرانت‌اند

```bash
npm install
npm run dev                          # http://localhost:5173
```

فرانت‌اند به‌طور پیش‌فرض به `http://localhost:8000/api` وصل می‌شود. برای آدرس دیگر، متغیر `VITE_API_URL` را در `.env.local` بگذارید.

برای دسترسی به پنل مدیریت، کاربر باید نقش `roaster` یا `admin` داشته باشد. جزئیات در [DEPLOY.md](DEPLOY.md) آمده است.

## تست‌ها

```bash
npm test                             # تست‌های فرانت‌اند (Vitest)

cd backend && python manage.py test  # تست‌های بک‌اند
```

## استقرار

کل سیستم با Docker Compose بالا می‌آید: Postgres، Redis، API، ورکر و Beat سلری، و Nginx.

```bash
cp .env.production.example .env      # مقادیر را پر کنید
docker compose up -d --build
```

راهنمای کامل، شامل دامنه و HTTPS، پرداخت واقعی، پیامک، پشتیبان‌گیری و عیب‌یابی، در **[DEPLOY.md](DEPLOY.md)** است.

### اسکریپت‌های نگهداری

این اسکریپت‌ها روی سرور و در پوشه پروژه اجرا می‌شوند:

| اسکریپت | کار |
| --- | --- |
| `deploy-update.sh` | اول از دیتابیس پشتیبان می‌گیرد و بعد آپدیت را اعمال می‌کند |
| `reset-password.sh` | ادمین‌ها را فهرست می‌کند و رمز یکی‌شان را عوض می‌کند |
| `delete-user.sh` | یک حساب آزمایشی را حذف می‌کند. حساب‌هایی که سفارش واقعی دارند حذف نمی‌شوند |
| `sms-probe.sh` | اتصال به SMS.ir را عیب‌یابی می‌کند |
| `sms-timing.sh` | تأخیر ارسال OTP را اندازه می‌گیرد |
| `tg-probe.sh` | فید تلگرام را مرحله‌به‌مرحله عیب‌یابی می‌کند |

## مستندات

- [DEPLOY.md](DEPLOY.md): استقرار و نگهداری روی سرور
- [docs/IRANIAN-GATEWAYS-AND-SMS.md](docs/IRANIAN-GATEWAYS-AND-SMS.md): پیاده‌سازی درگاه‌های پرداخت ایرانی و پیامک/OTP، با باگ‌هایی که در عمل پیش آمد

## امنیت

هیچ کلید یا رمزی را commit نکنید. همه مقادیر حساس از فایل `.env` خوانده می‌شوند و این فایل در `.gitignore` است. اگر مشکل امنیتی پیدا کردید، لطفاً به‌جای issue عمومی، مستقیم اطلاع دهید.

## مجوز

این پروژه تحت مجوز [MIT](LICENSE) منتشر شده است.
