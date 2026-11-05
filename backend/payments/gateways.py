"""Payment gateway drivers.

Three drivers behind one interface: a mock for development, ZarinPal via its
official SDK, and BitPay. Nothing above this layer knows which is running —
`get_gateway(name)` returns something with `.request()` and `.verify()`.

The two real gateways differ in shape, and this module is where that is
absorbed:

  ZarinPal  request -> authority (36 chars, 'A'|'S' + 35)
            redirect to /pg/StartPay/<authority>
            callback ?Authority=...&Status=OK|NOK
            verify(authority, amount) -> code 100 ok, 101 already verified

  BitPay    request -> id_get (a positive integer)
            redirect to /payment/gateway-<id_get>-get
            callback ?trans_id=...&id_get=...
            verify(id_get, trans_id) -> status 1 ok, 11 already verified

So BitPay needs a second identifier at verification time that ZarinPal does
not have. `verify()` therefore takes an optional `extra` dict; the callback
view passes the whole query string through and each driver reads what it needs.
"""

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django.conf import settings
from django.utils.crypto import get_random_string


class GatewayError(Exception):
    """The gateway refused the request or returned something unusable."""


def _to_rial(value):
    """A gateway-reported figure as whole rial, or zero if it is unusable.

    Fees are bookkeeping, not authorisation: a missing or malformed one must
    never turn a settled payment into a failed one.
    """
    if value in (None, ""):
        return Decimal("0")
    try:
        return Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ArithmeticError, ValueError, TypeError):
        return Decimal("0")


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
    # What the gateway takes for itself, in rial. The shop absorbs it; it is
    # never added to what the customer pays. ZarinPal reports it, BitPay does
    # not, so for BitPay this is an estimate from the merchant contract.
    fee: Decimal = Decimal("0")
    raw: dict = field(default_factory=dict)


class BaseGateway:
    name = "base"

    #: Shown in the checkout picker.
    label = "Base"

    #: Smallest amount the gateway accepts, in rial.
    min_amount = Decimal("10000")

    def request(self, *, amount: Decimal, description: str, callback_url: str, mobile="", email=""):
        raise NotImplementedError

    def verify(self, *, authority: str, amount: Decimal, extra: dict | None = None):
        raise NotImplementedError

    def check_amount(self, amount):
        """Fail here rather than at the gateway, with a sentence in Persian."""
        if amount is None or Decimal(amount) <= 0:
            raise GatewayError("مبلغ باید بزرگ‌تر از صفر باشد.")
        if Decimal(amount) < self.min_amount:
            raise GatewayError(
                f"حداقل مبلغ قابل پرداخت {int(self.min_amount):,} ریال است."
            )


class MockGateway(BaseGateway):
    """A stand-in that never leaves the process.

    It holds transactions in memory and hands back a callback URL pointing at
    our own mock pay page, so the whole flow is exercisable end to end without
    a merchant account. Mirrors ZarinPal's codes so the real driver is a drop-in
    replacement.
    """

    name = "mock"
    label = "درگاه آزمایشی"
    # Deliberately permissive: dev orders are often a few hundred rial.
    min_amount = Decimal("1")

    # authority -> {amount, verified, ref_id}
    _transactions: dict = {}

    def request(self, *, amount, description, callback_url, mobile="", email=""):
        self.check_amount(amount)

        authority = "A" + get_random_string(35, "0123456789")
        self._transactions[authority] = {
            "amount": Decimal(amount),
            "verified": False,
            "ref_id": "",
        }

        base = settings.MOCK_GATEWAY_URL.rstrip("/")
        separator = "&" if "?" in callback_url else "?"
        redirect = (
            f"{base}/{authority}/"
            f"?callback={callback_url}{separator}Authority={authority}"
        )

        return PaymentRequest(
            authority=authority,
            redirect_url=redirect,
            raw={"code": 100, "authority": authority, "message": "Mock request created."},
        )

    def verify(self, *, authority, amount, extra=None):
        transaction = self._transactions.get(authority)

        if transaction is None:
            return VerificationResult(
                success=False,
                message="Unknown authority.",
                raw={"code": -51, "message": "Session does not exist."},
            )

        # Guards against a tampered callback that reports a different figure.
        if transaction["amount"] != Decimal(amount):
            return VerificationResult(
                success=False,
                message="Amount does not match the original request.",
                raw={"code": -54, "message": "Amount mismatch."},
            )

        # ZarinPal answers 101 when a transaction is verified twice. Treat it as
        # success so a double callback is idempotent, not a false failure.
        if transaction["verified"]:
            return VerificationResult(
                success=True,
                ref_id=transaction["ref_id"],
                already_verified=True,
                message="Already verified.",
                raw={"code": 101, "ref_id": transaction["ref_id"]},
            )

        ref_id = get_random_string(11, "0123456789")
        transaction["verified"] = True
        transaction["ref_id"] = ref_id

        return VerificationResult(
            success=True,
            ref_id=ref_id,
            card_pan="6037********1234",
            message="Verified.",
            raw={"code": 100, "ref_id": ref_id, "card_pan": "6037********1234"},
        )

    # --- Test/dev helpers -------------------------------------------------
    def settle(self, authority):
        """Mark a transaction payable, as the hosted pay page would."""
        return authority in self._transactions

    def fail(self, authority):
        """Drop a transaction so verification reports failure."""
        self._transactions.pop(authority, None)


