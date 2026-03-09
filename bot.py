#!/usr/bin/env python3
"""
💳 CARD PAYMENT BOT
"""

import logging
import re
from datetime import datetime
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ConversationHandler, filters, ContextTypes
)
from config import BOT_TOKEN
from database import Database
from card_utils import format_card_number, mask_card, validate_card, get_card_type

# ── LOG (faqat stdout — Railway uchun) ──────────────────
logging.basicConfig(
    format='%(asctime)s %(levelname)s %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

db = Database()

# ConversationHandler states
CARD_NUM, CARD_EXP, CARD_NAME = range(3)


# ════════════════════════════════════════
#  YORDAMCHI
# ════════════════════════════════════════

def main_kb():
    return ReplyKeyboardMarkup([
        [KeyboardButton("💳 Kartalarim"), KeyboardButton("➕ Karta qo'shish")],
        [KeyboardButton("💸 Pul o'tkazish"), KeyboardButton("📊 Hisobot")],
        [KeyboardButton("📋 Tarix"), KeyboardButton("⚙️ Sozlamalar")],
    ], resize_keyboard=True)


def card_block(c: dict) -> str:
    ct = get_card_type(c['card_number'])
    icons = {"Visa": "💳", "Mastercard": "💳", "Humo": "🟠", "Uzcard": "🔵"}
    ic = icons.get(ct, "💳")
    return (
        f"╔══════════════════════════╗\n"
        f"║ {ic} {ct:<24}║\n"
        f"║                          ║\n"
        f"║  {mask_card(c['card_number'])}  ║\n"
        f"║                          ║\n"
        f"║  {c['card_name'][:24]:<24}  ║\n"
        f"║  Muddat: {c['expiry']}             ║\n"
        f"║                          ║\n"
        f"║  💰 {c['balance']:>16,.0f} so'm ║\n"
        f"╚══════════════════════════╝"
    )


def calc_fee(amount: float, card_type: str = "") -> float:
    if card_type in ("Humo", "Uzcard"):
        return round(min(max(amount * 0.003, 300), 3000))
    return round(min(max(amount * 0.005, 500), 5000))


# ════════════════════════════════════════
#  START
# ════════════════════════════════════════

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    db.get_or_create_user(u.id, u.full_name, u.username)
    await update.message.reply_text(
        f"🏦 *CARD BOT*ga xush kelibsiz!\n\nSalom, *{u.first_name}*! 👋\n\n"
        "💳 Kartalaringizni boshqaring\n"
        "💸 Pul o'tkazing\n"
        "📊 Balans va tarixni ko'ring\n\n"
        "Pastdagi tugmalardan foydalaning 👇",
        parse_mode='Markdown',
        reply_markup=main_kb()
    )


# ════════════════════════════════════════
#  KARTALAR
# ════════════════════════════════════════

async def show_cards(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    cards = db.get_user_cards(uid)
    if not cards:
        await update.message.reply_text(
            "💳 Hali karta yo'q.\n\n➕ *Karta qo'shish* tugmasini bosing.",
            parse_mode='Markdown', reply_markup=main_kb()
        )
        return
    await update.message.reply_text(f"💳 *Sizda {len(cards)} ta karta:*", parse_mode='Markdown')
    for card in cards:
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("⬆️ To'ldirish", callback_data=f"topup_{card['id']}"),
                InlineKeyboardButton("💸 O'tkazma", callback_data=f"transfer_{card['id']}"),
            ],
            [
                InlineKeyboardButton("📊 Balans", callback_data=f"balance_{card['id']}"),
                InlineKeyboardButton("🗑 O'chirish", callback_data=f"del_{card['id']}"),
            ],
        ])
        await update.message.reply_text(
            f"```\n{card_block(card)}\n```",
            parse_mode='Markdown', reply_markup=kb
        )


# ════════════════════════════════════════
#  KARTA QO'SHISH
# ════════════════════════════════════════

async def add_card_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data.clear()
    msg = update.message or update.callback_query.message
    if update.callback_query:
        await update.callback_query.answer()
    await msg.reply_text(
        "💳 *KARTA QO'SHISH*\n\nKarta raqamini kiriting:\n_16 ta raqam, masalan: 8600 1234 5678 9012_",
        parse_mode='Markdown'
    )
    return CARD_NUM


