# درگاه‌های پرداخت ایرانی و پیامک/OTP — یک پیاده‌سازی واقعی

این سند یادداشت‌های پیاده‌سازی دو زیرسیستم صنوبر است: **درگاه‌های پرداخت** (`ZarinPal` و `BitPay`) و **پیامک و کد یک‌بارمصرف** (`SMS.ir`). همه‌چیزی که این‌جا آمده ساخته، روی سرور مستقر و در محیط واقعی عیب‌یابی شده است؛ باگ‌هایی که فهرست شده‌اند فرضی نیستند، واقعاً اتفاق افتاده‌اند.

**برای چه کسی است؟** برای توسعه‌دهنده‌ای که می‌خواهد بفهمد این بخش‌ها در صنوبر چطور کار می‌کنند، یا می‌خواهد همین منطق را در پروژهٔ Django خودش به کار ببرد.

**چطور بخوانید:** قبل از نوشتن هر خط کد، بخش **باگ‌ها**ی هر قسمت را بخوانید. بیشترِ هزینهٔ این کار همین باگ‌ها بود، و همه‌شان بی‌صدا هستند — کد درست به نظر می‌رسد، HTTP 200 برمی‌گرداند، و هیچ کاری نمی‌کند.

**پشتهٔ فنی صنوبر:** Django 6 + DRF، PostgreSQL، Celery + Redis، Docker Compose، و `django-environ` برای تنظیمات. منطق درگاه و پیامک به هیچ‌کدام از این‌ها وابسته نیست، مگر جاهایی که صریحاً گفته شده؛ آزادانه با پروژهٔ خودتان تطبیقش دهید.

**کد اصلی کجاست:**

* `backend/payments/` — درایورهای درگاه در `gateways.py`، ویوهای درخواست و تأیید پرداخت در `views.py`، مدل `Payment` در `models.py`.
* `backend/accounts/otp.py` — سیاست صدور و بررسی کد یک‌بارمصرف و نرمال‌سازی شمارهٔ موبایل.
* `backend/accounts/otp_views.py` — endpointهای درخواست و تأیید کد.
* `backend/accounts/models.py` — مدل `PhoneOTP`.
* `backend/notifications/providers.py` — بک‌اندهای پیامک (`console`، `SMS.ir`، `Kavenegar`).
* `backend/config/digits.py` — تبدیل ارقام فارسی و عربی به انگلیسی.

تکه‌کدهای این سند خلاصه‌شدهٔ همان فایل‌ها هستند؛ برای جزئیات کامل به خود کد مراجعه کنید.

---

# بخش ۱ — درگاه‌های پرداخت (ZarinPal و BitPay)

## ۱.۱ شکل مسئله

هر دو درگاه دومرحله‌ای و مبتنی بر ریدایرکت هستند:

1. **درخواست** — سرور به درگاه می‌گوید «برای سفارش X مبلغ `N` ریال می‌خواهم، مشتری را به این آدرس برگردان». درگاه یک توکن برمی‌گرداند.
2. **ریدایرکت** — مرورگر به صفحهٔ پرداخت درگاه می‌رود و مشتری پرداخت می‌کند.
3. **بازگشت (callback)** — درگاه مرورگر را با همان توکن به آدرس شما برمی‌گرداند.
4. **تأیید (verify)** — سرور از درگاه می‌پرسد «این واقعاً پرداخت شده؟». فقط همین پاسخ اجازه دارد سفارش را تسویه کند.

**هرگز سفارش را فقط بر اساس callback تسویه نکنید.** callback یک ریدایرکت مرورگر است: هر کسی می‌تواند آن آدرس را با پارامترهای ساختگی تایپ کند. مرحلهٔ ۴ یک فراخوانی سرور به سرور است و تنها مرحلهٔ قابل‌اعتماد.

دو درگاه در یک نکتهٔ ساختاری با هم فرق دارند و همین نکته کل طراحی را شکل می‌دهد:

| | ZarinPal | BitPay |
|---|---|---|
| خروجی درخواست | `authority` — ۳۶ کاراکتر، `A` یا `S` + ۳۵ | `id_get` — یک عدد صحیح مثبت |
| ریدایرکت به | `/pg/StartPay/<authority>` | `/payment/gateway-<id_get>-get` |
| محتوای callback | `?Authority=…&Status=OK\|NOK` | `?trans_id=…&id_get=…` |
| نیاز تأیید | authority + مبلغ | id_get + **trans_id** |
| کد موفقیت | `100` (`101` = قبلاً تأیید شده) | `1` (`11` = قبلاً تأیید شده) |
| قالب پاسخ | JSON | در درخواست **یک عدد خام**، در تأیید JSON |
| گزارش کارمزد | بله، در پاسخ verify | **خیر** |

BitPay هنگام تأیید به یک شناسهٔ *دوم* نیاز دارد که ZarinPal اصلاً مفهومی از آن ندارد. همین تفاوت دلیل این است که `verify()` یک دیکشنری `extra` می‌گیرد.

## ۱.۲ رابط درایور

یک رابط، سه پیاده‌سازی (mock، ZarinPal، BitPay). هیچ لایه‌ای بالاتر از این نمی‌داند کدام در حال اجراست.

```python
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

class GatewayError(Exception):
    """The gateway refused the request or returned something unusable."""

@dataclass
class PaymentRequest:
    authority: str
    redirect_url: str
    raw: dict = field(default_factory=dict)

@dataclass
class VerificationResult:
    success: bool
    ref_id: str = ""
    card_pan: str = ""
    message: str = ""
    already_verified: bool = False
    fee: Decimal = Decimal("0")
    raw: dict = field(default_factory=dict)

class BaseGateway:
    name = "base"
    label = "Base"                      # shown in the checkout picker
    min_amount = Decimal("10000")       # rial

    def request(self, *, amount, description, callback_url, mobile="", email=""):
        raise NotImplementedError

    def verify(self, *, authority, amount, extra: dict | None = None):
        raise NotImplementedError

    def check_amount(self, amount):
        """Fail here rather than at the gateway, with a readable message."""
        if amount is None or Decimal(amount) <= 0:
            raise GatewayError("مبلغ باید بزرگ‌تر از صفر باشد.")
        if Decimal(amount) < self.min_amount:
            raise GatewayError(
                f"حداقل مبلغ قابل پرداخت {int(self.min_amount):,} ریال است."
            )
```

این‌که `verify()` به‌جای خطا انداختن یک شیء نتیجه برمی‌گرداند عمدی است: تأیید ناموفق یک نتیجهٔ عادی است (مشتری انصراف داده، کارت رد شده)، نه یک استثنا. فقط خرابی *زیرساخت* `GatewayError` می‌اندازد.

## ۱.۳ درایور ZarinPal

از SDK رسمی `zarinpal-py-sdk` استفاده می‌کند.

