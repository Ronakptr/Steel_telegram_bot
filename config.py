import os

# توکن ربات را از @BotFather بگیرید و اینجا قرار دهید
# بهتر است از متغیر محیطی استفاده کنید تا توکن در کد قرار نگیرد
BOT_TOKEN = os.environ.get("BOT_TOKEN", "REPLACE_WITH_YOUR_BOT_TOKEN")

# آیدی عددی تلگرام ادمین‌ها (می‌توانید با ربات @userinfobot آیدی خودتان را بگیرید)
ADMIN_IDS = [
    178064560,  # <-- این را با آیدی تلگرام خودتان جایگزین کنید
]

DB_PATH = os.path.join(os.path.dirname(__file__), "steel_bot.db")

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