async def got_card_num(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    raw = re.sub(r'\D', '', update.message.text)
    if not validate_card(raw):
        await update.message.reply_text(
            "❌ Noto'g'ri karta raqami!\n\n16 ta raqam kiriting:",
            parse_mode='Markdown'
        )
        return CARD_NUM
    ctx.user_data['card_number'] = raw
    ct = get_card_type(raw)
    await update.message.reply_text(
        f"✅ *{ct}* karta aniqlandi!\n`{format_card_number(raw)}`\n\n"
        f"Amal qilish muddatini kiriting:\n_MM/YY, masalan: 12/26_",
        parse_mode='Markdown'
    )
    return CARD_EXP


async def got_card_exp(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    exp = update.message.text.strip()
    if not re.match(r'^(0[1-9]|1[0-2])\/\d{2}$', exp):
        await update.message.reply_text("❌ Format noto'g'ri! MM/YY ko'rinishida:\n_12/26_", parse_mode='Markdown')
        return CARD_EXP
    m, y = exp.split('/')
    now = datetime.now()
    if (2000 + int(y)) < now.year or ((2000 + int(y)) == now.year and int(m) < now.month):
        await update.message.reply_text("❌ Karta muddati tugagan!")
        return CARD_EXP
    ctx.user_data['expiry'] = exp
    await update.message.reply_text(
        "👤 Karta egasining ismini kiriting:\n_Pasportdagidek, masalan: ALISHER TOSHMATOV_",
        parse_mode='Markdown'
    )
    return CARD_NAME


async def got_card_name(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip().upper()
    if len(name) < 3:
        await update.message.reply_text("❌ Ism juda qisqa!")
        return CARD_NAME
    uid = update.effective_user.id
    cn = ctx.user_data.get('card_number', '')
    if not cn:
        await update.message.reply_text("❌ Xatolik! /start bosing.", reply_markup=main_kb())
        return ConversationHandler.END
    if db.card_exists(uid, cn):
        await update.message.reply_text("❌ Bu karta allaqachon qo'shilgan!", reply_markup=main_kb())
        ctx.user_data.clear()
        return ConversationHandler.END
    db.get_or_create_user(uid, update.effective_user.full_name, update.effective_user.username)
    cid = db.add_card(uid, cn, ctx.user_data['expiry'], name)
    card = db.get_card(cid)
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("⬆️ To'ldirish", callback_data=f"topup_{cid}"),
        InlineKeyboardButton("💸 O'tkazma", callback_data=f"transfer_{cid}"),
    ]])
    await update.message.reply_text(
        f"✅ *Karta muvaffaqiyatli qo'shildi!*\n```\n{card_block(card)}\n```",
        parse_mode='Markdown', reply_markup=kb
    )
    ctx.user_data.clear()
    return ConversationHandler.END


async def conv_cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data.clear()
    await update.message.reply_text("❌ Bekor qilindi.", reply_markup=main_kb())
    return ConversationHandler.END


# ════════════════════════════════════════
#  CALLBACK HANDLER
# ════════════════════════════════════════