```python
class ZarinPalGateway(BaseGateway):
    name = "zarinpal"
    label = "زرین‌پال"
    min_amount = Decimal("10000")   # the SDK's validator refuses less

    def __init__(self, merchant_id=None, access_token=None, sandbox=None):
        self.merchant_id = merchant_id or settings.ZARINPAL_MERCHANT_ID
        if not self.merchant_id:
            raise GatewayError("ZARINPAL_MERCHANT_ID is not configured.")
        self.access_token = access_token or getattr(settings, "ZARINPAL_ACCESS_TOKEN", "")
        self.sandbox = settings.ZARINPAL_SANDBOX if sandbox is None else sandbox

    def _client(self):
        # Imported INSIDE the method on purpose — see Bug Z1.
        try:
            from zarinpal import ZarinPal
            from zarinpal_utils.Config import Config
        except ImportError as exc:
            raise GatewayError("zarinpal-py-sdk is not installed.") from exc
        return ZarinPal(Config(
            merchant_id=self.merchant_id,
            access_token=self.access_token,
            sandbox=self.sandbox,
        ))

    def request(self, *, amount, description, callback_url, mobile="", email=""):
        self.check_amount(amount)
        payload = {
            "amount": int(amount),              # rial
            "description": description or "Order",
            "callback_url": callback_url,
        }
        # The SDK validates mobile against ^09\d{9}$ and RAISES on anything
        # else — see Bug Z2. Only send a number that will pass.
        if mobile and mobile.startswith("09") and len(mobile) == 11:
            payload["mobile"] = mobile
        if email:
            payload["email"] = email

        client = self._client()
        try:
            body = client.payments.create(payload)
        except (ValueError, RuntimeError) as exc:
            # ValueError = SDK validation; RuntimeError wraps HTTP faults.
            raise GatewayError(f"درخواست پرداخت رد شد: {exc}") from exc

        data = (body or {}).get("data") or {}
        authority = data.get("authority")
        if not authority or data.get("code") not in (100, 101):
            errors = (body or {}).get("errors") or data
            raise GatewayError(f"درخواست پرداخت رد شد: {errors}")

        return PaymentRequest(
            authority=authority,
            redirect_url=client.payments.generate_payment_url(authority),
            raw=body,
        )

    def verify(self, *, authority, amount, extra=None):
        try:
            body = self._client().verifications.verify(
                {"amount": int(amount), "authority": authority}
            )
        except (ValueError, RuntimeError) as exc:
            return VerificationResult(success=False, message=f"تأیید ناموفق: {exc}", raw={})

        data = (body or {}).get("data") or {}
        code = data.get("code")

        if code in (100, 101):
            return VerificationResult(
                success=True,
                ref_id=str(data.get("ref_id", "")),
                card_pan=data.get("card_pan", ""),
                fee=_to_rial(data.get("fee")),   # authoritative, from the gateway
                already_verified=code == 101,
                message=data.get("message", ""),
                raw=body,
            )

        errors = (body or {}).get("errors") or data
        message = errors.get("message") if isinstance(errors, dict) else str(errors)
        return VerificationResult(success=False, message=str(message or "تأیید ناموفق."), raw=body)
```

### باگ‌های ZarinPal

**Z1 — SDK فضای نام سطح بالا را آلوده می‌کند.**
`zarinpal-py-sdk` *چهار* ماژول سطح بالا در site-packages نصب می‌کند: `zarinpal`، `resources`، `errors` و `zarinpal_utils`. نام‌هایی به این کلیت با ماژول‌های خود پروژه تداخل پیدا می‌کنند. آن را **داخل متد** import کنید، هرگز در سطح ماژول. فایدهٔ جانبی‌اش این است که اگر روی سروری SDK نصب نباشد، برنامه باز هم بالا می‌آید — فقط همین یک درایور از کار می‌افتد، نه کل برنامه.

**Z2 — SDK روی شماره موبایلی که نپسندد خطا می‌اندازد.**
`mobile` را با `^09\d{9}$` اعتبارسنجی می‌کند و `ValueError` می‌اندازد. مشتری‌ای که شماره‌اش به شکل `+98912…` ذخیره شده یا اصلاً شماره‌ای ندارد، درخواست پرداخت را از کار می‌اندازد. قبل از فرستادن، فیلد را بررسی کنید.

**Z3 — کد 101 یعنی «قبلاً تأیید شده»، و این یک موفقیت است.**
اگر هر چیزی غیر از `100` را شکست حساب کنید، یک callback تکراری (مشتری دکمهٔ برگشت را زده، یا درگاه دوباره تلاش کرده) سفارشی را که *پرداخت شده* ناموفق علامت می‌زند. هم `100` و هم `101` باید تسویه کنند.

## ۱.۴ درایور BitPay

بدون SDK؛ HTTP ساده با `requests`.

```python
class BitPayGateway(BaseGateway):
    name = "bitpay"
    label = "بیت‌پی"
    min_amount = Decimal("5000")

    LIVE_BASE = "https://bitpay.ir/payment"
    TEST_BASE = "https://bitpay.ir/payment-test"

    REQUEST_ERRORS = {
        -1: "کلید API با درگاه ثبت‌شده سازگار نیست.",
        -2: "مبلغ نامعتبر است یا کمتر از ۵۰۰۰ ریال است.",
        -3: "آدرس بازگشت خالی است.",
        -4: "درگاهی با این اطلاعات وجود ندارد یا در انتظار تأیید است.",
        -5: "خطا در اتصال به درگاه. دوباره تلاش کنید.",
    }
    VERIFY_ERRORS = {
        -1: "کلید API با درگاه ثبت‌شده سازگار نیست.",
        -2: "شناسه تراکنش عددی نیست.",
        -3: "شناسه پرداخت عددی نیست.",
        -4: "چنین تراکنشی وجود ندارد یا موفق نبوده است.",
    }

    def __init__(self, api_key=None, sandbox=None):
        self.sandbox = settings.BITPAY_SANDBOX if sandbox is None else sandbox
        self.api_key = api_key or settings.BITPAY_API_KEY
        # The documented test key. ONLY in sandbox, ONLY when nothing is set —
        # never a production fallback.
        if not self.api_key and self.sandbox:
            self.api_key = "adxcv-zzadq-polkjsad-opp13opoz-1sdf455aadzmck1244567"
        if not self.api_key:
            raise GatewayError("BITPAY_API_KEY is not configured.")

    @property
    def base(self):
        return self.TEST_BASE if self.sandbox else self.LIVE_BASE

    def _post(self, path, payload):
        import requests
        try:
            response = requests.post(f"{self.base}/{path}", data=payload, timeout=20)
            response.raise_for_status()
        except Exception as exc:
            raise GatewayError(f"درگاه بیت‌پی در دسترس نیست: {exc}") from exc
        return response

    def request(self, *, amount, description, callback_url, mobile="", email=""):
        self.check_amount(amount)
        payload = {"api": self.api_key, "amount": int(amount), "redirect": callback_url}
        if description:
            payload["description"] = description[:255]
        if email:
            payload["email"] = email
        if mobile and mobile.startswith("09") and len(mobile) == 11:
            payload["mobileNum"] = mobile   # shows the buyer's saved cards

        response = self._post("gateway-send", payload)
        body = (response.text or "").strip()

        # NOT JSON — a bare integer. Positive = id_get, negative = error code.
        try:
            code = int(body)
        except ValueError as exc:
            raise GatewayError(f"پاسخ نامعتبر از بیت‌پی: {body[:120]}") from exc

        if code <= 0:
            raise GatewayError(
                self.REQUEST_ERRORS.get(code, f"بیت‌پی درخواست را رد کرد (کد {code}).")
            )

        id_get = str(code)
        return PaymentRequest(
            authority=id_get,
            redirect_url=f"{self.base}/gateway-{id_get}-get",
            raw={"id_get": id_get, "raw": body},
        )

    def verify(self, *, authority, amount, extra=None):
        trans_id = str((extra or {}).get("trans_id") or "").strip()
        if not trans_id:
            return VerificationResult(
                success=False,
                message="شناسه تراکنش در بازگشت از بیت‌پی وجود نداشت.",
                raw={"extra": extra or {}},
            )

        response = self._post("gateway-result-second", {
            "api": self.api_key,
            "id_get": authority,
            "trans_id": trans_id,
            "json": 1,
        })

        try:
            body = response.json()
        except ValueError:
            return VerificationResult(
                success=False,
                message=f"پاسخ نامعتبر: {(response.text or '')[:120]}",
                raw={"text": (response.text or "")[:500]},
            )

        try:
            gateway_status = int(body.get("status"))
        except (TypeError, ValueError):
            return VerificationResult(success=False, message="وضعیت خوانده نشد.", raw=body)

        if gateway_status not in (1, 11):
            return VerificationResult(
                success=False,
                message=self.VERIFY_ERRORS.get(
                    gateway_status, f"تأیید ناموفق (کد {gateway_status})."
                ),
                raw=body,
            )

        # CRITICAL: check the amount the gateway reports against what we asked.
        reported = body.get("amount")
        if reported is not None:
            try:
                if Decimal(str(reported)) != Decimal(amount):
                    return VerificationResult(
                        success=False,
                        message="مبلغ تراکنش با مبلغ سفارش مطابقت ندارد.",
                        raw=body,
                    )
            except (ArithmeticError, ValueError):
                return VerificationResult(
                    success=False, message="مبلغ بازگشتی نامعتبر است.", raw=body
                )

        return VerificationResult(
            success=True,
            ref_id=trans_id,
            card_pan=str(body.get("cardNum") or ""),
            fee=self._fee_for(amount),      # estimated — see Bug B3
            already_verified=gateway_status == 11,
            message="پرداخت تأیید شد.",
            raw=body,
        )
```

