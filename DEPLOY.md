# استقرار صنوبر روی سرور

## پیش‌نیازها

یک سرور لینوکسی (Ubuntu 22.04 یا بالاتر) با حداقل **۲ گیگابایت RAM** و ۲۰ گیگابایت فضا. کمتر از ۲ گیگ، ورکر Celery و Postgres با هم به مشکل می‌خورند.

```bash
# نصب Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER && newgrp docker

docker --version && docker compose version
```

---

## ۱. آوردن کد و ساخت فایل محیطی

```bash
git clone <repo-url> senobar && cd senobar

cp .env.production.example .env
python3 -c "import secrets; print(secrets.token_urlsafe(50))"   # SECRET_KEY
python3 -c "import secrets; print(secrets.token_urlsafe(24))"   # POSTGRES_PASSWORD
nano .env
```

سه مقدار **حتماً** باید عوض شوند: `SECRET_KEY`، `POSTGRES_PASSWORD`، و `ALLOWED_HOSTS`. اگر `SECRET_KEY` یا `POSTGRES_PASSWORD` را نگذارید، compose بالا نمی‌آید — عمداً، چون شروع‌شدن با رمز پیش‌فرض بدتر از بالا نیامدن است.

```bash
chmod 600 .env
```

## ۲. بالا آوردن

```bash
docker compose up -d --build
```

ترتیب خودکار است: Postgres و Redis سالم می‌شوند، بعد `migrate` یک‌بار اجرا می‌شود و خارج می‌شود، بعد API و ورکر و Beat بالا می‌آیند، و آخر Nginx.

```bash
docker compose ps                 # همه باید healthy باشند
curl localhost/api/health/ready/  # باید {"status":"ok"} بدهد
```

## ۳. ساخت کاربر ادمین

```bash
docker compose exec api python manage.py createsuperuser
```

بعد نقش رستر را بدهید تا به پنل `/admin` (رجیستر Terminal) دسترسی داشته باشد:

```bash
docker compose exec api python manage.py shell -c "
from django.contrib.auth import get_user_model
u = get_user_model().objects.get(email='YOUR-EMAIL')
u.role = 'roaster'; u.is_staff = True; u.save()
print('ok:', u.email, u.role)
"
```

حالا `http://SERVER-IP/admin` پنل مدیریت است و `http://SERVER-IP/` فروشگاه.

---

## ۴. دامنه و HTTPS

DNS دامنه را به IP سرور بدهید (رکورد A)، سپس:

```bash
# پورت داخلی را عوض کنید تا Nginx میزبان جلو بیاید
sed -i 's/^WEB_PORT=80/WEB_PORT=8080/' .env
docker compose up -d

sudo apt install -y nginx certbot python3-certbot-nginx
```

`/etc/nginx/sites-available/senobar`:

```nginx
server {
    listen 80;
    server_name senobar.coffee www.senobar.coffee;

    # Must be at least as large as the container's own nginx.conf (32m) and
    # Django's MAX_IMAGE_UPLOAD_BYTES. The smallest limit in the chain wins,
    # so raising only the inner one changes nothing.
    client_max_body_size 32m;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/senobar /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d senobar.coffee -d www.senobar.coffee
```

`X-Forwarded-Proto` مهم است: بدون آن Django فکر می‌کند درخواست HTTP است و در ایمیل‌ها لینک `http://` می‌سازد.

بعد از اینکه HTTPS **مطمئناً** کار کرد، در `.env`:

```bash
SECURE_SSL_REDIRECT=True
SECURE_HSTS_SECONDS=31536000
FRONTEND_URL=https://senobar.coffee
CORS_ALLOWED_ORIGINS=https://senobar.coffee,https://www.senobar.coffee
```

```bash
docker compose up -d --build web api worker beat
```

**HSTS را زودتر فعال نکنید.** مرورگرها آن را به خاطر می‌سپارند و اگر TLS خراب باشد، سایت تا انقضای هدر غیرقابل دسترس می‌ماند.

---

## ۵. زمان‌بندی گزارش روزانه