async def on_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data
    uid = update.effective_user.id

    try:
        # ── BALANS ──
        if data.startswith("balance_"):
            cid = int(data.split("_")[1])
            card = db.get_card(cid)
            if card and card['user_id'] == uid:
                await q.message.reply_text(
                    f"💰 *Joriy balans*\n```\n{card_block(card)}\n```",
                    parse_mode='Markdown'
                )

        # ── TO'LDIRISH ──
        elif data.startswith("topup_"):
            cid = int(data.split("_")[1])
            card = db.get_card(cid)
            if not card or card['user_id'] != uid:
                await q.answer("❌ Xatolik!", show_alert=True)
                return
            ctx.user_data.clear()
            ctx.user_data['action'] = 'topup'
            ctx.user_data['card_id'] = cid
            await q.message.reply_text(
                f"⬆️ *KARTA TO'LDIRISH*\n\n"
                f"💳 Karta: `{mask_card(card['card_number'])}`\n"
                f"💰 Joriy balans: *{card['balance']:,.0f} so'm*\n\n"
                f"✏️ Qancha so'm kiritmoqchisiz?\n_(masalan: 50000)_",
                parse_mode='Markdown'
            )

        # ── O'TKAZMA ──
        elif data.startswith("transfer_"):
            cid = int(data.split("_")[1])
            card = db.get_card(cid)
            if not card or card['user_id'] != uid:
                await q.answer("❌ Xatolik!", show_alert=True)
                return
            ctx.user_data.clear()
            ctx.user_data['action'] = 'transfer_receiver'
            ctx.user_data['card_id'] = cid
            await q.message.reply_text(
                f"💸 *PUL O'TKAZISH*\n\n"
                f"💳 Kartadan: `{mask_card(card['card_number'])}`\n"
                f"💰 Balans: *{card['balance']:,.0f} so'm*\n\n"
                f"📤 Qabul qiluvchi karta raqamini kiriting:",
                parse_mode='Markdown'
            )

        # ── KARTA TANLASH (o'tkazma menyusidan) ──
        elif data.startswith("pick_"):
            cid = int(data.split("_")[1])
            card = db.get_card(cid)
            if not card:
                return
            ctx.user_data.clear()
            ctx.user_data['action'] = 'transfer_receiver'
            ctx.user_data['card_id'] = cid
            await q.edit_message_text(
                f"💸 *PUL O'TKAZISH*\n\n"
                f"💳 Tanlandi: `{mask_card(card['card_number'])}`\n"
                f"💰 Balans: *{card['balance']:,.0f} so'm*\n\n"
                f"📤 Qabul qiluvchi karta raqamini kiriting:",
                parse_mode='Markdown'
            )

        # ── O'CHIRISH ──
        elif data.startswith("del_"):
            cid = int(data.split("_")[1])
            kb = InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ Ha, o'chirish", callback_data=f"delok_{cid}"),
                InlineKeyboardButton("❌ Yo'q", callback_data="noop"),
            ]])
            await q.edit_message_reply_markup(reply_markup=kb)

        elif data.startswith("delok_"):
            cid = int(data.split("_")[1])
            db.delete_card(uid, cid)
            await q.edit_message_text("🗑 Karta o'chirildi!")

        # ── TO'LOVNI TASDIQLASH ──
        elif data == "pay_yes":
            card_id  = ctx.user_data.get('card_id')
            amount   = ctx.user_data.get('amount', 0)
            fee      = ctx.user_data.get('fee', 0)
            receiver = ctx.user_data.get('receiver', '')
            total    = amount + fee

            if not card_id:
                await q.edit_message_text("❌ Ma'lumot yo'qoldi. Qaytadan urinib ko'ring.")
                ctx.user_data.clear()
                return

            card = db.get_card(card_id)
            if not card:
                await q.edit_message_text("❌ Karta topilmadi.")
                ctx.user_data.clear()
                return

            # Balans tekshiruv
            fresh = db.get_card(card_id)
            if fresh['balance'] < total:
                await q.edit_message_text(
                    f"❌ *Mablag' yetarli emas!*\n\n"
                    f"Kerak: *{total:,.0f} so'm*\n"
                    f"Balans: *{fresh['balance']:,.0f} so'm*",
                    parse_mode='Markdown'
                )
                ctx.user_data.clear()
                return

            new_bal = db.deduct_balance(card_id, total)
            tx_id = db.save_transaction(
                user_id=uid, card_id=card_id,
                card_number=card['card_number'],
                amount=amount, fee=fee,
                receiver=receiver,
                tx_type='debit', status='success'
            )
            ctx.user_data.clear()
            await q.edit_message_text(
                f"✅ *TO'LOV AMALGA OSHIRILDI!*\n\n"
                f"📌 Tranzaksiya: `#{tx_id}`\n"
                f"💳 Kartadan: `{mask_card(card['card_number'])}`\n"
                f"📤 Qabul qiluvchi: `{receiver}`\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"💵 Summa: *{amount:,.0f} so'm*\n"
                f"💸 Komissiya: *{fee:,.0f} so'm*\n"
                f"💰 Yangi balans: *{new_bal:,.0f} so'm*\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}",
                parse_mode='Markdown'
            )

        elif data == "pay_no":
            ctx.user_data.clear()
            await q.edit_message_text("❌ To'lov bekor qilindi.")

        elif data == "noop":
            pass

    except Exception as e:
        logger.error(f"Callback xatosi [{data}]: {e}", exc_info=True)
        try:
            await q.message.reply_text("⚠️ Xatolik yuz berdi. Qaytadan urinib ko'ring.")
        except:
            pass


# ════════════════════════════════════════
#  MATN XABARLAR
# ════════════════════════════════════════