کلید API که در `__init__` آمده، کلید آزمایشی عمومی‌ای است که خود BitPay در مستنداتش منتشر کرده؛ فقط در حالت sandbox و فقط وقتی هیچ کلیدی تنظیم نشده به کار می‌رود.

### باگ‌های BitPay

**B1 — `gateway-send` خروجی JSON ندارد.**
یک عدد خام به‌صورت متن برمی‌گرداند و `response.json()` خطا می‌اندازد. با `int()` پارس کنید و مقدار منفی را کد خطا در نظر بگیرید.

**B2 — تأیید به `trans_id` نیاز دارد که فقط در callback وجود دارد.**
نمی‌توانید پرداخت BitPay را فقط با رکورد ذخیره‌شدهٔ خودتان تأیید کنید. query string کامل callback باید به `verify()` برسد. کل دلیل وجود پارامتر `extra` در رابط همین است.

**B3 — BitPay هیچ‌وقت کارمزدش را به شما نمی‌گوید.**
ZarinPal کمیسیونش را در پاسخ verify گزارش می‌کند؛ BitPay نه. از روی قرارداد پذیرنده (`BITPAY_FEE_PERCENT` و `BITPAY_FEE_CAP`) یک تخمین بسازید و **در مدل داده صریحاً برچسب «تخمینی» بزنید** — قبل از این‌که به‌عنوان عدد حسابداری استفاده‌اش کنید، با پنل خود BitPay تطبیقش دهید.

**B4 — آدرس بازگشت باید دقیقاً با آدرس ثبت‌شده در پنل یکی باشد**، زیردامنه هم شامل. عدم تطابق با یک خطای بی‌فایده شکست می‌خورد.

**B5 — وضعیت `11` یعنی «قبلاً تأیید شده» و یک موفقیت است.** همان تلهٔ `101` در ZarinPal.

## ۱.۵ درگاه mock

این را **اول** بسازید. با آن می‌شود کل جریان خرید را قبل از داشتن حساب پذیرندگی از ابتدا تا انتها آزمود، و هم‌زمان fixture تست‌ها هم هست.

کدهای ZarinPal را عیناً تقلید کنید تا درایور واقعی بدون تغییر جایگزینش شود. تراکنش‌ها را در یک دیکشنری سطح کلاس نگه دارید و `settle(authority)` و `fail(authority)` را در اختیار بگذارید تا یک endpoint جعلی «صفحهٔ پرداخت» بتواند آن را هدایت کند.

```python
_mock_singleton = MockGateway()

def get_gateway(name=None):
    name = name or settings.PAYMENT_GATEWAY
    if name == "mock":
        return _mock_singleton    # ONE instance — see Bug M1
    try:
        return _GATEWAYS[name]()
    except KeyError as exc:
        raise GatewayError(f"Unknown payment gateway: {name}") from exc
```

**M1 — mock باید singleton باشد.** تراکنش‌هایش در حافظه زندگی می‌کنند. اگر در هر فراخوانی نمونهٔ تازه‌ای ساخته شود، `verify()` هیچ‌وقت چیزی را که `request()` ساخته پیدا نمی‌کند و همهٔ پرداخت‌های mock با «unknown authority» شکست می‌خورند.

**M2 — در محیط production، `mock` نباید در `PAYMENT_GATEWAYS` باشد.** اگر مشتری بتواند آن را انتخاب کند، می‌تواند سفارش را مجانی تسویه کند. بخش ۱.۷ را ببینید.

## ۱.۶ مدل Payment

تصمیم‌های کلیدی:

```python
authority = models.CharField(max_length=64, blank=True, db_index=True)

class Meta:
    constraints = [
        models.UniqueConstraint(
            fields=["gateway", "authority"],
            condition=models.Q(authority__gt=""),   # partial: blanks excluded
            name="unique_authority_per_gateway",
        )
    ]
```

* یک فیلد توکن **هر دو** درگاه را نگه می‌دارد (authority در ZarinPal و `id_get` در BitPay)، چون هر دو نقش یکسانی دارند.
* محدودیت یکتایی **به ازای هر درگاه** است، پس `id_get` برابر `12345` هیچ‌وقت با یک authority اشتباه گرفته نمی‌شود.
* محدودیت **جزئی (partial)** است (`authority__gt=""`)، وگرنه همهٔ ردیف‌هایی که هنوز منتظر توکن‌اند روی رشتهٔ خالی با هم تداخل می‌کنند.
* `trans_id` در BitPay پس از تأیید در `ref_id` ذخیره می‌شود.

## ۱.۷ ویوی درخواست — سه بررسی که اهمیت دارند

```python
# 1. Recompute the amount. Never trust a stored total: line items or
#    shipping may have changed since the order was created.
amount = order.recalculate_total()

# 2. The customer picks the gateway, but ONLY from the configured list.
#    Without this check a crafted request could name "mock" in production
#    and settle the order for free.
requested = (serializer.validated_data.get("gateway") or "").strip()
offered = available_gateways()
if requested and requested not in {g["name"] for g in offered}:
    names = "، ".join(g["label"] for g in offered) or "هیچ درگاهی"
    return Response(
        {"gateway": f"این درگاه در دسترس نیست. درگاه‌های فعال: {names}"},
        status=400,
    )

# 3. Reject orders that are already paid or in a terminal state, BEFORE
#    opening a transaction with the gateway.
```

