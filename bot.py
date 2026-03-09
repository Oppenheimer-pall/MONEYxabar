#!/usr/bin/env python3
"""
💳 CARD PAYMENT BOT - Telegram
Professional karta boshqaruv va to'lov tizimi
"""

import logging
import sqlite3
import re
from datetime import datetime
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)
from config import BOT_TOKEN, ADMIN_IDS
from database import Database
from card_utils import format_card_number, mask_card, validate_card, get_card_type

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Conversation states
(
    ENTER_CARD_NUMBER, ENTER_CARD_EXPIRY, ENTER_CARD_NAME,
    ENTER_AMOUNT, ENTER_RECEIVER, CONFIRM_PAYMENT,
    ENTER_TOPUP_AMOUNT
) = range(7)

db = Database()


# ══════════════════════════════════════════
#  YORDAMCHI FUNKSIYALAR
# ══════════════════════════════════════════

def get_main_keyboard():
    keyboard = [
        [KeyboardButton("💳 Kartalarim"), KeyboardButton("➕ Karta qo'shish")],
        [KeyboardButton("💸 Pul o'tkazish"), KeyboardButton("📊 Hisobot")],
        [KeyboardButton("📋 Tarix"), KeyboardButton("⚙️ Sozlamalar")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def card_message_block(card: dict, show_balance=True) -> str:
    """Chiroyli karta bloki"""
    card_type = get_card_type(card['card_number'])
    masked = mask_card(card['card_number'])
    expiry = card['expiry']
    name = card['card_name'].upper()
    balance = card['balance']

    type_emoji = {
        "Visa": "💳", "Mastercard": "💳",
        "Humo": "🟠", "Uzcard": "🔵", "Unknown": "💳"
    }.get(card_type, "💳")

    block = f"""
╔══════════════════════════╗
║  {type_emoji}  {card_type:<22} ║
║                          ║
║  {masked}  ║
║                          ║
║  {name:<26} ║
║  Amal qilish: {expiry}          ║"""

    if show_balance:
        block += f"""
║                          ║
║  💰 Balans: {balance:>10,.0f} so'm ║"""

    block += """
╚══════════════════════════╝"""
    return block


def payment_receipt(tx: dict) -> str:
    """To'lov cheki"""
    status_emoji = "✅" if tx['status'] == 'success' else "❌"
    arrow = "⬆️ Yuborildi" if tx['type'] == 'debit' else "⬇️ Olindi"

    return f"""
━━━━━━━━━━━━━━━━━━━━━━━━━
{status_emoji} TO'LOV CHEKI
━━━━━━━━━━━━━━━━━━━━━━━━━
📌 Tranzaksiya ID: #{tx['id']}
📅 Sana: {tx['created_at']}
━━━━━━━━━━━━━━━━━━━━━━━━━
{arrow}
💳 Karta: {mask_card(tx['card_number'])}
👤 Qabul qiluvchi: {tx.get('receiver', 'N/A')}
━━━━━━━━━━━━━━━━━━━━━━━━━
💵 Summa: {tx['amount']:,.0f} so'm
💸 Komissiya: {tx.get('fee', 0):,.0f} so'm
💰 Jami: {tx['amount'] + tx.get('fee', 0):,.0f} so'm
━━━━━━━━━━━━━━━━━━━━━━━━━
📝 Holat: {tx['status'].upper()}
━━━━━━━━━━━━━━━━━━━━━━━━━"""


# ══════════════════════════════════════════
#  START VA ASOSIY KOMANDALAR
# ══════════════════════════════════════════

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.get_or_create_user(user.id, user.full_name, user.username)

    welcome = f"""
🏦 *CARD BOT*'ga xush kelibsiz!

Salom, *{user.first_name}*! 👋

Bu bot orqali siz:
💳 Kartalaringizni boshqarishingiz
💸 Pul o'tkazishingiz  
📊 Balansni tekshirishingiz
📋 Tranzaksiya tarixini ko'rishingiz mumkin

Boshlash uchun quyidagi tugmalardan foydalaning 👇
"""
    await update.message.reply_text(
        welcome,
        parse_mode='Markdown',
        reply_markup=get_main_keyboard()
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
📚 *YORDAM*

*Asosiy komandalar:*
/start - Botni ishga tushirish
/cards - Kartalarim
/addcard - Karta qo'shish
/balance - Balansni ko'rish
/transfer - Pul o'tkazish
/history - Tarix
/help - Yordam

*Qo'llab-quvvatlash:* @support
"""
    await update.message.reply_text(help_text, parse_mode='Markdown')


# ══════════════════════════════════════════
#  KARTALAR
# ══════════════════════════════════════════

async def show_cards(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    cards = db.get_user_cards(user_id)

    if not cards:
        keyboard = [[InlineKeyboardButton("➕ Karta qo'shish", callback_data="add_card")]]
        await update.message.reply_text(
            "💳 Sizda hali karta yo'q.\n\nQuyidagi tugma orqali karta qo'shing:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    msg = "💳 *SIZNING KARTALARINGIZ*\n"
    for i, card in enumerate(cards, 1):
        msg += f"\n*Karta {i}:*"
        msg += f"```{card_message_block(card)}```"

        keyboard = [
            [
                InlineKeyboardButton("💸 O'tkazma", callback_data=f"transfer_{card['id']}"),
                InlineKeyboardButton("📊 Balans", callback_data=f"balance_{card['id']}"),
            ],
            [
                InlineKeyboardButton("⬆️ To'ldirish", callback_data=f"topup_{card['id']}"),
                InlineKeyboardButton("🗑 O'chirish", callback_data=f"delete_card_{card['id']}"),
            ]
        ]
        await update.message.reply_text(
            msg,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        msg = ""


async def add_card_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()
        send = update.callback_query.message.reply_text
    else:
        send = update.message.reply_text

    await send(
        "💳 *KARTA QO'SHISH*\n\n"
        "Karta raqamini kiriting:\n"
        "_(16 ta raqam, masalan: 8600 1234 5678 9012)_",
        parse_mode='Markdown'
    )
    return ENTER_CARD_NUMBER


async def enter_card_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw = re.sub(r'\D', '', update.message.text)

    if not validate_card(raw):
        await update.message.reply_text(
            "❌ Noto'g'ri karta raqami!\n\n"
            "16 ta raqam kiriting:\n"
            "_8600 1234 5678 9012_",
            parse_mode='Markdown'
        )
        return ENTER_CARD_NUMBER

    context.user_data['new_card_number'] = raw
    card_type = get_card_type(raw)
    formatted = format_card_number(raw)

    await update.message.reply_text(
        f"✅ Karta aniqlandi: *{card_type}*\n"
        f"💳 `{formatted}`\n\n"
        f"Amal qilish muddatini kiriting:\n_(MM/YY, masalan: 12/26)_",
        parse_mode='Markdown'
    )
    return ENTER_CARD_EXPIRY


async def enter_card_expiry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    expiry = update.message.text.strip()

    if not re.match(r'^(0[1-9]|1[0-2])\/([0-9]{2})$', expiry):
        await update.message.reply_text(
            "❌ Noto'g'ri format!\n\nMM/YY formatida kiriting:\n_12/26_",
            parse_mode='Markdown'
        )
        return ENTER_CARD_EXPIRY

    # Check expiry
    month, year = expiry.split('/')
    exp_year = 2000 + int(year)
    exp_month = int(month)
    now = datetime.now()

    if exp_year < now.year or (exp_year == now.year and exp_month < now.month):
        await update.message.reply_text("❌ Karta muddati tugagan!")
        return ENTER_CARD_EXPIRY

    context.user_data['new_card_expiry'] = expiry
    await update.message.reply_text(
        "👤 Karta egasining ismini kiriting:\n_(Pasportdagi kabi, masalan: ALISHER TOSHMATOV)_",
        parse_mode='Markdown'
    )
    return ENTER_CARD_NAME


async def enter_card_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip().upper()

    if len(name) < 3 or len(name) > 50:
        await update.message.reply_text("❌ Ism noto'g'ri! Qaytadan kiriting:")
        return ENTER_CARD_NAME

    user_id = update.effective_user.id
    card_number = context.user_data['new_card_number']
    expiry = context.user_data['new_card_expiry']

    # Check duplicate
    if db.card_exists(user_id, card_number):
        await update.message.reply_text(
            "❌ Bu karta allaqachon qo'shilgan!",
            reply_markup=get_main_keyboard()
        )
        return ConversationHandler.END

    # Save card
    card_id = db.add_card(user_id, card_number, expiry, name)
    card = db.get_card(card_id)

    success_msg = (
        "✅ *KARTA MUVAFFAQIYATLI QO'SHILDI!*\n"
        f"```{card_message_block(card)}```"
    )

    keyboard = [[
        InlineKeyboardButton("💸 O'tkazma", callback_data=f"transfer_{card_id}"),
        InlineKeyboardButton("⬆️ To'ldirish", callback_data=f"topup_{card_id}"),
    ]]

    await update.message.reply_text(
        success_msg,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    context.user_data.clear()
    return ConversationHandler.END


# ══════════════════════════════════════════
#  PUL O'TKAZISH
# ══════════════════════════════════════════

async def transfer_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    cards = db.get_user_cards(user_id)

    if not cards:
        await update.message.reply_text(
            "❌ Karta yo'q! Avval karta qo'shing.",
            reply_markup=get_main_keyboard()
        )
        return ConversationHandler.END

    keyboard = []
    for card in cards:
        card_type = get_card_type(card['card_number'])
        masked = mask_card(card['card_number'])
        keyboard.append([InlineKeyboardButton(
            f"{card_type} | {masked} | {card['balance']:,.0f} so'm",
            callback_data=f"select_card_{card['id']}"
        )])
    keyboard.append([InlineKeyboardButton("❌ Bekor qilish", callback_data="cancel")])

    msg = "💸 *PUL O'TKAZISH*\n\nQaysi kartadan o'tkazmoqchisiz?"

    if update.callback_query:
        await update.callback_query.edit_message_text(
            msg, parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await update.message.reply_text(
            msg, parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    return ENTER_RECEIVER


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    user_id = update.effective_user.id

    # ── Karta tanlash (o'tkazma uchun) ──
    if data.startswith("select_card_"):
        card_id = int(data.split("_")[-1])
        card = db.get_card(card_id)
        if not card or card['user_id'] != user_id:
            await query.edit_message_text("❌ Xatolik!")
            return

        context.user_data['transfer_card_id'] = card_id
        context.user_data['transfer_card'] = card

        await query.edit_message_text(
            f"💳 Tanlangan karta:\n`{mask_card(card['card_number'])}`\n"
            f"💰 Balans: *{card['balance']:,.0f} so'm*\n\n"
            f"📤 Qabul qiluvchi karta raqamini kiriting:",
            parse_mode='Markdown'
        )
        context.user_data['transfer_step'] = 'receiver'
        return

    # ── Karta o'chirish ──
    elif data.startswith("delete_card_"):
        card_id = int(data.split("_")[-1])
        keyboard = [[
            InlineKeyboardButton("✅ Ha, o'chirish", callback_data=f"confirm_delete_{card_id}"),
            InlineKeyboardButton("❌ Yo'q", callback_data="cancel"),
        ]]
        await query.edit_message_text(
            "⚠️ Kartani o'chirishni tasdiqlaysizmi?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data.startswith("confirm_delete_"):
        card_id = int(data.split("_")[-1])
        db.delete_card(user_id, card_id)
        await query.edit_message_text("🗑 Karta o'chirildi!")

    # ── Balans ──
    elif data.startswith("balance_"):
        card_id = int(data.split("_")[-1])
        card = db.get_card(card_id)
        if card:
            await query.edit_message_text(
                f"💰 *BALANS*\n```{card_message_block(card)}```",
                parse_mode='Markdown'
            )

    # ── To'ldirish ──
    elif data.startswith("topup_"):
        card_id = int(data.split("_")[-1])
        context.user_data['topup_card_id'] = card_id
        context.user_data['transfer_step'] = 'topup_amount'
        await query.edit_message_text(
            "⬆️ *KARTA TO'LDIRISH*\n\nSummani kiriting (so'mda):",
            parse_mode='Markdown'
        )

    # ── O'tkazma ──
    elif data.startswith("transfer_"):
        card_id = int(data.split("_")[-1])
        card = db.get_card(card_id)
        context.user_data['transfer_card_id'] = card_id
        context.user_data['transfer_card'] = card

        await query.edit_message_text(
            f"💳 Tanlangan karta:\n`{mask_card(card['card_number'])}`\n"
            f"💰 Balans: *{card['balance']:,.0f} so'm*\n\n"
            f"📤 Qabul qiluvchi karta raqamini kiriting:",
            parse_mode='Markdown'
        )
        context.user_data['transfer_step'] = 'receiver'

    # ── To'lovni tasdiqlash ──
    elif data == "confirm_payment":
        await process_payment(update, context)

    elif data == "cancel_payment":
        context.user_data.clear()
        await query.edit_message_text("❌ To'lov bekor qilindi.", reply_markup=None)

    # ── Karta qo'shish ──
    elif data == "add_card":
        await query.edit_message_text(
            "💳 *KARTA QO'SHISH*\n\nKarta raqamini kiriting:\n_(16 ta raqam)_",
            parse_mode='Markdown'
        )
        context.user_data['conv_state'] = ENTER_CARD_NUMBER

    elif data == "cancel":
        context.user_data.clear()
        await query.edit_message_text("❌ Bekor qilindi.")


async def process_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """To'lovni amalga oshirish"""
    query = update.callback_query
    data = context.user_data

    card = data.get('transfer_card')
    amount = data.get('transfer_amount', 0)
    receiver = data.get('transfer_receiver', '')
    fee = data.get('transfer_fee', 0)
    total = amount + fee

    if card['balance'] < total:
        await query.edit_message_text(
            f"❌ *Mablag' yetarli emas!*\n\n"
            f"Kerak: {total:,.0f} so'm\n"
            f"Balans: {card['balance']:,.0f} so'm",
            parse_mode='Markdown'
        )
        context.user_data.clear()
        return

    # Pul yechish
    new_balance = db.deduct_balance(card['id'], total)

    # Tranzaksiya saqlash
    tx_id = db.save_transaction(
        user_id=update.effective_user.id,
        card_id=card['id'],
        card_number=card['card_number'],
        amount=amount,
        fee=fee,
        receiver=receiver,
        tx_type='debit',
        status='success'
    )

    tx = db.get_transaction(tx_id)
    receipt = payment_receipt(tx)

    success_msg = (
        f"✅ *TO'LOV AMALGA OSHIRILDI!*\n"
        f"```{receipt}```\n"
        f"💳 Yangi balans: *{new_balance:,.0f} so'm*"
    )

    await query.edit_message_text(success_msg, parse_mode='Markdown')
    context.user_data.clear()


# ══════════════════════════════════════════
#  XABAR HANDLER
# ══════════════════════════════════════════

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    step = context.user_data.get('transfer_step')

    # ── Receiver kiritish ──
    if step == 'receiver':
        raw = re.sub(r'\D', '', text)
        if not validate_card(raw):
            await update.message.reply_text("❌ Noto'g'ri karta raqami! Qaytadan kiriting:")
            return

        context.user_data['transfer_receiver'] = format_card_number(raw)
        context.user_data['transfer_step'] = 'amount'

        await update.message.reply_text(
            f"✅ Qabul qiluvchi: `{format_card_number(raw)}`\n\n"
            f"💵 O'tkazma summini kiriting (so'mda):",
            parse_mode='Markdown'
        )
        return

    # ── Summa kiritish ──
    elif step == 'amount':
        try:
            amount = float(re.sub(r'[^\d.]', '', text))
            if amount < 1000:
                await update.message.reply_text("❌ Minimal summa: 1,000 so'm")
                return
            if amount > 50_000_000:
                await update.message.reply_text("❌ Maksimal summa: 50,000,000 so'm")
                return
        except:
            await update.message.reply_text("❌ Noto'g'ri summa! Raqam kiriting:")
            return

        card = context.user_data.get('transfer_card')
        fee = calculate_fee(amount)
        total = amount + fee

        context.user_data['transfer_amount'] = amount
        context.user_data['transfer_fee'] = fee

        receiver = context.user_data.get('transfer_receiver', 'N/A')

        confirm_msg = (
            f"📋 *TO'LOV MA'LUMOTLARI*\n\n"
            f"💳 Kartadan: `{mask_card(card['card_number'])}`\n"
            f"📤 Karta ga: `{receiver}`\n"
            f"💵 Summa: *{amount:,.0f} so'm*\n"
            f"💸 Komissiya: *{fee:,.0f} so'm*\n"
            f"💰 Jami: *{total:,.0f} so'm*\n\n"
            f"_Joriy balans: {card['balance']:,.0f} so'm_\n\n"
            f"✅ Tasdiqlaysizmi?"
        )

        keyboard = [[
            InlineKeyboardButton("✅ Tasdiqlash", callback_data="confirm_payment"),
            InlineKeyboardButton("❌ Bekor", callback_data="cancel_payment"),
        ]]

        await update.message.reply_text(
            confirm_msg, parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    # ── To'ldirish summasi ──
    elif step == 'topup_amount':
        try:
            amount = float(re.sub(r'[^\d.]', '', text))
            if amount < 1000:
                await update.message.reply_text("❌ Minimal summa: 1,000 so'm")
                return
        except:
            await update.message.reply_text("❌ Noto'g'ri summa!")
            return

        card_id = context.user_data.get('topup_card_id')
        new_balance = db.add_balance(card_id, amount)
        card = db.get_card(card_id)

        # Tranzaksiya saqlash
        db.save_transaction(
            user_id=user_id,
            card_id=card_id,
            card_number=card['card_number'],
            amount=amount,
            fee=0,
            receiver=card['card_name'],
            tx_type='credit',
            status='success'
        )

        await update.message.reply_text(
            f"✅ *KARTA TO'LDIRILDI!*\n\n"
            f"💳 Karta: `{mask_card(card['card_number'])}`\n"
            f"⬆️ Kirim: *+{amount:,.0f} so'm*\n"
            f"💰 Yangi balans: *{new_balance:,.0f} so'm*",
            parse_mode='Markdown'
        )
        context.user_data.clear()
        return

    # ── Tugma bosilishi ──
    if text == "💳 Kartalarim":
        await show_cards(update, context)
    elif text == "➕ Karta qo'shish":
        await add_card_start(update, context)
    elif text == "💸 Pul o'tkazish":
        await transfer_start(update, context)
    elif text == "📊 Hisobot":
        await show_report(update, context)
    elif text == "📋 Tarix":
        await show_history(update, context)
    elif text == "⚙️ Sozlamalar":
        await settings(update, context)


# ══════════════════════════════════════════
#  HISOBOT VA TARIX
# ══════════════════════════════════════════

async def show_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    stats = db.get_user_stats(user_id)
    cards = db.get_user_cards(user_id)

    total_balance = sum(c['balance'] for c in cards)
    total_spent = stats.get('total_debit', 0)
    total_received = stats.get('total_credit', 0)
    tx_count = stats.get('tx_count', 0)

    report = (
        f"📊 *MOLIYAVIY HISOBOT*\n\n"
        f"💳 Kartalar soni: *{len(cards)}*\n"
        f"💰 Umumiy balans: *{total_balance:,.0f} so'm*\n\n"
        f"📈 Bu oy:\n"
        f"  ⬇️ Chiqim: *{total_spent:,.0f} so'm*\n"
        f"  ⬆️ Kirim: *{total_received:,.0f} so'm*\n"
        f"  📋 Tranzaksiyalar: *{tx_count}*\n\n"
        f"_So'nggi yangilanish: {datetime.now().strftime('%d.%m.%Y %H:%M')}_"
    )

    await update.message.reply_text(report, parse_mode='Markdown')


async def show_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    txs = db.get_transactions(user_id, limit=10)

    if not txs:
        await update.message.reply_text("📋 Tranzaksiya tarixi bo'sh.")
        return

    msg = "📋 *SO'NGGI 10 TA TRANZAKSIYA*\n\n"

    for tx in txs:
        emoji = "⬆️" if tx['type'] == 'credit' else "⬇️"
        sign = "+" if tx['type'] == 'credit' else "-"
        status_e = "✅" if tx['status'] == 'success' else "❌"

        msg += (
            f"{status_e} {emoji} `{sign}{tx['amount']:,.0f}` so'm\n"
            f"   💳 {mask_card(tx['card_number'])} → {tx.get('receiver', 'N/A')}\n"
            f"   📅 {tx['created_at']}\n\n"
        )

    await update.message.reply_text(msg, parse_mode='Markdown')


async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = db.get_user(user_id)

    keyboard = [
        [InlineKeyboardButton("🔔 Bildirishnomalar", callback_data="settings_notif")],
        [InlineKeyboardButton("🌐 Til o'zgartirish", callback_data="settings_lang")],
        [InlineKeyboardButton("🔐 Xavfsizlik", callback_data="settings_security")],
    ]

    await update.message.reply_text(
        f"⚙️ *SOZLAMALAR*\n\n"
        f"👤 Ism: {user['full_name']}\n"
        f"🆔 ID: `{user_id}`\n"
        f"📅 Ro'yxatdan: {user['created_at']}\n",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ══════════════════════════════════════════
#  YORDAMCHI
# ══════════════════════════════════════════

def calculate_fee(amount: float) -> float:
    """Komissiya hisoblash: 0.5%, min 500, max 5000 so'm"""
    fee = amount * 0.005
    return min(max(fee, 500), 5000)


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "❌ Bekor qilindi.",
        reply_markup=get_main_keyboard()
    )
    return ConversationHandler.END


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Xatolik: {context.error}")


# ══════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════

def main():
    db.init()

    app = Application.builder().token(BOT_TOKEN).build()

    # Conversation handler - karta qo'shish
    add_card_conv = ConversationHandler(
        entry_points=[
            CommandHandler("addcard", add_card_start),
            MessageHandler(filters.Regex("^➕ Karta qo'shish$"), add_card_start),
        ],
        states={
            ENTER_CARD_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_card_number)],
            ENTER_CARD_EXPIRY: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_card_expiry)],
            ENTER_CARD_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_card_name)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("cards", show_cards))
    app.add_handler(CommandHandler("transfer", transfer_start))
    app.add_handler(CommandHandler("history", show_history))
    app.add_handler(add_card_conv)
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    app.add_error_handler(error_handler)

    logger.info("✅ Bot ishga tushdi!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
