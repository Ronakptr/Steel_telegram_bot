import io

from telegram import Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
    MessageHandler,
    CommandHandler,
    filters,
)
from openpyxl import Workbook, load_workbook

import database as db
import keyboards as kb
from config import ADMIN_IDS, ORDER_STATUSES

# مراحل مکالمه افزودن محصول
ADD_CAT_NAME, ADD_PROD_CAT, ADD_PROD_NAME, ADD_PROD_UNIT, ADD_PROD_PRICE = range(5)
# مراحل تغییر قیمت
EDIT_PRICE_PICK, EDIT_PRICE_VALUE = range(5, 7)
# مرحله ایمپورت اکسل
AWAIT_EXCEL_FILE = 7


def is_admin(user_id):
    return user_id in ADMIN_IDS


async def admin_only_guard(update: Update):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ این بخش فقط برای ادمین‌هاست.")
        return False
    return True


async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only_guard(update):
        return
    await update.message.reply_text("پنل مدیریت:", reply_markup=kb.admin_menu_keyboard())


async def back_to_user_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("بازگشت به منوی اصلی.", reply_markup=kb.main_menu_keyboard())


# ---------- افزودن محصول ----------

async def add_product_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only_guard(update):
        return ConversationHandler.END
    cats = db.list_categories()
    if cats:
        lines = "\n".join(f"- {c['name']}" for c in cats)
        await update.message.reply_text(
            f"دسته‌بندی‌های موجود:\n{lines}\n\n"
            "نام دسته‌بندی محصول جدید رو بفرستید (اگه جدیده، خودکار ساخته می‌شه):"
        )
    else:
        await update.message.reply_text("نام دسته‌بندی محصول رو بفرستید (مثلاً: میلگرد):")
    return ADD_CAT_NAME


async def add_product_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cat_name = update.message.text.strip()
    cat_id = db.add_category(cat_name)
    if cat_id is None:
        cats = {c["name"]: c["id"] for c in db.list_categories()}
        cat_id = cats.get(cat_name)
    context.user_data["new_prod_cat_id"] = cat_id
    await update.message.reply_text("نام محصول رو بفرستید (مثلاً: میلگرد ۱۴ آجدار):")
    return ADD_PROD_NAME


async def add_product_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_prod_name"] = update.message.text.strip()
    await update.message.reply_text("واحد اندازه‌گیری چیه؟ (مثلاً: کیلوگرم، تن، شاخه)")
    return ADD_PROD_UNIT


async def add_product_unit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_prod_unit"] = update.message.text.strip()
    await update.message.reply_text("قیمت به تومان رو به عدد بفرستید (مثلاً: 285000):")
    return ADD_PROD_PRICE


async def add_product_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().replace(",", "")
    if not text.isdigit():
        await update.message.reply_text("لطفاً فقط عدد بفرستید.")
        return ADD_PROD_PRICE
    price = int(text)
    cat_id = context.user_data["new_prod_cat_id"]
    name = context.user_data["new_prod_name"]
    unit = context.user_data["new_prod_unit"]
    product_id = db.add_product(cat_id, name, unit, price)
    await update.message.reply_text(
        f"✅ محصول «{name}» با قیمت {price:,} تومان / {unit} اضافه شد. (کد: {product_id})",
        reply_markup=kb.admin_menu_keyboard(),
    )
    return ConversationHandler.END


# ---------- تغییر قیمت ----------

async def edit_price_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only_guard(update):
        return ConversationHandler.END
    cats = db.list_categories()
    if not cats:
        await update.message.reply_text("هنوز محصولی ثبت نشده.")
        return ConversationHandler.END
    await update.message.reply_text(
        "یک دسته‌بندی انتخاب کنید:", reply_markup=kb.categories_keyboard(prefix="editcat")
    )
    return ConversationHandler.END


async def edit_price_pick_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        await query.edit_message_text("⛔ فقط برای ادمین.")
        return
    cat_id = int(query.data.split(":")[1])
    products = db.list_products(category_id=cat_id, active_only=False)
    if not products:
        await query.edit_message_text("محصولی در این دسته نیست.")
        return
    await query.edit_message_text(
        "محصول مورد نظر برای تغییر قیمت رو انتخاب کنید:",
        reply_markup=kb.products_keyboard(cat_id, prefix="editprod"),
    )