`available_gateways()` فقط وقتی یک درگاه را به مشتری نشان می‌دهد که سه شرط با هم برقرار باشند:

1. نامش در `PAYMENT_GATEWAYS` (متغیر محیطی) آمده باشد،
2. درایورش قابل ساختن باشد (اطلاعات اتصال موجود باشد — نبودِ کلید باعث می‌شود همین‌جا کنار گذاشته شود، نه وسط پرداخت یک مشتری)،
3. در پنل مدیریت خاموش نشده باشد (یک toggle در دیتابیس).

جدا بودن toggle از اطلاعات اتصال عمدی است: ممکن است فروشگاه بخواهد یک بعدازظهر پرداخت از یک درگاه را متوقف کند، بی‌آن‌که کلیدی را که فردا لازم دارد پاک کند. خواندن از دیتابیس را در `try/except` بپیچید تا دیتابیسی که migrate نشده نتواند صفحهٔ پرداخت را از کار بیندازد.

## ۱.۸ ویوی تأیید — بخش‌هایی که بار اصلی را می‌کشند

```python
class PaymentVerifyView(APIView):
    # AllowAny is deliberate: the gateway redirects the BROWSER here and the
    # session cookie may not survive the round trip (SameSite, new tab).
    # The authority is the credential — unguessable and single-use.
    permission_classes = (AllowAny,)

    def post(self, request):  return self._handle(request.data)
    def get(self, request):   return self._handle(request.query_params)  # ZarinPal uses GET

    def _handle(self, data):
        ...
        payment = get_object_or_404(Payment, authority=authority)

        # Idempotency: report the same result rather than charging again.
        if payment.status == Payment.Status.PAID:
            return Response({"status": "paid", "already_verified": True, ...})

        if gateway_status != "OK":          # customer cancelled at the gateway
            payment.mark_failed("Cancelled at the gateway.", status=Payment.Status.CANCELLED)
            return Response({"status": "cancelled", ...}, status=402)

        result = get_gateway(payment.gateway).verify(
            authority=authority, amount=payment.amount, extra=extra
        )
        if not result.success:
            payment.mark_failed(result.message, raw=result.raw)
            return Response({"status": "failed", ...}, status=402)

        # Settle under a row lock so two concurrent callbacks cannot both
        # apply stock reservations.
        with transaction.atomic():
            locked = Payment.objects.select_for_update().get(pk=payment.pk)
            if locked.status == Payment.Status.PAID:
                payment = locked          # someone else won the race
            else:
                payment = locked.mark_paid(
                    ref_id=result.ref_id, card_pan=result.card_pan,
                    fee=result.fee, raw=result.raw,
                )
                payment.order.mark_paid(reference=f"{payment.gateway}:{result.ref_id}")
```

**P1 — verify باید هم GET و هم POST را بپذیرد.** ZarinPal مشتری را با GET و پارامترهای query برمی‌گرداند. endpointی که فقط POST بپذیرد، بی‌صدا هیچ‌وقت تسویه نمی‌کند.

**P2 — endpoint باید `AllowAny` باشد.** مرورگر از دامنهٔ یک شخص ثالث می‌رسد و کوکی نشست اغلب زنده نمی‌ماند. احراز هویت روی این endpoint یعنی پرداخت‌های واقعی تسویه نمی‌شوند. خودِ authority نقش اعتبارنامه را دارد.

**P3 — `select_for_update` دور تسویه.** بدون قفل، یک callback تکراری `order.mark_paid()` را دو بار اجرا می‌کند و موجودی دو بار رزرو می‌شود. محافظ واقعی همان بررسی `if locked.status == PAID` داخل قفل است.

**P4 — کل query string callback را به‌عنوان `extra` به `verify()` بدهید.**
وگرنه BitPay هیچ‌وقت تأیید نمی‌شود (باگ B2).

## ۱.۹ تنظیمات

```python
PAYMENT_GATEWAY  = env("PAYMENT_GATEWAY", default="mock")          # default choice
PAYMENT_GATEWAYS = env.list("PAYMENT_GATEWAYS", default=[PAYMENT_GATEWAY])  # allowlist

ZARINPAL_MERCHANT_ID   = env("ZARINPAL_MERCHANT_ID", default="")
ZARINPAL_ACCESS_TOKEN  = env("ZARINPAL_ACCESS_TOKEN", default="")
ZARINPAL_SANDBOX       = env.bool("ZARINPAL_SANDBOX", default=DEBUG)

BITPAY_API_KEY      = env("BITPAY_API_KEY", default="")
BITPAY_SANDBOX      = env.bool("BITPAY_SANDBOX", default=DEBUG)
BITPAY_FEE_PERCENT  = env("BITPAY_FEE_PERCENT", default="1.0")
BITPAY_FEE_CAP      = env("BITPAY_FEE_CAP", default="50000")

PAYMENT_CALLBACK_URL = (
    env("PAYMENT_CALLBACK_URL", default="") or f"{FRONTEND_URL}/checkout/callback"
)
MOCK_GATEWAY_URL = env("MOCK_GATEWAY_URL", default=f"{FRONTEND_URL}/checkout/mock-gateway")
```

**مبالغ به ریال هستند**، نه تومان. هر دو درگاه به ریال حساب می‌کنند. اگر رابط کاربری‌تان تومان نشان می‌دهد، در مرز سیستم و فقط *یک بار* تبدیل کنید — باگ X2 را ببینید.

---

# بخش ۲ — پیامک و OTP (SMS.ir)

## ۲.۱ دو کانال، و چرا باید از هم جدا بمانند

`SMS.ir` دو endpoint دارد و این دو جایگزین هم نیستند:

| | `/v1/send/bulk` | `/v1/send/verify` |
|---|---|---|
| محتوا | متن آزاد | یک **قالب ثبت‌شده** که با پارامتر پر می‌شود |
| خط | خط تبلیغاتی شما | یک **خط خدماتی** |
| رسیدن به شماره‌هایی که پیامک تبلیغاتی را بسته‌اند | خیر | بله |
| اولویت اپراتور | عادی | بالاتر |
| تأخیر | چند دقیقه، گاهی ده‌ها دقیقه | چند ثانیه |

**کدهای یک‌بارمصرف باید از `/send/verify` فرستاده شوند.** فرستادن کد ورود با `/send/bulk` دقیقاً همان علامت «پیامک کار می‌کند ولی خیلی دیر می‌رسد» را ایجاد می‌کند، و مشتری‌ای که پیامک تبلیغاتی را روی شماره‌اش بسته اصلاً کد را دریافت نمی‌کند. قالب‌ها در پنل `SMS.ir` ثبت می‌شوند و با یک `templateId` عددی به آن‌ها ارجاع داده می‌شود.

## ۲.۲ رابط بک‌اند

از الگوی email backend خود Django تقلید کنید: درایوری که با تنظیمات انتخاب می‌شود، با یک پیش‌فرض console که به‌جای ارسال، چاپ می‌کند.