class ZarinPalGateway(BaseGateway):
    """ZarinPal, through the official `zarinpal-py-sdk`.

    The SDK is imported inside methods on purpose. It installs four modules at
    the top level of site-packages — `zarinpal`, `resources`, `errors` and
    `zarinpal_utils` — names generic enough to collide with project modules.
    Confining the import to this class keeps that surface as small as possible,
    and means a deployment without the SDK still boots (only this driver fails).
    """

    name = "zarinpal"
    label = "زرین‌پال"
    # The SDK's own Validator refuses anything under 10,000 rial.
    min_amount = Decimal("10000")

    def __init__(self, merchant_id=None, access_token=None, sandbox=None):
        self.merchant_id = merchant_id or settings.ZARINPAL_MERCHANT_ID
        if not self.merchant_id:
            raise GatewayError("ZARINPAL_MERCHANT_ID is not configured.")

        self.access_token = access_token or getattr(settings, "ZARINPAL_ACCESS_TOKEN", "")
        self.sandbox = (
            settings.ZARINPAL_SANDBOX if sandbox is None else sandbox
        )

    def _client(self):
        try:
            from zarinpal import ZarinPal
            from zarinpal_utils.Config import Config
        except ImportError as exc:  # pragma: no cover - deployment problem
            raise GatewayError(
                "zarinpal-py-sdk is not installed; run pip install -r requirements.txt."
            ) from exc

        return ZarinPal(
            Config(
                merchant_id=self.merchant_id,
                access_token=self.access_token,
                sandbox=self.sandbox,
            )
        )

    def request(self, *, amount, description, callback_url, mobile="", email=""):
        self.check_amount(amount)

        payload = {
            # Prices are stored in rial, which is what ZarinPal bills in.
            "amount": int(amount),
            "description": description or "Senobar order",
            "callback_url": callback_url,
        }
        # The SDK validates mobile against ^09\d{9}$ and raises on anything
        # else, so only send a number that will pass.
        if mobile and mobile.startswith("09") and len(mobile) == 11:
            payload["mobile"] = mobile
        if email:
            payload["email"] = email

        client = self._client()
        try:
            body = client.payments.create(payload)
        except (ValueError, RuntimeError) as exc:
            # ValueError is the SDK's validation; RuntimeError wraps HTTP faults.
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
            return VerificationResult(
                success=False, message=f"تأیید پرداخت ناموفق بود: {exc}", raw={}
            )

        data = (body or {}).get("data") or {}
        code = data.get("code")

        if code in (100, 101):
            return VerificationResult(
                success=True,
                ref_id=str(data.get("ref_id", "")),
                card_pan=data.get("card_pan", ""),
                # ZarinPal states its own commission in the verify payload, so
                # this is the authoritative figure rather than an estimate.
                fee=_to_rial(data.get("fee")),
                already_verified=code == 101,
                message=data.get("message", ""),
                raw=body,
            )

        errors = (body or {}).get("errors") or data
        message = errors.get("message") if isinstance(errors, dict) else str(errors)
        return VerificationResult(
            success=False, message=str(message or "تأیید پرداخت ناموفق بود."), raw=body
        )