async def on_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    uid  = update.effective_user.id
    action = ctx.user_data.get('action', '')

    try:
        # ════ TO'LDIRISH SUMMASI ════
        if action == 'topup':
            raw = re.sub(r'[^\d.]', '', text)
            if not raw:
                await update.message.reply_text("❌ Faqat raqam kiriting, masalan: *50000*", parse_mode='Markdown')
                return
            amount = float(raw)
            if amount < 1000:
                await update.message.reply_text("❌ Minimal summa: *1,000 so'm*", parse_mode='Markdown')
                return
            if amount > 100_000_000:
                await update.message.reply_text("❌ Maksimal summa: *100,000,000 so'm*", parse_mode='Markdown')
                return

            cid  = ctx.user_data.get('card_id')
            if not cid:
                await update.message.reply_text("❌ Xatolik! Kartani qaytadan tanlang.", reply_markup=main_kb())
                ctx.user_data.clear()
                return

            new_bal = db.add_balance(cid, amount)
            card    = db.get_card(cid)

            db.save_transaction(
                user_id=uid, card_id=cid,
                card_number=card['card_number'],
                amount=amount, fee=0,
                receiver=card['card_name'],
                tx_type='credit', status='success'
            )
            ctx.user_data.clear()
            await update.message.reply_text(
                f"✅ *KARTA TO'LDIRILDI!*\n\n"
                f"💳 Karta: `{mask_card(card['card_number'])}`\n"
                f"⬆️ Kirim: *+{amount:,.0f} so'm*\n"
                f"💰 Yangi balans: *{new_bal:,.0f} so'm*\n\n"
                f"📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}",
                parse_mode='Markdown',
                reply_markup=main_kb()
            )
            return

        # ════ O'TKAZMA: QABUL QILUVCHI ════
        elif action == 'transfer_receiver':
            raw = re.sub(r'\D', '', text)
            if not validate_card(raw):
                await update.message.reply_text("❌ Noto'g'ri karta raqami! Qaytadan kiriting:")
                return
            ctx.user_data['receiver'] = format_card_number(raw)
            ctx.user_data['action']   = 'transfer_amount'
            cid  = ctx.user_data.get('card_id')
            card = db.get_card(cid)
            await update.message.reply_text(
                f"✅ Qabul qiluvchi: `{format_card_number(raw)}`\n\n"
                f"💰 Joriy balansiz: *{card['balance']:,.0f} so'm*\n\n"
                f"💵 Qancha so'm o'tkazmoqchisiz?",
                parse_mode='Markdown'
            )
            return

        # ════ O'TKAZMA: SUMMA ════
        elif action == 'transfer_amount':
            raw = re.sub(r'[^\d.]', '', text)
            if not raw:
                await update.message.reply_text("❌ Faqat raqam kiriting:")
                return
            amount = float(raw)
            if amount < 1000:
                await update.message.reply_text("❌ Minimal: *1,000 so'm*", parse_mode='Markdown')
                return
            if amount > 50_000_000:
                await update.message.reply_text("❌ Maksimal: *50,000,000 so'm*", parse_mode='Markdown')
                return

            cid      = ctx.user_data.get('card_id')
            card     = db.get_card(cid)
            ctype    = get_card_type(card['card_number'])
            fee      = calc_fee(amount, ctype)
            total    = amount + fee
            receiver = ctx.user_data.get('receiver', '')

            ctx.user_data['amount'] = amount
            ctx.user_data['fee']    = fee
            ctx.user_data['action'] = 'transfer_confirm'

            kb = InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ Tasdiqlash", callback_data="pay_yes"),
                InlineKeyboardButton("❌ Bekor", callback_data="pay_no"),
            ]])
            await update.message.reply_text(
                f"📋 *TO'LOV MA'LUMOTLARI*\n\n"
                f"💳 Kartadan: `{mask_card(card['card_number'])}`\n"
                f"📤 Karta ga: `{receiver}`\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"💵 Summa: *{amount:,.0f} so'm*\n"
                f"💸 Komissiya ({ctype}): *{fee:,.0f} so'm*\n"
                f"💰 Jami yechiladigan: *{total:,.0f} so'm*\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"_Balans: {card['balance']:,.0f} so'm_\n\n"
                f"Tasdiqlaysizmi?",
                parse_mode='Markdown', reply_markup=kb
            )
            return

        # ════ TUGMALAR ════
        if text == "💳 Kartalarim":
            await show_cards(update, ctx)
        elif text == "➕ Karta qo'shish":
            await add_card_start(update, ctx)
        elif text == "💸 Pul o'tkazish":
            await transfer_menu(update, ctx)
        elif text == "📊 Hisobot":
            await show_report(update, ctx)
        elif text == "📋 Tarix":
            await show_history(update, ctx)
        elif text == "⚙️ Sozlamalar":
            await show_settings(update, ctx)
        else:
            if not action:
                await update.message.reply_text(
                    "❓ Tushunmadim. Quyidagi tugmalardan foydalaning 👇",
                    reply_markup=main_kb()
                )

    except Exception as e:
        logger.error(f"on_message xatosi [action={action}]: {e}", exc_info=True)
        ctx.user_data.clear()
        await update.message.reply_text(
            "⚠️ Xatolik yuz berdi. Qaytadan urinib ko'ring.",
            reply_markup=main_kb()
        )


# ════════════════════════════════════════
#  O'TKAZMA MENYU
# ════════════════════════════════════════