```python
class BaseSMSBackend:
    name = "base"

    def send(self, *, to, body):
        raise NotImplementedError

    def send_verify(self, *, to, code, template_id=None, parameters=None):
        """One-time code through the provider's verify channel.
        A provider without that channel falls back to an ordinary message."""
        return self.send(to=to, body=f"کد ورود: {code}")


class ConsoleSMSBackend(BaseSMSBackend):
    """The default in development and in tests."""
    name = "console"

    def send(self, *, to, body):
        logger.info("SMS -> %s\n%s", to, body)
        return {"provider": "console", "to": to, "status": "logged"}

    def send_verify(self, *, to, code, template_id=None, parameters=None):
        # Log the code so a developer can complete a login locally
        # without a provider account.
        logger.info("SMS VERIFY -> %s  code=%s", to, code)
        return {"provider": "console", "to": to, "code": str(code)}
```

## ۲.۳ درایور SMS.ir

```python
class SmsIrBackend(BaseSMSBackend):
    name = "smsir"
    BASE = "https://api.sms.ir/v1"

    STATUS_TEXT = {
        10: "کلید وب‌سرویس نامعتبر است.",
        11: "کلید وب‌سرویس غیرفعال است.",
        12: "کلید وب‌سرویس محدود به آی‌پی‌های تعریف‌شده است.",
        13: "حساب کاربری غیرفعال است.",
        14: "حساب کاربری در حالت تعلیق است.",
        20: "تعداد درخواست بیشتر از حد مجاز است.",
        101: "شماره خط نامعتبر است.",
        102: "اعتبار پنل پیامک کافی نیست.",
        104: "شماره موبایل نادرست است.",
        113: "قالب پیامک یافت نشد.",
        114: "مقدار پارامتر بیش از ۲۵ کاراکتر است.",
        115: "شماره موبایل در لیست سیاه سامانه است.",
        116: "نام پارامتر قالب مقداردهی نشده است.",
    }

    def __init__(self):
        self.api_key = settings.SMSIR_API_KEY
        if not self.api_key:
            raise SMSError("SMSIR_API_KEY is not configured.")
        self.line_number = settings.SMSIR_LINE_NUMBER

    def _headers(self):
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "x-api-key": self.api_key,
        }

    def _post(self, path, payload):
        import time, requests

        started = time.monotonic()
        try:
            response = requests.post(
                f"{self.BASE}{path}", json=payload,
                headers=self._headers(), timeout=settings.SMSIR_TIMEOUT,
            )
        except Exception as exc:
            raise SMSError(f"SMS provider unreachable: {exc}") from exc

        # Log how long the provider took to ACCEPT. A slow SMS has two very
        # different causes that look identical from outside: a slow call here,
        # or a fast accept and slow delivery on the operator's side.
        # Only this number tells them apart.
        elapsed = time.monotonic() - started
        (logger.warning if elapsed > 3 else logger.info)(
            "SMS.ir %s accepted in %.2fs", path, elapsed
        )

        try:
            body = response.json()
        except ValueError:
            raise SMSError(f"non-JSON response (HTTP {response.status_code}).") from None

        # HTTP 200 does NOT mean accepted. The body's `status` must be 1.
        status = body.get("status")
        if status != 1:
            detail = self.STATUS_TEXT.get(status) or body.get("message") or "خطای نامشخص"
            raise SMSError(
                f"SMS rejected (HTTP {response.status_code}, status {status}): "
                f"{detail} — {body.get('message')!r} on {path}"
            )
        return body.get("data") or {}

    def send(self, *, to, body):
        # lineNumber is typed as a NUMBER by the API; a quoted string is
        # rejected as status 101. Cast only when it is all digits, so a
        # malformed setting produces the provider's own error, not a TypeError.
        line = int(self.line_number) if str(self.line_number).isdigit() else self.line_number
        return self._post("/send/bulk", {
            "lineNumber": line,
            "messageText": body,
            "mobiles": [_normalise(to)],
        })

    def send_verify(self, *, to, code, template_id=None, parameters=None):
        template = template_id or settings.SMSIR_VERIFY_TEMPLATE_ID
        if not template:
            raise SMSError("SMSIR_VERIFY_TEMPLATE_ID is not configured.")
        if parameters is None:
            parameters = [{"name": settings.SMSIR_VERIFY_PARAM, "value": str(code)}]
        return self._post("/send/verify", {
            "mobile": _normalise(to),
            "templateId": int(template),
            "parameters": _clip(parameters),
        })
```

### دو تابع کمکی نرمال‌سازی — هر دو رفع باگ هستند

```python
PARAM_MAX = 25

def _clip(parameters):
    """Trim every template parameter to the provider's limit.

    SMS.ir rejects the WHOLE message with status 114 when any parameter
    exceeds 25 characters. Enforced here, not at each call site: a caller
    that forgets loses the message entirely, and it only shows up in
    production against a name that happens to be long.
    """
    return [
        {"name": p["name"], "value": str(p.get("value") or "")[:PARAM_MAX]}
        for p in parameters
    ]


def _normalise(number):
    """Reduce anything a customer types to what SMS.ir expects: 9121234567.

    The provider types mobile numbers as int64, so the leading zero is NOT
    part of the format — 09121234567 is rejected.
    """
    # digits_only(), NOT str.isdigit(): the latter returns True for Persian
    # and Arabic-Indic numerals, so ۰۹۱۲… would pass through unchanged and
    # reach the provider in a script it cannot read.
    digits = digits_only(number)
    if digits.startswith("0098"):
        digits = digits[4:]
    elif digits.startswith("98") and len(digits) == 12:
        digits = digits[2:]
    elif digits.startswith("0") and len(digits) == 11:
        digits = digits[1:]
    return digits
```

تابع کمکی ارقام که این‌ها به آن وابسته‌اند:

```python
_PERSIAN = "۰۱۲۳۴۵۶۷۸۹"
_ARABIC  = "٠١٢٣٤٥٦٧٨٩"
_TRANSLATION = {ord(c): str(i) for i, c in enumerate(_PERSIAN)}
_TRANSLATION.update({ord(c): str(i) for i, c in enumerate(_ARABIC)})

def to_english_digits(value):
    if not isinstance(value, str):
        return value
    return value.translate(_TRANSLATION)

def digits_only(value):
    if not isinstance(value, str):
        return value
    return "".join(c for c in to_english_digits(value) if c.isdigit())
```

### باگ‌های SMS.ir

**S1 — صفر ابتدای شماره باید حذف شود.** `SMS.ir` شماره موبایل را int64 در نظر می‌گیرد. `09121234567` رد می‌شود؛ `9121234567` را می‌خواهد. مستندات `"Mobile": "9120000000"` را نشان می‌دهد — به‌راحتی از چشم می‌افتد. **این یکی بی‌صدا هیچ پیامکی نمی‌فرستد.**

**S2 — `str.isdigit()` برای ارقام فارسی `True` برمی‌گرداند.** `"۰۹۱۲".isdigit()` برابر `True` است. هر اعتبارسنجی یا فیلتری که روی `isdigit()` ساخته شده باشد، ارقام فارسی را بدون تبدیل رد می‌کند و ارائه‌دهنده رشته‌ای دریافت می‌کند که نمی‌تواند پارسش کند. از یک جدول تبدیل صریح استفاده کنید. *(این باگ فقط به این دلیل پیدا شد که تستی که برای S1 نوشته شده بود شکست خورد.)*

