from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton

import database as db
from config import ORDER_STATUSES


def main_menu_keyboard():
    return ReplyKeyboardMarkup(
        [
          ["📋 سفارش‌های من", "📞 اطلاعات تماس"],
            ["➕ افزودن محصول", "✏️ تغییر قیمت"],
            ["📥 وارد کردن از اکسل", "📤 خروجی اکسل"],
            ["📦 سفارش‌های در انتظار", "📊 همه سفارش‌ها"],
        ],
        resize_keyboard=True,
    )


def admin_menu_keyboard():
    return ReplyKeyboardMarkup(
        [
            ["➕ افزودن محصول", "✏️ تغییر قیمت"],
            ["📦 سفارش‌های در انتظار", "📊 همه سفارش‌ها"],
            ["🔙 بازگشت به منوی کاربر"],
        ],
        resize_keyboard=True,
    )


def categories_keyboard(prefix="cat"):
    cats = db.list_categories()
    buttons = [
        [InlineKeyboardButton(c["name"], callback_data=f"{prefix}:{c['id']}")]
        for c in cats
    ]
    return InlineKeyboardMarkup(buttons)


def products_keyboard(category_id, prefix="prod"):
    products = db.list_products(category_id=category_id)
    buttons = []
    for p in products:
        label = f"{p['name']} — {p['price']:,} تومان / {p['unit']}"
        buttons.append([InlineKeyboardButton(label, callback_data=f"{prefix}:{p['id']}")])
    buttons.append([InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_categories")])
    return InlineKeyboardMarkup(buttons)


def quantity_keyboard(product_id):
    row1 = [InlineKeyboardButton(str(q), callback_data=f"qty:{product_id}:{q}") for q in [1, 5, 10]]
    row2 = [InlineKeyboardButton(str(q), callback_data=f"qty:{product_id}:{q}") for q in [50, 100, 500]]
    custom = [InlineKeyboardButton("✏️ مقدار دلخواه", callback_data=f"qtycustom:{product_id}")]
    return InlineKeyboardMarkup([row1, row2, custom])


def cart_keyboard():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("➕ افزودن محصول دیگر", callback_data="add_more")],
            [InlineKeyboardButton("✅ نهایی کردن سفارش", callback_data="checkout")],
            [InlineKeyboardButton("🗑️ خالی کردن سبد", callback_data="clear_cart")],
        ]
    )


def phone_request_keyboard():
    return ReplyKeyboardMarkup(
        [[KeyboardButton("📱 ارسال شماره تماس", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def order_status_keyboard(order_id):
    buttons = []
    row = []
    for key, label in ORDER_STATUSES.items():
        row.append(InlineKeyboardButton(label, callback_data=f"setstatus:{order_id}:{key}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    return InlineKeyboardMarkup(buttons)