async def edit_price_pick_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        await query.edit_message_text("⛔ فقط برای ادمین.")
        return ConversationHandler.END
    product_id = int(query.data.split(":")[1])
    context.user_data["editing_product_id"] = product_id
    product = db.get_product(product_id)
    await query.edit_message_text(
        f"قیمت فعلی «{product['name']}»: {product['price']:,} تومان / {product['unit']}\n\n"
        "قیمت جدید رو به عدد بفرستید:"
    )
    return EDIT_PRICE_VALUE


async def edit_price_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().replace(",", "")
    if not text.isdigit():
        await update.message.reply_text("لطفاً فقط عدد بفرستید.")
        return EDIT_PRICE_VALUE
    new_price = int(text)
    product_id = context.user_data["editing_product_id"]
    db.update_price(product_id, new_price)
    product = db.get_product(product_id)
    await update.message.reply_text(
        f"✅ قیمت «{product['name']}» به {new_price:,} تومان به‌روز شد.",
        reply_markup=kb.admin_menu_keyboard(),
    )
    return ConversationHandler.END


# ---------- ورود/خروج اکسل ----------

async def import_excel_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only_guard(update):
        return ConversationHandler.END
    await update.message.reply_text(
        "یه فایل اکسل (.xlsx) بفرستید با این ستون‌ها در سطر اول:\n\n"
        "دسته‌بندی | نام محصول | واحد | قیمت\n\n"
        "مثال:\n"
        "میلگرد | میلگرد ۱۴ آجدار | کیلوگرم | 285000\n\n"
        "اگه محصولی از قبل با همین نام و دسته وجود داشته باشه، فقط قیمتش آپدیت می‌شه. "
        "برای لغو /cancel رو بزنید."
    )
    return AWAIT_EXCEL_FILE


async def import_excel_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.message.document
    if not document or not document.file_name.lower().endswith((".xlsx", ".xlsm")):
        await update.message.reply_text("لطفاً یه فایل اکسل معتبر (.xlsx) بفرستید.")
        return AWAIT_EXCEL_FILE

    file = await context.bot.get_file(document.file_id)
    file_bytes = await file.download_as_bytearray()

    try:
        wb = load_workbook(io.BytesIO(bytes(file_bytes)))
        sheet = wb.active
    except Exception:
        await update.message.reply_text("نتونستم فایل رو باز کنم. مطمئن شید فرمتش .xlsx باشه.")
        return AWAIT_EXCEL_FILE

    added, updated, skipped = 0, 0, 0
    rows = list(sheet.iter_rows(min_row=2, values_only=True))
    for row in rows:
        if not row or len(row) < 4:
            skipped += 1
            continue
        cat_name, prod_name, unit, price = row[0], row[1], row[2], row[3]
        if not cat_name or not prod_name or not unit or price is None:
            skipped += 1
            continue
        try:
            price_int = int(float(str(price).replace(",", "")))
        except (ValueError, TypeError):
            skipped += 1
            continue

        cat_name = str(cat_name).strip()
        prod_name = str(prod_name).strip()
        unit = str(unit).strip()

        cat_id = db.add_category(cat_name)
        if cat_id is None:
            cats = {c["name"]: c["id"] for c in db.list_categories()}
            cat_id = cats.get(cat_name)

        existing = db.get_product_by_name(cat_id, prod_name)
        if existing:
            db.update_price(existing["id"], price_int)
            updated += 1
        else:
            db.add_product(cat_id, prod_name, unit, price_int)
            added += 1

    await update.message.reply_text(
        f"✅ ایمپورت تموم شد:\n"
        f"➕ {added} محصول جدید اضافه شد\n"
        f"✏️ {updated} محصول به‌روزرسانی شد\n"
        f"⏭️ {skipped} سطر نامعتبر رد شد",
        reply_markup=kb.admin_menu_keyboard(),
    )
    return ConversationHandler.END