**S3 — `lineNumber` باید عدد صحیح باشد، نه رشته.** شمارهٔ خطی که داخل کوتیشن باشد، وضعیت 101 «خط نامعتبر» برمی‌گرداند.

**S4 — HTTP 200 همراه با `status != 1` یعنی رد شده.** `raise_for_status()` کافی نیست. همیشه بدنهٔ پاسخ را بررسی کنید.

**S5 — یک پارامتر ۲۶ کاراکتری کل پیام را از بین می‌برد** (وضعیت 114)، نه فقط همان پارامتر را. کوتاه‌سازی را در یک نقطهٔ مرکزی انجام دهید.

**S6 — برای کدها از `/send/verify` استفاده کنید، نه `/send/bulk`.** بخش ۲.۱ را ببینید. علامت اشتباه در این مورد «پیامک کار می‌کند ولی خیلی کند است» است.

**S7 — تأخیر پذیرش را لاگ کنید.** بدون آن نمی‌توانید کندی فراخوانی API را از کندی تحویل اپراتور تشخیص دهید، و چیز اشتباهی را تنظیم خواهید کرد.

## ۲.۴ OTP: صدور و بررسی

سیاست را بیرون از ویوها نگه دارید.

```python
def generate_code():
    """`secrets`, not `random`: random is seeded predictably and its output
    can be reconstructed from earlier values — for a login code that means
    an attacker who requests a few codes could compute someone else's."""
    upper = 10 ** settings.OTP_CODE_LENGTH
    return str(secrets.randbelow(upper)).zfill(settings.OTP_CODE_LENGTH)


def issue(phone, *, ip=None, purpose=PhoneOTP.Purpose.LOGIN):
    """Create and store a code, returning (otp, raw_code).
    The caller sends the raw code; only its hash is kept, so this is the
    one moment it exists."""
    now = timezone.now()
    recent = PhoneOTP.objects.filter(
        phone=phone, purpose=purpose, created_at__gte=now - timedelta(hours=1)
    )

    # Resend throttle FIRST: it is the limit an ordinary impatient customer
    # actually hits, and it produces the more useful message of the two.
    latest = recent.order_by("-created_at").first()
    if latest:
        wait = settings.OTP_RESEND_SECONDS - (now - latest.created_at).total_seconds()
        if wait > 0:
            raise OTPError(f"برای دریافت کد جدید {int(wait)} ثانیه صبر کنید.",
                           retry_after=int(wait))

    if recent.count() >= settings.OTP_MAX_PER_HOUR:
        raise OTPError("تعداد درخواست کد بیش از حد مجاز است.", retry_after=3600)

    raw = generate_code()
    otp = PhoneOTP.objects.create(
        phone=phone,
        code_hash=make_password(raw),        # hashed, never stored in clear
        purpose=purpose,
        requested_ip=ip,
        expires_at=now + timedelta(seconds=settings.OTP_TTL_SECONDS),
    )
    return otp, raw


def verify(phone, code, *, purpose=PhoneOTP.Purpose.LOGIN):
    """Check against the NEWEST live code only.

    Asking for a second code must invalidate the first in practice, or two
    codes are usable at once and the rate limit buys an attacker MORE
    guesses rather than fewer.
    """
    otp = (PhoneOTP.objects
           .filter(phone=phone, purpose=purpose, is_used=False)
           .order_by("-created_at").first())

    if otp is None:
        raise OTPError("کدی برای این شماره صادر نشده است.")
    if otp.is_expired:
        raise OTPError("این کد منقضی شده است.")
    if otp.attempts >= settings.OTP_MAX_ATTEMPTS:
        raise OTPError("تعداد تلاش‌های نادرست بیش از حد مجاز است.")
    if not otp.check_code(code):
        left = max(0, settings.OTP_MAX_ATTEMPTS - otp.attempts)
        raise OTPError(f"کد نادرست است. {left} تلاش باقی مانده." if left
                       else "کد نادرست است و این کد باطل شد.")
    return otp
```

### مدل

```python
class PhoneOTP(models.Model):
    phone       = models.CharField(max_length=20, db_index=True)
    code_hash   = models.CharField(max_length=128)
    attempts    = models.PositiveSmallIntegerField(default=0)
    is_used     = models.BooleanField(default=False)
    requested_ip= models.GenericIPAddressField(null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True, db_index=True)
    expires_at  = models.DateTimeField()

    class Meta:
        indexes = [models.Index(fields=["phone", "-created_at"])]

    def check_code(self, raw):
        """Verify, counting the attempt either way.

        The attempt is recorded BEFORE the answer is returned, so a caller
        that forgets to save cannot accidentally give away unlimited guesses.
        """
        if not self.is_live:
            return False
        if check_password(str(raw), self.code_hash):
            self.is_used = True
            self.save(update_fields=["is_used"])
            return True
        self.attempts += 1
        self.save(update_fields=["attempts"])
        return False
```

چهار ویژگی امنیتی، که هر کدام بار اصلی را می‌کشند:

* **کد هش می‌شود و هرگز به‌صورت خام ذخیره نمی‌شود.** یک dump از دیتابیس — یا یک نگاه به پنل ادمین — نباید به کسی اجازه دهد به‌جای مشتری وارد شود.
* **هر ردیف با اولین استفادهٔ موفق سوزانده می‌شود**، پس یک کد در طول عمرش دوباره قابل استفاده نیست.
* **حدس‌های اشتباه کد را از بین می‌برند، نه حساب را.** مهاجمی که روی شمارهٔ کسی حدس می‌زند نباید بتواند او را از ورود به حساب خودش محروم کند.
* **محدودیت نرخ به ازای هر شماره و هر ساعت است**، و همین جلوی استفاده از endpoint برای خرج کردن اعتبار پیامک فروشگاه را می‌گیرد.

### نرمال‌سازی شماره برای ذخیره

دقت کنید که این شکل با آن‌چه `SMS.ir` می‌خواهد *فرق دارد* — به شکل `09…` ذخیره می‌شود و به شکل `9…` فرستاده می‌شود:

```python
def normalise_phone(raw):
    """Reduce the forms customers type to one stored shape: 09xxxxxxxxx.
    Without this, 09121234567, +989121234567 and ۰۹۱۲۱۲۳۴۵۶۷ would be three
    different accounts for one person."""
    digits = digits_only(raw or "")
    if digits.startswith("98") and len(digits) == 12:
        digits = "0" + digits[2:]
    elif digits.startswith("9") and len(digits) == 10:
        digits = "0" + digits
    return digits
```

## ۲.۵ endpointهای OTP