Beat با یک زمان‌بندی پیش‌فرض بالا می‌آید: گزارش رست ساعت ۸ صبح به وقت تهران. برای تغییر زمان بدون ری‌دیپلوی، در `/admin` → **Periodic Tasks** آن را ویرایش کنید (زمان‌بندی در دیتابیس ذخیره می‌شود).

بررسی اینکه Beat واقعاً کار می‌کند:

```bash
docker compose logs -f beat | grep daily-roast
docker compose exec api celery -A config call reports.daily_roast_report  # اجرای دستی
```

---

## ۶. پرداخت واقعی

فعلاً `PAYMENT_GATEWAY=mock` است و **هیچ تراکنش واقعی انجام نمی‌شود**. برای زرین‌پال:

```bash
PAYMENT_GATEWAY=zarinpal
ZARINPAL_MERCHANT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

```bash
docker compose up -d api worker
```

**قبل از اعلام عمومی، یک سفارش واقعی با مبلغ کم بدهید و کامل تا verify ببرید.** درایور زرین‌پال نوشته شده اما با کلید واقعی تست نشده است.

## ۷. ایمیل و پیامک واقعی

پیش‌فرض هر دو `console` هستند، یعنی فقط در لاگ چاپ می‌شوند. برای واقعی:

```bash
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.example.com
EMAIL_PORT=587
EMAIL_HOST_USER=...
EMAIL_HOST_PASSWORD=...

SMS_BACKEND=kavenegar
KAVENEGAR_API_KEY=...
```

---

## کارهای روزمره

```bash
docker compose logs -f api worker          # لاگ زنده
docker compose restart api                 # ری‌استارت
docker compose exec api python manage.py migrate   # مایگریشن دستی

# به‌روزرسانی کد
git pull && docker compose up -d --build

# پشتیبان دیتابیس
docker compose exec -T db pg_dump -U senobar senobar | gzip > backup-$(date +%F).sql.gz

# بازگردانی
gunzip -c backup-2026-08-30.sql.gz | docker compose exec -T db psql -U senobar senobar
```

پشتیبان‌گیری را خودکار کنید — یک خط در crontab کافی است:

```
0 3 * * * cd /home/USER/senobar && docker compose exec -T db pg_dump -U senobar senobar | gzip > /backups/senobar-$(date +\%F).sql.gz
```

فایل‌های آپلودشده (تصاویر محصولات) در volume به نام `media` هستند و در `pg_dump` نمی‌آیند؛ جداگانه از آن‌ها بکاپ بگیرید:

```bash
docker run --rm -v senobar_media:/data -v $(pwd):/out alpine \
  tar czf /out/media-$(date +%F).tar.gz -C /data .
```

---

## عیب‌یابی

| نشانه | علت معمول |
|---|---|
| `web` بالا نمی‌آید | `api` هنوز healthy نشده. `docker compose logs api` |
| ۵۰۲ از Nginx | Gunicorn کرش کرده؛ معمولاً `SECRET_KEY` یا `DATABASE_URL` غلط است |
| تسک‌ها اجرا نمی‌شوند | `docker compose logs worker` — اگر Redis در دسترس نباشد اینجا پیداست |
| گزارش ۸ صبح نمی‌آید | `docker compose logs beat`؛ و اینکه `CELERY_TIMEZONE` روی `Asia/Tehran` باشد |
| ایمیل نمی‌رسد | پیش‌فرض `console` است — در لاگ `api` چاپ می‌شود، نه در اینباکس |
| فارسی به‌هم‌ریخته | فونت‌ها self-host شده‌اند؛ معمولاً کش مرورگر است، Ctrl+Shift+R |

---

## چیزهایی که هنوز باید انجام دهید

- **مایگریشن روی Postgres واقعی هرگز اجرا نشده است.** همه‌ی تست‌ها روی SQLite با همان فایل‌های مایگریشن اجرا شده‌اند. اولین `docker compose up` اولین اجرای واقعی است — لاگ `migrate` را بخوانید.
- درایور زرین‌پال با کلید واقعی تست نشده.
- درایور کاوه‌نگار با کلید واقعی تست نشده.
- بکاپ خودکار تنظیم نشده.
