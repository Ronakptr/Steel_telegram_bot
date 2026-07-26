import os

# توکن ربات را از @BotFather بگیرید و اینجا قرار دهید
# بهتر است از متغیر محیطی استفاده کنید تا توکن در کد قرار نگیرد
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
if not BOT_TOKEN:
    raise RuntimeError("متغیر محیطی BOT_TOKEN تنظیم نشده است.")

# آیدی عددی تلگرام ادمین‌ها؛ در Render با ADMIN_IDS و جداشده با ویرگول تنظیم کنید.
_admin_ids_raw = os.environ.get("ADMIN_IDS", "")
try:
    ADMIN_IDS = [int(value.strip()) for value in _admin_ids_raw.split(",") if value.strip()]
except ValueError as exc:
    raise RuntimeError("متغیر ADMIN_IDS باید فقط شامل آیدی‌های عددی جداشده با ویرگول باشد.") from exc
if not ADMIN_IDS:
    raise RuntimeError("متغیر محیطی ADMIN_IDS تنظیم نشده است.")

DB_PATH = os.environ.get(
    "DB_PATH", os.path.join(os.path.dirname(__file__), "steel_bot.db")
)

# برای اجرا روی Render (یا هر سرویس webhook/serverless دیگه)
# اگه این متغیر تنظیم بشه، ربات به‌جای polling از webhook استفاده می‌کنه
# مقدارش باید آدرس عمومی سرویس شما باشه، مثلاً: https://my-steel-bot.onrender.com
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "")
PORT = int(os.environ.get("PORT", "10000"))

# مراحل مختلف وضعیت سفارش
ORDER_STATUSES = {
    "pending": "⏳ در انتظار بررسی",
    "confirmed": "✅ تایید شده",
    "preparing": "📦 در حال آماده‌سازی",
    "shipped": "🚚 ارسال شده",
    "delivered": "🏁 تحویل داده شده",
    "cancelled": "❌ لغو شده",
}

UNITS = ["کیلوگرم", "تن", "شاخه", "متر"]
# اطلاعات تماس که با دکمه "📞 اطلاعات تماس" به کاربر نشون داده می‌شه
CONTACT_INFO = (
    "📞 شماره تماس:09177151440\n"
    "📍 آدرس:بلوار امیرکبیر،جنب ترمینال مسافربری،خیابان توانیر،بلوار طلاییه قبل از شماره گذاری\n"
    "🌐 وبسایت: https://farsboresh.ir/\n\n"
    "💳 شماره کارت: 6037-xxxx-xxxx-xxxx\n"
    "🏦 شماره حساب: xxxxxxxxxx\n"
    "به نام:رضا پناهی دوست\n"
    "بانک: ..."
)


# تنظیمات OCR محلی فیش واریزی (بدون API خارجی)
RECEIPT_ACCOUNT_HOLDER = os.environ.get("RECEIPT_ACCOUNT_HOLDER", "رضا پناهی دوست")
RECEIPT_CARD_LAST4 = os.environ.get("RECEIPT_CARD_LAST4", "")
MAX_RECEIPT_SIZE_MB = int(os.environ.get("MAX_RECEIPT_SIZE_MB", "8"))
OCR_LANG = os.environ.get("OCR_LANG", "fas+eng")
OCR_TIMEOUT_SECONDS = int(os.environ.get("OCR_TIMEOUT_SECONDS", "25"))
TESSERACT_CMD = os.environ.get("TESSERACT_CMD", "")