```python
class OTPRequestThrottle(AnonRateThrottle):
    """A ceiling per IP, ON TOP OF the per-number limit in issue().

    The per-number limit stops one customer being spammed; this stops one
    machine walking through many numbers to burn the SMS credit.
    """
    scope = "otp"


@api_view(["POST"])
@permission_classes((AllowAny,))
@throttle_classes([OTPRequestThrottle])
def request_code(request):
    phone = normalise_phone(request.data.get("phone"))
    if not is_valid_phone(phone):
        return Response({"phone": "شماره موبایل باید ۱۱ رقم و با ۰۹ شروع شود."}, status=400)

    try:
        otp, raw = issue(phone, ip=_client_ip(request))
    except OTPError as exc:
        return Response({"detail": exc.message, "retry_after": exc.retry_after}, status=429)

    # Sent INLINE, not through Celery: the customer is staring at the screen
    # waiting for it, and a queued task that fails silently leaves them on a
    # code-entry form with no code coming.
    try:
        send_verify_sms(to=phone, code=raw)
    except SMSError as exc:
        logger.error("OTP send failed for %s: %s", phone, exc)
        # The row STAYS. Deleting it here would let a broken provider be
        # used to bypass the rate limit.
        return Response({"detail": "ارسال پیامک ناموفق بود."}, status=502)

    return Response({
        "is_new": not User.objects.filter(phone=phone).exists(),
        "expires_in": (otp.expires_at - otp.created_at).seconds,
        "resend_after": settings.OTP_RESEND_SECONDS,   # so the client can
    })                                                 # disable its own button


@api_view(["POST"])
@permission_classes((AllowAny,))
def verify_code(request):
    phone = normalise_phone(request.data.get("phone"))
    code = str(request.data.get("code") or "").strip()
    ...
    try:
        verify(phone, code)
    except OTPError as exc:
        return Response({"detail": exc.message}, status=400)

    user, created = _get_or_create_user(phone, request.data.get("name"))

    # Checked AFTER the code, so a disabled account cannot be probed by the
    # difference in response.
    if not user.is_active:
        return Response({"detail": "این حساب غیرفعال است."}, status=403)

    payload = issue_tokens(user)
    payload["created"] = created
    return Response(payload)
```

IP کلاینت پشت پراکسی:

```python
def _client_ip(request):
    # Only the FIRST entry is ours — the rest can be forged by the caller.
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")
```

ساختن حساب برای مشتری‌ای که فقط شماره موبایل دارد:

```python
def _get_or_create_user(phone, name=None):
    # `phone` is not unique on the user model — an email-registered customer
    # may have typed the same number — so the NEWEST match wins rather than
    # the query raising. Deterministic matters: an ambiguous login that
    # sometimes lands in a different account is worse than either choice.
    existing = User.objects.filter(phone=phone).order_by("-date_joined").first()
    if existing:
        return existing, False

    with transaction.atomic():
        user = User.objects.create_user(
            # A unique email is required; a phone-only customer has none.
            # `.invalid` is reserved by RFC 2606 so it can never be delivered to.
            email=f"{phone}@phone.example.invalid",
            password=None,        # unusable password: this account logs in by code
            phone=phone,
            first_name=(name or "").strip()[:60],
        )
    return user, True
```

### باگ‌های OTP

**O1 — کد را درجا (inline) بفرستید، نه از طریق Celery.** taskی که در صف شکست بخورد، مشتری را برای همیشه روی صفحهٔ واردکردن کد نگه می‌دارد. اگر ارائه‌دهنده از دسترس خارج است، مشتری باید *همین حالا* با یک 502 بفهمد.

**O2 — وقتی ارسال شکست خورد، ردیف OTP را پاک نکنید.** این کار یک ارائه‌دهندهٔ خراب را به راهی برای دور زدن محدودیت نرخ تبدیل می‌کند.

**O3 — `is_active` را بعد از تأیید کد بررسی کنید**، نه قبل از آن؛ وگرنه تفاوت پاسخ‌ها لو می‌دهد کدام شماره‌ها حساب دارند.

**O4 — فقط جدیدترین کد باید معتبر باشد.** وگرنه درخواست ۵ کد به مهاجم به‌جای `OTP_MAX_ATTEMPTS` حدس، ۵ × `OTP_MAX_ATTEMPTS` حدس می‌دهد.

## ۲.۶ تنظیمات

```python
SMS_BACKEND = env("SMS_BACKEND", default="console")   # console | smsir | kavenegar
SMS_SENDER  = env("SMS_SENDER", default="YourShop")

SMSIR_API_KEY      = env("SMSIR_API_KEY", default="")
SMSIR_LINE_NUMBER  = env("SMSIR_LINE_NUMBER", default="")
SMSIR_TIMEOUT      = env.float("SMSIR_TIMEOUT", default=8.0)

# One template id per message the shop sends, each registered in the panel.
SMSIR_VERIFY_TEMPLATE_ID  = env("SMSIR_VERIFY_TEMPLATE_ID", default="")
SMSIR_VERIFY_PARAM        = env("SMSIR_VERIFY_PARAM", default="CODE")
SMSIR_WELCOME_TEMPLATE_ID = env("SMSIR_WELCOME_TEMPLATE_ID", default="")
SMSIR_ORDER_TEMPLATE_ID   = env("SMSIR_ORDER_TEMPLATE_ID", default="")
SMSIR_ORDER_PARAM         = env("SMSIR_ORDER_PARAM", default="ORDER_STATUS")
SMSIR_ORDER_CODE_PARAM    = env("SMSIR_ORDER_CODE_PARAM", default="ORDER_CODE")

OTP_CODE_LENGTH    = env.int("OTP_CODE_LENGTH", default=5)
OTP_TTL_SECONDS    = env.int("OTP_TTL_SECONDS", default=120)
OTP_MAX_PER_HOUR   = env.int("OTP_MAX_PER_HOUR", default=5)
OTP_MAX_ATTEMPTS   = env.int("OTP_MAX_ATTEMPTS", default=5)
OTP_RESEND_SECONDS = env.int("OTP_RESEND_SECONDS", default=60)

REST_FRAMEWORK = {
    "DEFAULT_THROTTLE_RATES": {
        "otp": env("OTP_IP_RATE", default="20/hour"),
    },
}
```

**نام** پارامترهای قالب قابل تنظیم است، چون این نام‌ها هنگام ثبت قالب در پنل `SMS.ir` انتخاب می‌شوند و باید دقیقاً یکی باشند. عدم تطابق، وضعیت 116 برمی‌گرداند.

---

# بخش ۳ — تله‌های مشترک

این‌ها مخصوص هیچ‌کدام از دو زیرسیستم نیستند، و روی هم رفته بیشتر از کل کدهای بالا وقت گرفتند.

## X1 — بخش `environment:` در Docker Compose یک لیست مجاز (allowlist) است

**این پرهزینه‌ترین باگ کل این پروژه است.** سه بار جداگانه به آن خوردیم.

اگر یک سرویس `environment:` را صریحاً فهرست کرده باشد، متغیری که *آن‌جا نامش نیامده* هرگز به کانتینر نمی‌رسد، هر طور هم که در `.env` تنظیم شده باشد. برنامه بدون هیچ خطایی «تنظیم‌نشده» اجرا می‌شود: پیامک بی‌صدا کاری نمی‌کند و درگاه پرداخت بی‌صدا روی mock می‌ماند.

```yaml
x-api-env: &api-env
  # This block is an ALLOWLIST. Every setting the code reads has to be named
  # here, or the driver silently runs unconfigured.
  SMSIR_API_KEY: ${SMSIR_API_KEY:-}
  SMSIR_LINE_NUMBER: ${SMSIR_LINE_NUMBER:-}
  SMSIR_VERIFY_TEMPLATE_ID: ${SMSIR_VERIFY_TEMPLATE_ID:-}
  # ... every single SMSIR_*, OTP_*, ZARINPAL_*, BITPAY_*, PAYMENT_*
```