async def transfer_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid   = update.effective_user.id
    cards = db.get_user_cards(uid)
    if not cards:
        await update.message.reply_text("❌ Karta yo'q! Avval karta qo'shing.")
        return
    if len(cards) == 1:
        # Faqat 1 ta karta bo'lsa to'g'ridan-to'g'ri o'tkazmaga o'tish
        card = cards[0]
        ctx.user_data.clear()
        ctx.user_data['action']  = 'transfer_receiver'
        ctx.user_data['card_id'] = card['id']
        await update.message.reply_text(
            f"💸 *PUL O'TKAZISH*\n\n"
            f"💳 Kartadan: `{mask_card(card['card_number'])}`\n"
            f"💰 Balans: *{card['balance']:,.0f} so'm*\n\n"
            f"📤 Qabul qiluvchi karta raqamini kiriting:",
            parse_mode='Markdown'
        )
        return
    kb = [[InlineKeyboardButton(
        f"{get_card_type(c['card_number'])} | {mask_card(c['card_number'])} | {c['balance']:,.0f} so'm",
        callback_data=f"pick_{c['id']}"
    )] for c in cards]
    await update.message.reply_text(
        "💸 *Qaysi kartadan o'tkazasiz?*",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(kb)
    )


# ════════════════════════════════════════
#  HISOBOT, TARIX, SOZLAMALAR
# ════════════════════════════════════════

async def show_report(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid   = update.effective_user.id
    cards = db.get_user_cards(uid)
    stats = db.get_user_stats(uid)
    total = sum(c['balance'] for c in cards)
    await update.message.reply_text(
        f"📊 *MOLIYAVIY HISOBOT*\n\n"
        f"💳 Kartalar: *{len(cards)} ta*\n"
        f"💰 Umumiy balans: *{total:,.0f} so'm*\n\n"
        f"📅 Bu oy:\n"
        f"  ⬇️ Chiqim: *{stats.get('total_debit', 0):,.0f} so'm*\n"
        f"  ⬆️ Kirim: *{stats.get('total_credit', 0):,.0f} so'm*\n"
        f"  🔢 Tranzaksiyalar: *{stats.get('tx_count', 0)} ta*\n\n"
        f"_So'nggi yangilanish: {datetime.now().strftime('%d.%m.%Y %H:%M')}_",
        parse_mode='Markdown'
    )


async def show_history(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    txs = db.get_transactions(uid, limit=15)
    if not txs:
        await update.message.reply_text("📋 Tarix bo'sh.")
        return
    msg = "📋 *SO'NGGI TRANZAKSIYALAR*\n\n"
    for tx in txs:
        e  = "⬆️" if tx['type'] == 'credit' else "⬇️"
        s  = "+" if tx['type'] == 'credit' else "-"
        ok = "✅" if tx['status'] == 'success' else "❌"
        msg += (
            f"{ok} {e} *{s}{tx['amount']:,.0f} so'm*\n"
            f"   💳 {mask_card(tx['card_number'])}\n"
            f"   📅 {tx['created_at']}\n\n"
        )
    await update.message.reply_text(msg, parse_mode='Markdown')


async def show_settings(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    await update.message.reply_text(
        f"⚙️ *SOZLAMALAR*\n\n"
        f"👤 Ism: *{u.full_name}*\n"
        f"🆔 Telegram ID: `{u.id}`\n\n"
        f"Bot v2.0",
        parse_mode='Markdown'
    )


async def on_error(update, ctx):
    logger.error(f"Global xatolik: {ctx.error}", exc_info=ctx.error)


# ════════════════════════════════════════
#  MAIN
# ════════════════════════════════════════

def main():
    db.init()
    logger.info(f"DB: {db.db_path}")

    app = Application.builder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[
            CommandHandler("addcard", add_card_start),
            MessageHandler(filters.Regex(r"^➕ Karta qo'shish$"), add_card_start),
        ],
        states={
            CARD_NUM:  [MessageHandler(filters.TEXT & ~filters.COMMAND, got_card_num)],
            CARD_EXP:  [MessageHandler(filters.TEXT & ~filters.COMMAND, got_card_exp)],
            CARD_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, got_card_name)],
        },
        fallbacks=[
            CommandHandler("cancel", conv_cancel),
            CommandHandler("start", conv_cancel),
        ],
        allow_reentry=True,
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", start))
    app.add_handler(CommandHandler("cards", show_cards))
    app.add_handler(CommandHandler("history", show_history))
    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))
    app.add_error_handler(on_error)

    logger.info("✅ Bot ishga tushdi!")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == '__main__':
    main()
