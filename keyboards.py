import math

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton

import database as db
from config import ORDER_STATUSES


def main_menu_keyboard():
    return ReplyKeyboardMarkup(
        [
            ["🛒 ثبت سفارش جدید", "💰 مشاهده قیمت‌ها"],
            ["📋 سفارش‌های من", "🧾 ارسال فیش واریزی"],
            ["📞 اطلاعات تماس"],
        ],
        resize_keyboard=True,
    )


def admin_menu_keyboard():
    return ReplyKeyboardMarkup(
        [
            ["➕ افزودن محصول", "🧰 مدیریت محصولات"],
            ["📥 وارد کردن از اکسل", "📤 خروجی اکسل"],
            ["📦 سفارش‌های در انتظار", "📊 همه سفارش‌ها"],
            ["🔙 بازگشت به منوی کاربر"],
        ],
        resize_keyboard=True,
    )


def categories_keyboard(prefix="cat"):
    # کاربران فقط دسته‌هایی را می‌بینند که حداقل یک محصول فعال دارند.
    active_only = prefix in {"cat", "pricecat"}
    cats = db.list_categories(active_products_only=active_only)
    buttons = [
        [InlineKeyboardButton(c["name"], callback_data=f"{prefix}:{c['id']}")]
        for c in cats
    ]
    return InlineKeyboardMarkup(buttons)


def products_keyboard(category_id, prefix="prod", active_only=True):
    products = db.list_products(category_id=category_id, active_only=active_only)
    buttons = []
    for p in products:
        label = f"{p['name']} — {p['price']:,} تومان / {p['unit']}"
        buttons.append([InlineKeyboardButton(label, callback_data=f"{prefix}:{p['id']}")])
    buttons.append([InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_categories")])
    return InlineKeyboardMarkup(buttons)


def product_management_keyboard(products, page=0, per_page=8):
    total = len(products)
    total_pages = max(1, math.ceil(total / per_page))
    page = max(0, min(page, total_pages - 1))
    start = page * per_page
    current = products[start:start + per_page]

    buttons = []
    for p in current:
        status = "🟢" if p["is_active"] else "⚪"
        label = f"{status} {p['name']} — {p['price']:,} تومان / {p['unit']}"
        buttons.append([
            InlineKeyboardButton(label, callback_data=f"manageprod:{p['id']}:{page}")
        ])

    navigation = []
    if page > 0:
        navigation.append(InlineKeyboardButton("⬅️ قبلی", callback_data=f"managepage:{page - 1}"))
    navigation.append(InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="managenoop"))
    if page < total_pages - 1:
        navigation.append(InlineKeyboardButton("بعدی ➡️", callback_data=f"managepage:{page + 1}"))
    buttons.append(navigation)
    buttons.append([InlineKeyboardButton("✖️ بستن", callback_data="manageclose")])
    return InlineKeyboardMarkup(buttons)


def product_actions_keyboard(product_id, is_active, page=0):
    toggle_text = "⏸ غیرفعال کردن" if is_active else "▶️ فعال کردن"
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("✏️ ویرایش کامل", callback_data=f"prodedit:{product_id}:{page}")],
            [InlineKeyboardButton(toggle_text, callback_data=f"prodtoggle:{product_id}:{page}")],
            [InlineKeyboardButton("🗑 حذف محصول", callback_data=f"proddeleteask:{product_id}:{page}")],
            [InlineKeyboardButton("🔙 بازگشت به فهرست", callback_data=f"managepage:{page}")],
        ]
    )


def product_delete_confirm_keyboard(product_id, page=0):
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ بله، حذف شود", callback_data=f"proddelete:{product_id}:{page}"),
                InlineKeyboardButton("❌ خیر", callback_data=f"manageprod:{product_id}:{page}"),
            ]
        ]
    )


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


def receipt_order_keyboard(orders):
    buttons = [
        [InlineKeyboardButton(
            f"سفارش #{o['id']} — {o['total_price']:,} تومان",
            callback_data=f"receiptorder:{o['id']}"
        )]
        for o in orders
    ]
    return InlineKeyboardMarkup(buttons)


def receipt_review_keyboard(receipt_id):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ تأیید پرداخت", callback_data=f"receiptapprove:{receipt_id}"),
            InlineKeyboardButton("❌ رد فیش", callback_data=f"receiptreject:{receipt_id}"),
        ]
    ])
