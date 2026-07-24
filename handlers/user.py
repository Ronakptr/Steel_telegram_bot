from telegram import Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
    MessageHandler,
    CommandHandler,
    filters,
)

import database as db
import keyboards as kb
from config import ORDER_STATUSES, ADMIN_IDS

# مراحل مکالمه
ASK_QTY_CUSTOM, ASK_ADDRESS, ASK_PHONE, CONFIRM = range(4)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.upsert_user(user.id, user.full_name, user.username)
    text = (
        f"سلام {user.first_name} 👋\n\n"
        "به ربات فروش آهن‌آلات خوش اومدید.\n"
        "از منوی زیر می‌تونید سفارش ثبت کنید، قیمت‌ها رو ببینید یا وضعیت سفارش‌های قبلیتون رو چک کنید."
    )
    await update.message.reply_text(text, reply_markup=kb.main_menu_keyboard())
    return ConversationHandler.END


async def show_prices(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cats = db.list_categories()
    if not cats:
        await update.message.reply_text("در حال حاضر محصولی ثبت نشده. بعداً دوباره سر بزنید.")
        return
    await update.message.reply_text(
        "یک دسته‌بندی رو انتخاب کنید تا قیمت‌های به‌روز رو ببینید:",
        reply_markup=kb.categories_keyboard(prefix="pricecat"),
    )


async def show_prices_for_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cat_id = int(query.data.split(":")[1])
    products = db.list_products(category_id=cat_id)
    if not products:
        await query.edit_message_text("محصولی در این دسته موجود نیست.")
        return
    lines = ["💰 قیمت‌های به‌روز:\n"]
    for p in products:
        lines.append(f"• {p['name']}: {p['price']:,} تومان / {p['unit']}")
    await query.edit_message_text("\n".join(lines))


async def new_order_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["cart"] = context.user_data.get("cart", [])
    cats = db.list_categories()
    if not cats:
        await update.message.reply_text("در حال حاضر محصولی برای سفارش ثبت نشده.")
        return ConversationHandler.END
    await update.message.reply_text(
        "یک دسته‌بندی انتخاب کنید:", reply_markup=kb.categories_keyboard(prefix="cat")
    )
    return ConversationHandler.END


async def pick_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cat_id = int(query.data.split(":")[1])
    context.user_data["current_category"] = cat_id
    products = db.list_products(category_id=cat_id)
    if not products:
        await query.edit_message_text("محصولی در این دسته موجود نیست.")
        return
    await query.edit_message_text(
        "یک محصول رو انتخاب کنید:", reply_markup=kb.products_keyboard(cat_id)
    )


async def back_to_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "یک دسته‌بندی انتخاب کنید:", reply_markup=kb.categories_keyboard(prefix="cat")
    )


async def pick_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    product_id = int(query.data.split(":")[1])
    product = db.get_product(product_id)
    if not product:
        await query.edit_message_text("این محصول دیگر موجود نیست.")
        return
    context.user_data["current_product"] = product_id
    await query.edit_message_text(
        f"{product['name']}\nقیمت: {product['price']:,} تومان / {product['unit']}\n\n"
        "چه مقداری نیاز دارید؟",
        reply_markup=kb.quantity_keyboard(product_id),
    )


async def pick_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, product_id, qty = query.data.split(":")
    await add_to_cart(update, context, int(product_id), int(qty))


async def ask_custom_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    product_id = int(query.data.split(":")[1])
    context.user_data["awaiting_qty_for"] = product_id
    await query.edit_message_text("مقدار مورد نظرتون رو به عدد بفرستید:")
    return ASK_QTY_CUSTOM


async def receive_custom_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text.replace(".", "", 1).isdigit():
        await update.message.reply_text("لطفاً فقط عدد ارسال کنید. مثال: 25")
        return ASK_QTY_CUSTOM
    qty = float(text)
    product_id = context.user_data.get("awaiting_qty_for")
    await add_to_cart(update, context, product_id, qty, is_message=True)
    return ConversationHandler.END


async def add_to_cart(update, context, product_id, qty, is_message=False):
    product = db.get_product(product_id)
    if not product:
        msg = "این محصول دیگر موجود نیست."
        if is_message:
            await update.message.reply_text(msg)
        else:
            await update.callback_query.edit_message_text(msg)
        return

    line_total = product["price"] * qty
    cart = context.user_data.get("cart", [])
    cart.append(
        {
            "product_id": product_id,
            "name": product["name"],
            "unit": product["unit"],
            "price": product["price"],
            "qty": qty,
            "line_total": line_total,
        }
    )
    context.user_data["cart"] = cart

    text = build_cart_text(cart)
    if is_message:
        await update.message.reply_text(text, reply_markup=kb.cart_keyboard())
    else:
        await update.callback_query.edit_message_text(text, reply_markup=kb.cart_keyboard())


def build_cart_text(cart):
    lines = ["🛒 سبد سفارش شما:\n"]
    total = 0
    for item in cart:
        lines.append(
            f"• {item['name']}: {item['qty']} {item['unit']} × {item['price']:,} = {item['line_total']:,} تومان"
        )
        total += item["line_total"]
    lines.append(f"\n💵 جمع کل: {total:,} تومان")
    return "\n".join(lines)