دستور عیب‌یابی که با یک فرمان پیدایش می‌کند:

```bash
docker compose exec api printenv | grep -E "SMSIR|ZARINPAL|BITPAY|OTP_"
```

اگر متغیری که در `.env` تنظیم کرده‌اید در این خروجی نیست، باگ شما همین است.

نکتهٔ مرتبط: **فایل `.env` باید کنار `docker-compose.yml` باشد**، نه داخل پوشهٔ backend. Compose آن را از ریشهٔ پروژه می‌خواند.

## X2 — تومان در برابر ریال

درگاه‌ها به **ریال** حساب می‌کنند. فروشگاه‌های ایرانی **تومان** نمایش می‌دهند (هر تومان = ۱۰ ریال). فقط یک بار و در یک مرز مشخص تبدیل کنید، و واحد را در نام هر فیلد و هر docstring بنویسید. اشتباه در این مورد از مشتری ۱۰ برابر یا یک‌دهم مبلغ را می‌گیرد و تا وقتی کسی شکایت نکند دیده نمی‌شود.

## X3 — `autodiscover_tasks()` در Celery فقط `tasks.py` را import می‌کند

اگر taskها را در ماژول دیگری بگذارید، کانتینر وب آن را import می‌کند (پس `.delay()` موفق می‌شود و کار در صف قرار می‌گیرد) ولی ورکر هرگز import نمی‌کند — در نتیجه ورکر چنین taskی را ثبت‌شده ندارد و **آن را بی‌صدا دور می‌اندازد**. علامتش taskی است که بدون خطا در صف قرار می‌گیرد و هیچ‌وقت اجرا نمی‌شود.

```python
app.autodiscover_tasks()                        # finds tasks.py
app.autodiscover_tasks(related_name="feed")     # ...and only tasks.py
```

با تستی از آن محافظت کنید که ثبت‌شدن نام همهٔ taskهای مورد انتظار را بررسی می‌کند:

```python
from config.celery import app

EXPECTED = ["feed.order_placed", "feed.payment_confirmed", ...]

def test_every_task_is_registered():
    """A task missing here is one the worker will silently drop."""
    missing = [name for name in EXPECTED if name not in app.tasks]
    assert not missing, f"not registered on the worker: {missing}"
```

بعد، قبل از این‌که به آن اعتماد کنید، **خط `related_name` را غیرفعال کنید و ببینید تست قرمز می‌شود**. وقتی این کار در پروژهٔ اصلی انجام شد، تست ۱۳ شکست داد — و تنها دلیلی که می‌دانیم تست کار می‌کند همین است.

## X4 — هرگز اطلاعات محرمانه را در دیتابیس نگذارید

کلیدهای پذیرنده و کلیدهای API جایشان در `.env` **روی سرور** است:

* کلیدی که در دیتابیس باشد، برای هر کسی که به پنل ادمین برسد خواناست،
* و از هر بکاپی از دیتابیس قابل بازیابی است.

هر کسی کلید API پیامک را داشته باشد می‌تواند به هزینهٔ حساب شما پیامک بفرستد؛ هر کسی کلید پذیرنده را داشته باشد می‌تواند جای فروشگاه عمل کند. اگر کلیدی حتی یک بار در یک چت، یک تیکت یا یک commit قرار گرفت — **آن را عوض کنید (rotate)**؛ فقط پاک کردن پیام کافی نیست.

## X5 — هرگز `.env` را داخل فایل فشردهٔ استقرار نفرستید

صریحاً مستثنایش کنید و قبل از ارسال بررسی کنید:

```bash
tar czf update.tar.gz --exclude='.env' --exclude='.env.*' \
    --exclude='node_modules' --exclude='.venv' --exclude='*.sqlite3' .
tar tzf update.tar.gz | grep -cE '\.env|node_modules'   # must print 0
```

## X6 — برای هر یکپارچه‌سازی یک اسکریپت probe بسازید

وقتی چیزی کار نمی‌کند، حدس زدن را کنار بگذارید و بگذارید *سرور* جواب بدهد. اسکریپتی که داخل کانتینر اجرا می‌شد و نتیجهٔ واقعی هر مرحله را چاپ می‌کرد، باگ Celery را در یک اجرا پیدا کرد — بعد از این‌که دو حدس اشتباه یک ساعت وقت گرفته بودند.

آن را به شکل مراحل شماره‌دار بسازید که هر کدام دقیقاً چیزی را که گرفته چاپ کند:

```text
1. is the setting visible in the container?
2. can the driver be constructed?
3. does a minimal API call succeed, and what exactly comes back?
4. does the queued path work, or only the inline one?
```

---

# بخش ۴ — ترتیب پیاده‌سازی

به همین ترتیب بسازید. هر مرحله قبل از وجود مرحلهٔ بعد قابل تست است.

1. **بک‌اند پیامک console + مدل‌ها و سیاست OTP.** کل جریان ورود با کدی که در لاگ چاپ می‌شود کار می‌کند. حساب ارائه‌دهندهٔ پیامک لازم نیست.
2. **درگاه پرداخت mock + کل جریان خرید.** سفارش‌ها را می‌شود از ابتدا تا انتها ثبت و تسویه کرد. حساب پذیرندگی لازم نیست.
3. **همین حالا تست‌ها را بنویسید**، روی mock و console. وقتی درایورهای واقعی اضافه شوند هم معتبر می‌مانند، چون رابط تغییر نمی‌کند.
4. **`SMS.ir` را اضافه کنید.** اول قالب‌ها را در پنل ثبت کنید؛ `templateId` هر کدام و نام دقیق پارامترهایش را یادداشت کنید.
5. **`ZarinPal` و `BitPay` را اضافه کنید**، در حالت sandbox. هر دو اطلاعات اتصال آزمایشی مستند دارند.
6. **راه‌اندازی واقعی**: کلیدهای واقعی در `.env` روی سرور، `PAYMENT_GATEWAYS` بدون `mock`، و قبل از باز کردن فروشگاه **از طریق هر درگاه یک سفارش واقعی کوچک ثبت کنید**. قبول شدن در sandbox دلیلی بر کار کردن در production نیست — قرارداد پذیرنده، آدرس بازگشت ثبت‌شده و شمارهٔ خط در production همه متفاوت‌اند.

## تستی که ارزش نوشتن دارد

وقتی باگی را رفع می‌کنید، قبل از اعتماد به تست، عمداً کاری کنید که شکست بخورد. دو تا از تست‌هایی که برای این پروژه نوشته شده بودند چیز اشتباهی را بررسی می‌کردند:

* تست نرمال‌سازی OTP *خودِ باگ صفر ابتدایی را کدگذاری کرده بود* — بررسی می‌کرد که `_normalise()` مقدار `09121234567` را برگرداند. سبز نگه داشتن آن، قالب اشتباه را برای همیشه قفل می‌کرد.
* یک تست ترتیب DOM به دلیل اشتباهی قبول می‌شد و نمی‌توانست هیچ regressionی را بگیرد.

رفع باگ را غیرفعال کنید، قرمز شدن تست را ببینید، و دوباره برگردانیدش. تستی که شکست خوردنش را ندیده‌اید، مدرک هیچ چیزی نیست.
