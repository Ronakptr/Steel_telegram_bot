import logging

from telegram.ext import ApplicationBuilder

from config import BOT_TOKEN, WEBHOOK_URL, PORT
from database import init_db
from handlers.user import register_user_handlers
from handlers.admin import register_admin_handlers

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)


def main():
    init_db()

    app = ApplicationBuilder().token(BOT_TOKEN).job_queue(None).build()


    register_user_handlers(app)
    register_admin_handlers(app)

    if WEBHOOK_URL:
        # حالت webhook - برای هاست‌های serverless/رایگان مثل Render
        print(f"ربات با webhook روی پورت {PORT} اجرا می‌شه...")
        app.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=BOT_TOKEN,
            webhook_url=f"{WEBHOOK_URL.rstrip('/')}/{BOT_TOKEN}",
        )
    else:
        # حالت polling - برای اجرا روی سیستم شخصی یا VPS
        print("ربات در حال اجراست (polling)... برای توقف Ctrl+C بزنید.")
        app.run_polling()


if __name__ == "__main__":
    main()