class BitPayGateway(BaseGateway):
    """BitPay (bitpay.ir).

    Two-step like ZarinPal, but with two identifiers instead of one: the
    request returns `id_get`, and the callback adds `trans_id`. Verification
    needs both. We store `id_get` in Payment.authority — it is what the request
    produced and what the callback echoes back — and keep `trans_id` in
    Payment.ref_id once verified.

    Amounts are rial, minimum 5,000. The gateway is sensitive to the redirect
    URL matching the one registered in the panel, subdomain included.
    """

    name = "bitpay"
    label = "بیت‌پی"
    min_amount = Decimal("5000")

    LIVE_BASE = "https://bitpay.ir/payment"
    TEST_BASE = "https://bitpay.ir/payment-test"

    # Documented request-time errors, keyed by the integer BitPay returns.
    REQUEST_ERRORS = {
        -1: "کلید API با درگاه ثبت‌شده سازگار نیست.",
        -2: "مبلغ نامعتبر است یا کمتر از ۵۰۰۰ ریال است.",
        -3: "آدرس بازگشت خالی است.",
        -4: "درگاهی با این اطلاعات وجود ندارد یا در انتظار تأیید است.",
        -5: "خطا در اتصال به درگاه. دوباره تلاش کنید.",
    }

    # And the verification-time ones.
    VERIFY_ERRORS = {
        -1: "کلید API با درگاه ثبت‌شده سازگار نیست.",
        -2: "شناسه تراکنش عددی نیست.",
        -3: "شناسه پرداخت عددی نیست.",
        -4: "چنین تراکنشی وجود ندارد یا موفق نبوده است.",
    }

    def __init__(self, api_key=None, sandbox=None):
        self.sandbox = settings.BITPAY_SANDBOX if sandbox is None else sandbox

        # The documented test key. Only ever used in sandbox mode, and only
        # when no key is configured — never as a production fallback.
        self.api_key = api_key or settings.BITPAY_API_KEY
        if not self.api_key and self.sandbox:
            self.api_key = "adxcv-zzadq-polkjsad-opp13opoz-1sdf455aadzmck1244567"
        if not self.api_key:
            raise GatewayError("BITPAY_API_KEY is not configured.")

    @property
    def base(self):
        return self.TEST_BASE if self.sandbox else self.LIVE_BASE

    def _fee_for(self, amount):
        """Estimate BitPay's commission on `amount`, in rial.

        BitPay's API never reports what it took, so the figure is derived from
        the percent and cap in settings, which mirror the merchant contract.
        It is an estimate for the invoice, not a statement from the gateway —
        reconcile against the BitPay panel before trusting it as accounting.
        """
        percent = Decimal(str(settings.BITPAY_FEE_PERCENT))
        cap = Decimal(str(settings.BITPAY_FEE_CAP))
        fee = min(Decimal(amount) * percent / Decimal("100"), cap)
        return fee.quantize(Decimal("1"), rounding=ROUND_HALF_UP)

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

        payload = {
            "api": self.api_key,
            "amount": int(amount),
            "redirect": callback_url,
        }
        if description:
            payload["description"] = description[:255]
        if email:
            payload["email"] = email
        if mobile and mobile.startswith("09") and len(mobile) == 11:
            # Shows the buyer's saved cards on the bank page.
            payload["mobileNum"] = mobile

        response = self._post("gateway-send", payload)
        body = (response.text or "").strip()

        # A bare integer is the answer: positive is the id_get, negative is an
        # error code. The endpoint is not JSON.
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

        response = self._post(
            "gateway-result-second",
            {
                "api": self.api_key,
                "id_get": authority,
                "trans_id": trans_id,
                "json": 1,
            },
        )

        try:
            body = response.json()
        except ValueError:
            return VerificationResult(
                success=False,
                message=f"پاسخ نامعتبر از بیت‌پی: {(response.text or '')[:120]}",
                raw={"text": (response.text or "")[:500]},
            )

        try:
            gateway_status = int(body.get("status"))
        except (TypeError, ValueError):
            return VerificationResult(
                success=False, message="وضعیت تراکنش از بیت‌پی خوانده نشد.", raw=body
            )

        if gateway_status not in (1, 11):
            return VerificationResult(
                success=False,
                message=self.VERIFY_ERRORS.get(
                    gateway_status, f"تأیید پرداخت ناموفق بود (کد {gateway_status})."
                ),
                raw=body,
            )

        # BitPay reports what it charged. If that is not what we asked for, the
        # callback has been tampered with or the wrong transaction was matched —
        # either way, do not settle the order.
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
                    success=False, message="مبلغ بازگشتی از بیت‌پی نامعتبر است.", raw=body
                )

        return VerificationResult(
            success=True,
            ref_id=trans_id,
            card_pan=str(body.get("cardNum") or ""),
            fee=self._fee_for(amount),
            already_verified=gateway_status == 11,
            message="پرداخت تأیید شد.",
            raw=body,
        )


_GATEWAYS = {
    "mock": MockGateway,
    "zarinpal": ZarinPalGateway,
    "bitpay": BitPayGateway,
}

# One shared mock instance, so its in-memory transactions survive between the
# request and verify calls of a single checkout.
_mock_singleton = MockGateway()


def get_gateway(name=None):
    name = name or settings.PAYMENT_GATEWAY
    if name == "mock":
        return _mock_singleton
    try:
        return _GATEWAYS[name]()
    except KeyError as exc:
        raise GatewayError(f"Unknown payment gateway: {name}") from exc


def available_gateways():
    """The gateways checkout may offer, in the order they should be listed.

    Three things have to agree before a gateway reaches a customer:

      1. It is named in PAYMENT_GATEWAYS — the environment decides which
         gateways this deployment knows about at all.
      2. Its driver can be constructed. A missing merchant id or API key skips
         it here rather than failing halfway through someone's payment.
      3. It is not switched off in the back office (GatewayToggle).

    The toggle is a separate step from the credentials on purpose: a shop may
    want to stop taking payments through a gateway for an afternoon without
    deleting the key it will need again tomorrow.
    """
    # Imported here rather than at module scope: this module is imported by
    # settings-adjacent code, and a model import at the top would run before
    # the app registry is ready.
    from .models import GatewayToggle

    try:
        disabled = GatewayToggle.disabled_names()
    except Exception:
        # An unmigrated database must not take checkout down with it; the
        # environment list alone is a safe fallback.
        disabled = set()

    offered = []
    for name in settings.PAYMENT_GATEWAYS:
        if name in disabled:
            continue
        try:
            gateway = get_gateway(name)
        except GatewayError:
            continue
        offered.append({"name": gateway.name, "label": gateway.label})
    return offered