async def add_more(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "یک دسته‌بندی انتخاب کنید:", reply_markup=kb.categories_keyboard(prefix="cat")
    )


async def clear_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["cart"] = []
    await query.edit_message_text("سبد سفارش خالی شد. برای شروع دوباره /neworder رو بزنید.")


async def checkout_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cart = context.user_data.get("cart", [])
    if not cart:
        await query.edit_message_text("سبد سفارش شما خالیه.")
        return ConversationHandler.END
    await query.edit_message_text("لطفاً آدرس تحویل بار رو بنویسید:")
    return ASK_ADDRESS


async def receive_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["address"] = update.message.text
    await update.message.reply_text(
        "شماره تماس‌تون رو بفرستید (می‌تونید از دکمه زیر استفاده کنید):",
        reply_markup=kb.phone_request_keyboard(),
    )
    return ASK_PHONE


async def receive_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.contact:
        phone = update.message.contact.phone_number
    else:
        phone = update.message.text
    context.user_data["phone"] = phone

    cart = context.user_data.get("cart", [])
    total = sum(item["line_total"] for item in cart)
    address = context.user_data.get("address", "")

    user = update.effective_user
    db.upsert_user(user.id, user.full_name, user.username, phone=phone)
    order_id = db.create_order(user.id, cart, total, address, phone)

    from telegram import ReplyKeyboardRemove

    text = (
        f"✅ سفارش شما با شماره #{order_id} ثبت شد!\n\n"
        f"{build_cart_text(cart)}\n\n"
        f"📍 آدرس: {address}\n"
        f"📱 تلفن: {phone}\n\n"
        f"وضعیت فعلی: {ORDER_STATUSES['pending']}\n"
        "به محض بررسی توسط کارشناسان، بهتون اطلاع می‌دیم."
    )
    await update.message.reply_text(text, reply_markup=kb.main_menu_keyboard())

    context.user_data["cart"] = []

    # اطلاع به ادمین‌ها
    admin_text = (
        f"🆕 سفارش جدید #{order_id}\n"
        f"از: {user.full_name} (@{user.username or '---'})\n\n"
        f"{build_cart_text(cart)}\n\n"
        f"📍 آدرس: {address}\n📱 تلفن: {phone}"
    )
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                admin_id, admin_text, reply_markup=kb.order_status_keyboard(order_id)
            )
        except Exception:
            pass

    return ConversationHandler.END


async def my_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    orders = db.list_user_orders(user.id)
    if not orders:
        await update.message.reply_text("شما هنوز سفارشی ثبت نکردید.")
        return
    lines = ["📋 سفارش‌های شما:\n"]
    for o in orders:
        status_label = ORDER_STATUSES.get(o["status"], o["status"])
        lines.append(
            f"#{o['id']} | {o['total_price']:,} تومان | {status_label} | {o['created_at'][:10]}"
        )
    await update.message.reply_text("\n".join(lines))


async def support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "برای پشتیبانی می‌تونید با شماره زیر تماس بگیرید:\n📞 021-XXXXXXX"
    )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["cart"] = []
    await update.message.reply_text("عملیات لغو شد.", reply_markup=kb.main_menu_keyboard())
    return ConversationHandler.END


def register_user_handlers(app):
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Regex("^💰 مشاهده قیمت‌ها$"), show_prices))
    app.add_handler(MessageHandler(filters.Regex("^📋 سفارش‌های من$"), my_orders))
    app.add_handler(MessageHandler(filters.Regex("^📞 تماس با پشتیبانی$"), support))
    app.add_handler(MessageHandler(filters.Regex("^🛒 ثبت سفارش جدید$"), new_order_start))
    app.add_handler(CommandHandler("neworder", new_order_start))

    app.add_handler(CallbackQueryHandler(pick_category, pattern=r"^cat:\d+$"))
    app.add_handler(CallbackQueryHandler(back_to_categories, pattern=r"^back_to_categories$"))
    app.add_handler(CallbackQueryHandler(pick_product, pattern=r"^prod:\d+$"))
    app.add_handler(CallbackQueryHandler(pick_quantity, pattern=r"^qty:\d+:\d+(\.\d+)?$"))
    app.add_handler(CallbackQueryHandler(add_more, pattern=r"^add_more$"))
    app.add_handler(CallbackQueryHandler(clear_cart, pattern=r"^clear_cart$"))
    app.add_handler(CallbackQueryHandler(show_prices_for_category, pattern=r"^pricecat:\d+$"))

    custom_qty_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(ask_custom_quantity, pattern=r"^qtycustom:\d+$")],
        states={
            ASK_QTY_CUSTOM: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_custom_quantity)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    app.add_handler(custom_qty_conv)

    checkout_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(checkout_start, pattern=r"^checkout$")],
        states={
            ASK_ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_address)],
            ASK_PHONE: [MessageHandler((filters.TEXT | filters.CONTACT) & ~filters.COMMAND, receive_phone)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    app.add_handler(checkout_conv)