async def export_excel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only_guard(update):
        return
    cats = {c["id"]: c["name"] for c in db.list_categories()}
    products = db.list_products(active_only=False)
    if not products:
        await update.message.reply_text("هنوز محصولی ثبت نشده.")
        return

    wb = Workbook()
    sheet = wb.active
    sheet.append(["دسته‌بندی", "نام محصول", "واحد", "قیمت"])
    for p in products:
        sheet.append([cats.get(p["category_id"], ""), p["name"], p["unit"], p["price"]])

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    await update.message.reply_document(
        document=buffer, filename="محصولات.xlsx", caption="لیست فعلی محصولات"
    )


# ---------- مدیریت سفارش‌ها ----------

async def pending_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only_guard(update):
        return
    orders = db.list_all_orders(status="pending")
    if not orders:
        await update.message.reply_text("سفارش در انتظاری وجود نداره. 🎉")
        return
    for o in orders:
        await send_order_summary(update, context, o)


async def all_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only_guard(update):
        return
    orders = db.list_all_orders(limit=20)
    if not orders:
        await update.message.reply_text("هنوز سفارشی ثبت نشده.")
        return
    for o in orders:
        await send_order_summary(update, context, o)


async def send_order_summary(update, context, order):
    user = db.get_user(order["user_id"])
    status_label = ORDER_STATUSES.get(order["status"], order["status"])
    text = (
        f"سفارش #{order['id']}\n"
        f"مشتری: {user['full_name'] if user else order['user_id']}\n"
        f"مبلغ: {order['total_price']:,} تومان\n"
        f"وضعیت: {status_label}\n"
        f"تاریخ: {order['created_at'][:16]}"
    )
    await update.message.reply_text(text, reply_markup=kb.order_status_keyboard(order["id"]))


async def set_order_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        await query.edit_message_text("⛔ فقط برای ادمین.")
        return
    _, order_id, status_key = query.data.split(":")
    order_id = int(order_id)
    db.update_order_status(order_id, status_key)
    order = db.get_order(order_id)
    status_label = ORDER_STATUSES.get(status_key, status_key)
    await query.edit_message_text(f"وضعیت سفارش #{order_id} به «{status_label}» تغییر کرد.")

    # اطلاع به مشتری
    try:
        await context.bot.send_message(
            order["user_id"],
            f"📦 وضعیت سفارش #{order_id} شما به‌روز شد:\n{status_label}",
        )
    except Exception:
        pass


def register_admin_handlers(app):
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(MessageHandler(filters.Regex("^🔙 بازگشت به منوی کاربر$"), back_to_user_menu))
    app.add_handler(MessageHandler(filters.Regex("^📦 سفارش‌های در انتظار$"), pending_orders))
    app.add_handler(MessageHandler(filters.Regex("^📊 همه سفارش‌ها$"), all_orders))

    app.add_handler(CallbackQueryHandler(edit_price_pick_category, pattern=r"^editcat:\d+$"))
    app.add_handler(CallbackQueryHandler(set_order_status, pattern=r"^setstatus:\d+:\w+$"))

    app.add_handler(MessageHandler(filters.Regex("^📤 خروجی اکسل$"), export_excel))

    import_excel_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^📥 وارد کردن از اکسل$"), import_excel_start)],
        states={
            AWAIT_EXCEL_FILE: [MessageHandler(filters.Document.ALL, import_excel_receive)],
        },
        fallbacks=[CommandHandler("cancel", back_to_user_menu)],
    )
    app.add_handler(import_excel_conv)

    add_product_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^➕ افزودن محصول$"), add_product_start)],
        states={
            ADD_CAT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_product_category)],
            ADD_PROD_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_product_name)],
            ADD_PROD_UNIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_product_unit)],
            ADD_PROD_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_product_price)],
        },
        fallbacks=[CommandHandler("cancel", back_to_user_menu)],
    )
    app.add_handler(add_product_conv)

    edit_price_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^✏️ تغییر قیمت$"), edit_price_start),
            CallbackQueryHandler(edit_price_pick_product, pattern=r"^editprod:\d+$"),
        ],
        states={
            EDIT_PRICE_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_price_value)],
        },
        fallbacks=[CommandHandler("cancel", back_to_user_menu)],
    )
    app.add_handler(edit_price_conv)
