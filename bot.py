# ═══════════════════════════════════════════════════════════════
#  Telegram View Booster Bot — Advanced Professional Edition
#  Features: bKash / Nagad / Binance BEP20 Deposit System
#            Admin Panel, Order Tracking, Referral System
# ═══════════════════════════════════════════════════════════════

import re
import time
import logging
import requests
import telebot
from telebot.types import (
    KeyboardButton, ReplyKeyboardMarkup,
    InlineKeyboardButton, InlineKeyboardMarkup,
)

from config import (
    BOT_TOKEN, ADMIN_USER_ID, ADMIN_USERNAME,
    SMM_PANEL_API, SMM_PANEL_URL, SMM_SERVICE_ID,
    WELCOME_BONUS, REF_BONUS, MIN_VIEW, MAX_VIEW,
    REQUIRED_CHANNELS, PAYMENT_CHANNEL,
    BKASH_NUMBER, NAGAD_NUMBER, BINANCE_BEP20_ADDRESS,
    DEPOSIT_PACKAGES,
)
from database import (
    init_database,
    user_exists, create_user, get_user, update_user_info,
    add_balance, cut_balance,
    set_welcome_bonus_claimed, set_referred_status,
    increment_ref_count, increment_order_count,
    get_all_user_ids, get_user_count,
    ban_user, unban_user, is_banned,
    create_deposit, get_deposit, approve_deposit, reject_deposit,
    get_pending_deposits, get_user_deposits, get_total_deposits_stats,
    create_order, get_total_orders_stats,
)

# ── Logging ───────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# ── Bot Instance ──────────────────────────────────────
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# ── In-Memory State for Multi-Step Flows ──────────────
# user_id -> { "step": ..., "data": { ... } }
user_state: dict[int, dict] = {}


# ══════════════════════════════════════════════════════
#  UTILITY FUNCTIONS
# ══════════════════════════════════════════════════════

def fmt(number) -> str:
    """Format number with commas: 1000000 → 1,000,000"""
    if isinstance(number, float) and number == int(number):
        number = int(number)
    return f"{number:,}"


def main_menu_markup() -> ReplyKeyboardMarkup:
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        KeyboardButton("👁‍🗨 Order Views"),
        KeyboardButton("👤 My Account"),
        KeyboardButton("💰 Deposit"),
        KeyboardButton("💳 Pricing"),
        KeyboardButton("🗣 Invite Friends"),
        KeyboardButton("📜 Help"),
    )
    return markup


def cancel_markup() -> ReplyKeyboardMarkup:
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton("✘ Cancel"))
    return markup


def is_member_of_channels(user_id: int) -> bool:
    for channel in REQUIRED_CHANNELS:
        try:
            status = bot.get_chat_member(channel, user_id).status
            if status not in ("member", "administrator", "creator"):
                return False
        except Exception:
            return False
    return True


def is_valid_telegram_link(link: str) -> bool:
    return bool(re.match(r"^https?://t\.me/[a-zA-Z0-9_]{5,}/\d+$", link))


def send_smm_order(link: str, quantity: int) -> dict | None:
    try:
        resp = requests.post(SMM_PANEL_URL, data={
            "key": SMM_PANEL_API,
            "action": "add",
            "service": SMM_SERVICE_ID,
            "link": link,
            "quantity": quantity,
        }, timeout=30)
        return resp.json()
    except Exception as e:
        logger.error(f"SMM panel error: {e}")
        return None


def clear_state(user_id: int) -> None:
    user_state.pop(user_id, None)


def ensure_registered(message) -> dict | None:
    """Register user if new, return user data. Returns None if banned."""
    uid = str(message.from_user.id)
    if not user_exists(uid):
        create_user(
            uid,
            username=message.from_user.username or "",
            first_name=message.from_user.first_name or "",
        )
    else:
        update_user_info(
            uid,
            username=message.from_user.username or "",
            first_name=message.from_user.first_name or "",
        )
    if is_banned(uid):
        bot.reply_to(message, "🚫 Your account has been suspended. Contact admin.")
        return None
    return get_user(uid)


# ══════════════════════════════════════════════════════
#  /start COMMAND
# ══════════════════════════════════════════════════════

@bot.message_handler(commands=["start"])
def cmd_start(message):
    user_id = message.from_user.id
    uid = str(user_id)
    first_name = message.from_user.first_name or "User"

    # ── Parse referral ────────────────────────────────
    parts = message.text.split()
    ref_by = None
    if len(parts) > 1 and parts[1].isdigit() and int(parts[1]) != user_id:
        if user_exists(parts[1]):
            ref_by = parts[1]

    # ── Register user ─────────────────────────────────
    if not user_exists(uid):
        create_user(
            uid,
            username=message.from_user.username or "",
            first_name=first_name,
            ref_by=ref_by or "none",
        )
        if ref_by:
            increment_ref_count(ref_by)
    else:
        update_user_info(uid, message.from_user.username or "", first_name)

    if is_banned(uid):
        bot.reply_to(message, "🚫 Your account has been suspended.")
        return

    # ── Force join check ──────────────────────────────
    if not is_member_of_channels(user_id):
        channels_text = "\n".join(f"  • {ch}" for ch in REQUIRED_CHANNELS)
        markup = InlineKeyboardMarkup()
        for ch in REQUIRED_CHANNELS:
            markup.add(InlineKeyboardButton(
                f"Join {ch}", url=f"https://t.me/{ch.lstrip('@')}"
            ))
        markup.add(InlineKeyboardButton("✅ I Joined", callback_data="check_join"))
        bot.send_message(
            user_id,
            f"🔒 <b>Please join the required channels first:</b>\n\n"
            f"{channels_text}\n\n"
            f"After joining, tap <b>✅ I Joined</b> below.",
            reply_markup=markup,
        )
        return

    # ── Welcome bonus ─────────────────────────────────
    data = get_user(uid)
    if data and data["welcome_bonus"] == 0:
        add_balance(uid, WELCOME_BONUS)
        set_welcome_bonus_claimed(uid)
        bot.send_message(
            user_id,
            f"🎁 <b>Welcome Bonus!</b>\n"
            f"+ {fmt(WELCOME_BONUS)} views added to your balance!",
        )

    # ── Referral bonus (one-time) ─────────────────────
    data = get_user(uid)
    if data and data["ref_by"] != "none" and data["referred"] == 0:
        try:
            add_balance(data["ref_by"], REF_BONUS)
            bot.send_message(
                int(data["ref_by"]),
                f"🎉 <b>{first_name}</b> joined via your referral!\n"
                f"+ {fmt(REF_BONUS)} views added to your balance!",
            )
        except Exception:
            pass
        set_referred_status(uid)

    # ── Main menu ─────────────────────────────────────
    bot.send_message(
        user_id,
        f"👋 <b>Welcome, {first_name}!</b>\n\n"
        f"With <b>View Booster Bot</b> you can increase the views of "
        f"your Telegram posts in just a few steps.\n\n"
        f"👇 Choose an option below to get started:",
        reply_markup=main_menu_markup(),
    )


# ══════════════════════════════════════════════════════
#  CALLBACK: Check Join
# ══════════════════════════════════════════════════════

@bot.callback_query_handler(func=lambda c: c.data == "check_join")
def cb_check_join(call):
    user_id = call.from_user.id
    if is_member_of_channels(user_id):
        bot.answer_callback_query(call.id, "✅ Verified! Send /start again.")
        bot.delete_message(call.message.chat.id, call.message.message_id)
        cmd_start(call.message)
    else:
        bot.answer_callback_query(
            call.id, "❌ You haven't joined all channels yet!", show_alert=True
        )


# ══════════════════════════════════════════════════════
#  MENU HANDLERS
# ══════════════════════════════════════════════════════

@bot.message_handler(func=lambda m: m.text == "👤 My Account")
def menu_account(message):
    data = ensure_registered(message)
    if not data:
        return
    uid = str(message.from_user.id)
    bot_username = bot.get_me().username
    ref_link = f"https://t.me/{bot_username}?start={uid}"

    bot.reply_to(
        message,
        f"<b>━━━━ 👤 My Account ━━━━</b>\n\n"
        f"🆔 <b>User ID:</b> <code>{uid}</code>\n"
        f"👤 <b>Username:</b> @{data['username'] or 'N/A'}\n"
        f"👁‍🗨 <b>Balance:</b> <code>{fmt(data['balance'])}</code> Views\n"
        f"🗣 <b>Referrals:</b> {data['total_refs']}\n"
        f"📦 <b>Total Orders:</b> {data['total_orders']}\n"
        f"🔗 <b>Referral Link:</b>\n<code>{ref_link}</code>\n\n"
        f"💡 Share your link to earn <b>{fmt(REF_BONUS)}</b> views per referral!",
    )


@bot.message_handler(func=lambda m: m.text == "🗣 Invite Friends")
def menu_invite(message):
    data = ensure_registered(message)
    if not data:
        return
    uid = str(message.from_user.id)
    bot_username = bot.get_me().username
    ref_link = f"https://t.me/{bot_username}?start={uid}"

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton(
        "📤 Share with Friends",
        url=f"https://t.me/share/url?url={ref_link}&text="
            f"🚀 Get free Telegram post views! Join now!"
    ))

    bot.reply_to(
        message,
        f"<b>━━━━ 🗣 Invite Friends ━━━━</b>\n\n"
        f"🔗 <b>Your Referral Link:</b>\n<code>{ref_link}</code>\n\n"
        f"🎁 <b>You get:</b> {fmt(REF_BONUS)} views per referral\n"
        f"🎁 <b>Friend gets:</b> {fmt(WELCOME_BONUS)} views welcome bonus\n"
        f"👥 <b>Your Referrals:</b> {data['total_refs']}\n\n"
        f"📤 Tap the button below to share:",
        reply_markup=markup,
    )


@bot.message_handler(func=lambda m: m.text == "📜 Help")
def menu_help(message):
    bot.reply_to(
        message,
        f"<b>━━━━ ❓ FAQ ━━━━</b>\n\n"
        f"<b>Q: Are the views real?</b>\n"
        f"No, the views are generated and not from real users.\n\n"
        f"<b>Q: Min/Max views per order?</b>\n"
        f"Min: {fmt(MIN_VIEW)} — Max: {fmt(MAX_VIEW)} views per post.\n\n"
        f"<b>Q: What is the view speed?</b>\n"
        f"Average 40–80 views per minute per post, depending on server load.\n\n"
        f"<b>Q: How to add balance?</b>\n"
        f"1️⃣ Invite friends — earn <b>{fmt(REF_BONUS)}</b> views each.\n"
        f"2️⃣ Deposit via <b>bKash / Nagad / Binance (USDT BEP20)</b>.\n\n"
        f"<b>Q: Can I transfer balance?</b>\n"
        f"Yes, if balance > 10K. Contact {ADMIN_USERNAME}.\n\n"
        f"🆘 <b>Need help?</b> Contact {ADMIN_USERNAME}",
    )


@bot.message_handler(func=lambda m: m.text == "💳 Pricing")
def menu_pricing(message):
    ensure_registered(message)
    uid = str(message.from_user.id)

    pkg_lines = []
    for i, pkg in enumerate(DEPOSIT_PACKAGES, 1):
        views_k = pkg["views"] // 1000
        rate = pkg["price_bdt"] / views_k
        pkg_lines.append(
            f"  {get_number_emoji(i)} <b>{fmt(pkg['views'])} views</b>\n"
            f"      💵 {pkg['price_usd']}$ / ৳{fmt(pkg['price_bdt'])} "
            f"<i>(৳{rate:.2f}/K)</i>"
        )

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton(
        "💰 Deposit Now", callback_data="deposit_start"
    ))

    bot.reply_to(
        message,
        f"<b>━━━━ 💎 Pricing ━━━━</b>\n\n"
        f"<i>Choose a package and deposit via bKash, Nagad or Binance.</i>\n\n"
        f"<b>📜 Packages:</b>\n\n"
        + "\n\n".join(pkg_lines) +
        f"\n\n<b>💳 Payment Methods:</b>\n"
        f"  • bKash (Send Money)\n"
        f"  • Nagad (Send Money)\n"
        f"  • Binance USDT (BEP20)\n\n"
        f"🆔 <b>Your ID:</b> <code>{uid}</code>",
        reply_markup=markup,
    )


def get_number_emoji(n: int) -> str:
    emojis = {1: "➊", 2: "➋", 3: "➌", 4: "➍", 5: "➎", 6: "➏",
              7: "➐", 8: "➑", 9: "➒", 10: "➓"}
    return emojis.get(n, f"{n}.")


# ══════════════════════════════════════════════════════
#  ORDER VIEWS FLOW
# ══════════════════════════════════════════════════════

@bot.message_handler(func=lambda m: m.text == "👁‍🗨 Order Views")
def menu_order_views(message):
    data = ensure_registered(message)
    if not data:
        return
    user_id = message.from_user.id

    user_state[user_id] = {"step": "order_amount", "data": {}}

    bot.reply_to(
        message,
        f"<b>👁‍🗨 Order Views</b>\n\n"
        f"Enter the number of views ({fmt(MIN_VIEW)} – {fmt(MAX_VIEW)}):\n\n"
        f"👁‍🗨 <b>Your Balance:</b> <code>{fmt(data['balance'])}</code> views",
        reply_markup=cancel_markup(),
    )


@bot.message_handler(func=lambda m: m.text == "✘ Cancel")
def handle_cancel(message):
    clear_state(message.from_user.id)
    bot.reply_to(
        message,
        "✅ Operation cancelled.",
        reply_markup=main_menu_markup(),
    )


@bot.message_handler(func=lambda m: user_state.get(m.from_user.id, {}).get("step") == "order_amount")
def step_order_amount(message):
    user_id = message.from_user.id
    uid = str(user_id)
    text = message.text.strip()

    if text == "✘ Cancel":
        handle_cancel(message)
        return

    if not text.isdigit():
        bot.reply_to(message, "📛 Please enter a <b>numeric</b> value only.")
        return

    amount = int(text)
    data = get_user(uid)
    balance = data["balance"]

    if amount < MIN_VIEW:
        bot.reply_to(message, f"❌ Minimum order is <b>{fmt(MIN_VIEW)}</b> views.")
        return
    if amount > MAX_VIEW:
        bot.reply_to(message, f"❌ Maximum order is <b>{fmt(MAX_VIEW)}</b> views.")
        return
    if amount > balance:
        bot.reply_to(
            message,
            f"❌ Insufficient balance!\n"
            f"Required: <b>{fmt(amount)}</b> — Available: <b>{fmt(balance)}</b>\n\n"
            f"💡 Deposit via <b>💰 Deposit</b> to add more views.",
        )
        clear_state(user_id)
        return

    user_state[user_id] = {"step": "order_link", "data": {"amount": amount}}
    bot.reply_to(
        message,
        f"✅ Amount: <b>{fmt(amount)}</b> views\n\n"
        f"🔗 Now send the Telegram post link:\n"
        f"<i>Example: https://t.me/channelname/123</i>",
        reply_markup=cancel_markup(),
    )


@bot.message_handler(func=lambda m: user_state.get(m.from_user.id, {}).get("step") == "order_link")
def step_order_link(message):
    user_id = message.from_user.id
    uid = str(user_id)
    link = message.text.strip()

    if link == "✘ Cancel":
        handle_cancel(message)
        return

    if not is_valid_telegram_link(link):
        bot.reply_to(
            message,
            "❌ Invalid link! Please send a valid Telegram post link.\n"
            "<i>Example: https://t.me/channelname/123</i>",
        )
        return

    state_data = user_state[user_id]["data"]
    amount = state_data["amount"]

    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("✅ Confirm", callback_data=f"confirm_order:{amount}:{link}"),
        InlineKeyboardButton("❌ Cancel", callback_data="cancel_order"),
    )

    bot.reply_to(
        message,
        f"<b>━━━━ 📋 Order Summary ━━━━</b>\n\n"
        f"👁‍🗨 <b>Views:</b> {fmt(amount)}\n"
        f"🔗 <b>Link:</b> {link}\n"
        f"💰 <b>Cost:</b> {fmt(amount)} views from balance\n\n"
        f"<i>Tap ✅ Confirm to place the order.</i>",
        reply_markup=markup,
    )
    clear_state(user_id)


@bot.callback_query_handler(func=lambda c: c.data.startswith("confirm_order:"))
def cb_confirm_order(call):
    user_id = call.from_user.id
    uid = str(user_id)
    parts = call.data.split(":", 2)
    amount = int(parts[1])
    link = parts[2]

    data = get_user(uid)
    if not data or data["balance"] < amount:
        bot.answer_callback_query(call.id, "❌ Insufficient balance!", show_alert=True)
        return

    bot.answer_callback_query(call.id, "⏳ Processing your order...")
    bot.edit_message_text(
        "⏳ <b>Submitting your order...</b>",
        call.message.chat.id, call.message.message_id,
    )

    result = send_smm_order(link, amount)

    if not result or "order" not in result or result["order"] is None:
        error_msg = result.get("error", "Unknown error") if result else "Connection failed"
        bot.edit_message_text(
            f"❌ <b>Order failed!</b>\n\n<i>{error_msg}</i>\n\nPlease try again later.",
            call.message.chat.id, call.message.message_id,
        )
        return

    oid = result["order"]
    cut_balance(uid, float(amount))
    increment_order_count(uid, float(amount))
    create_order(uid, str(oid), link, amount)

    bot.edit_message_text(
        f"<b>━━━━ ✅ Order Placed ━━━━</b>\n\n"
        f"📋 <b>Order ID:</b> <code>{oid}</code>\n"
        f"🔗 <b>Link:</b> {link}\n"
        f"👁‍🗨 <b>Views:</b> {fmt(amount)}\n"
        f"💰 <b>Cost:</b> {fmt(amount)} views\n\n"
        f"⏳ Views will start within a few minutes.\n"
        f"😊 Thank you for your order!",
        call.message.chat.id, call.message.message_id,
        disable_web_page_preview=True,
    )

    try:
        bot.send_message(
            PAYMENT_CHANNEL,
            f"<b>━━━━ 🆕 New Order ━━━━</b>\n\n"
            f"📋 <b>Order ID:</b> <code>{oid}</code>\n"
            f"👤 <b>User:</b> {call.from_user.first_name}\n"
            f"🆔 <b>User ID:</b> <code>{uid}</code>\n"
            f"👁‍🗨 <b>Views:</b> {fmt(amount)}\n"
            f"🔗 <b>Link:</b> {link}",
            disable_web_page_preview=True,
        )
    except Exception as e:
        logger.error(f"Failed to notify channel: {e}")


@bot.callback_query_handler(func=lambda c: c.data == "cancel_order")
def cb_cancel_order(call):
    bot.answer_callback_query(call.id, "Order cancelled.")
    bot.edit_message_text(
        "❌ Order cancelled.",
        call.message.chat.id, call.message.message_id,
    )


# ══════════════════════════════════════════════════════
#  DEPOSIT SYSTEM (bKash / Nagad / Binance BEP20)
# ══════════════════════════════════════════════════════

@bot.message_handler(func=lambda m: m.text == "💰 Deposit")
def menu_deposit(message):
    ensure_registered(message)
    show_deposit_methods(message.chat.id)


@bot.callback_query_handler(func=lambda c: c.data == "deposit_start")
def cb_deposit_start(call):
    bot.answer_callback_query(call.id)
    show_deposit_methods(call.message.chat.id)


def show_deposit_methods(chat_id):
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("🟪 bKash (Send Money)", callback_data="dep_method:bkash"),
        InlineKeyboardButton("🟧 Nagad (Send Money)", callback_data="dep_method:nagad"),
        InlineKeyboardButton("🟡 Binance USDT (BEP20)", callback_data="dep_method:binance"),
    )
    markup.add(InlineKeyboardButton("📜 My Deposits", callback_data="my_deposits"))

    bot.send_message(
        chat_id,
        f"<b>━━━━ 💰 Deposit ━━━━</b>\n\n"
        f"Choose your payment method:\n\n"
        f"🟪 <b>bKash</b> — Send Money (BDT)\n"
        f"🟧 <b>Nagad</b> — Send Money (BDT)\n"
        f"🟡 <b>Binance</b> — USDT via BEP20 Network\n\n"
        f"<i>After payment, submit your Transaction ID for verification.</i>",
        reply_markup=markup,
    )


@bot.callback_query_handler(func=lambda c: c.data.startswith("dep_method:"))
def cb_deposit_method(call):
    method = call.data.split(":")[1]
    bot.answer_callback_query(call.id)

    markup = InlineKeyboardMarkup(row_width=1)
    for pkg in DEPOSIT_PACKAGES:
        if method == "binance":
            price_text = f"${pkg['price_usd']} USDT"
        else:
            price_text = f"৳{fmt(pkg['price_bdt'])}"
        markup.add(InlineKeyboardButton(
            f"{pkg['label']} — {price_text}",
            callback_data=f"dep_pkg:{method}:{pkg['id']}",
        ))
    markup.add(InlineKeyboardButton("◀️ Back", callback_data="deposit_start"))

    method_name = {"bkash": "🟪 bKash", "nagad": "🟧 Nagad", "binance": "🟡 Binance USDT"}
    bot.edit_message_text(
        f"<b>{method_name[method]} — Select Package</b>\n\n"
        f"Choose a views package below:",
        call.message.chat.id, call.message.message_id,
        reply_markup=markup,
    )


@bot.callback_query_handler(func=lambda c: c.data.startswith("dep_pkg:"))
def cb_deposit_package(call):
    _, method, pkg_id_str = call.data.split(":")
    pkg_id = int(pkg_id_str)
    pkg = next((p for p in DEPOSIT_PACKAGES if p["id"] == pkg_id), None)
    if not pkg:
        bot.answer_callback_query(call.id, "❌ Invalid package!", show_alert=True)
        return

    bot.answer_callback_query(call.id)
    user_id = call.from_user.id

    if method == "bkash":
        payment_info = (
            f"🟪 <b>bKash Payment Details</b>\n\n"
            f"📱 <b>Send Money to:</b> <code>{BKASH_NUMBER}</code>\n"
            f"💵 <b>Amount:</b> <code>৳{fmt(pkg['price_bdt'])}</code>\n\n"
            f"⚠️ <b>Important:</b>\n"
            f"• Use <b>Send Money</b> option only\n"
            f"• Send the <b>exact amount</b> shown above\n"
            f"• After sending, copy the <b>TrxID</b> from bKash"
        )
    elif method == "nagad":
        payment_info = (
            f"🟧 <b>Nagad Payment Details</b>\n\n"
            f"📱 <b>Send Money to:</b> <code>{NAGAD_NUMBER}</code>\n"
            f"💵 <b>Amount:</b> <code>৳{fmt(pkg['price_bdt'])}</code>\n\n"
            f"⚠️ <b>Important:</b>\n"
            f"• Use <b>Send Money</b> option only\n"
            f"• Send the <b>exact amount</b> shown above\n"
            f"• After sending, copy the <b>TrxID</b> from Nagad"
        )
    else:  # binance
        payment_info = (
            f"🟡 <b>Binance USDT (BEP20) Payment Details</b>\n\n"
            f"📋 <b>Wallet Address (BEP20):</b>\n<code>{BINANCE_BEP20_ADDRESS}</code>\n\n"
            f"💵 <b>Amount:</b> <code>{pkg['price_usd']} USDT</code>\n"
            f"🔗 <b>Network:</b> BSC (BEP20)\n\n"
            f"⚠️ <b>Important:</b>\n"
            f"• Send via <b>BEP20 (BSC)</b> network only\n"
            f"• Send the <b>exact amount</b> shown above\n"
            f"• After sending, copy the <b>Transaction Hash (TxID)</b>"
        )

    user_state[user_id] = {
        "step": "deposit_trxid",
        "data": {
            "method": method,
            "package": pkg,
        },
    }

    bot.edit_message_text(
        f"{payment_info}\n\n"
        f"<b>📦 Package:</b> {fmt(pkg['views'])} views\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"✏️ <b>Now send your Transaction ID (TrxID) as a message below:</b>",
        call.message.chat.id, call.message.message_id,
    )

    bot.send_message(
        user_id,
        "⬇️ <b>Send your Transaction ID / TxHash now:</b>",
        reply_markup=cancel_markup(),
    )


@bot.message_handler(func=lambda m: user_state.get(m.from_user.id, {}).get("step") == "deposit_trxid")
def step_deposit_trxid(message):
    user_id = message.from_user.id
    uid = str(user_id)
    trx_id = message.text.strip()

    if trx_id == "✘ Cancel":
        handle_cancel(message)
        return

    if len(trx_id) < 5:
        bot.reply_to(message, "❌ Transaction ID is too short. Please enter a valid TrxID.")
        return

    state = user_state[user_id]["data"]
    method = state["method"]
    pkg = state["package"]

    deposit_id = create_deposit(
        user_id=uid,
        method=method,
        package_id=pkg["id"],
        views=pkg["views"],
        amount_bdt=pkg["price_bdt"],
        amount_usd=pkg["price_usd"],
        trx_id=trx_id,
    )

    clear_state(user_id)

    method_names = {"bkash": "bKash", "nagad": "Nagad", "binance": "Binance USDT (BEP20)"}

    bot.send_message(
        user_id,
        f"<b>━━━━ ✅ Deposit Submitted ━━━━</b>\n\n"
        f"📋 <b>Deposit ID:</b> <code>#{deposit_id}</code>\n"
        f"💳 <b>Method:</b> {method_names[method]}\n"
        f"📦 <b>Package:</b> {fmt(pkg['views'])} views\n"
        f"💵 <b>Amount:</b> {'$' + str(pkg['price_usd']) + ' USDT' if method == 'binance' else '৳' + fmt(pkg['price_bdt'])}\n"
        f"🧾 <b>TrxID:</b> <code>{trx_id}</code>\n\n"
        f"⏳ <b>Status:</b> Pending admin verification\n"
        f"<i>You will be notified once your deposit is processed.</i>",
        reply_markup=main_menu_markup(),
    )

    admin_markup = InlineKeyboardMarkup(row_width=2)
    admin_markup.add(
        InlineKeyboardButton("✅ Approve", callback_data=f"adm_approve:{deposit_id}"),
        InlineKeyboardButton("❌ Reject", callback_data=f"adm_reject:{deposit_id}"),
    )

    try:
        bot.send_message(
            ADMIN_USER_ID,
            f"<b>━━━━ 🔔 New Deposit Request ━━━━</b>\n\n"
            f"📋 <b>Deposit ID:</b> <code>#{deposit_id}</code>\n"
            f"👤 <b>User:</b> {message.from_user.first_name} "
            f"(@{message.from_user.username or 'N/A'})\n"
            f"🆔 <b>User ID:</b> <code>{uid}</code>\n"
            f"💳 <b>Method:</b> {method_names[method]}\n"
            f"📦 <b>Package:</b> {fmt(pkg['views'])} views\n"
            f"💵 <b>Amount:</b> {'$' + str(pkg['price_usd']) + ' USDT' if method == 'binance' else '৳' + fmt(pkg['price_bdt'])}\n"
            f"🧾 <b>TrxID:</b> <code>{trx_id}</code>",
            reply_markup=admin_markup,
        )
    except Exception as e:
        logger.error(f"Failed to notify admin: {e}")


# ── Admin: Approve / Reject Deposit ───────────────────

@bot.callback_query_handler(func=lambda c: c.data.startswith("adm_approve:"))
def cb_admin_approve(call):
    if call.from_user.id != ADMIN_USER_ID:
        bot.answer_callback_query(call.id, "⛔ Admin only!", show_alert=True)
        return

    deposit_id = int(call.data.split(":")[1])
    deposit = approve_deposit(deposit_id)

    if not deposit:
        bot.answer_callback_query(call.id, "⚠️ Already processed!", show_alert=True)
        return

    bot.answer_callback_query(call.id, "✅ Deposit approved!")

    bot.edit_message_text(
        call.message.text + "\n\n✅ <b>APPROVED</b> by admin",
        call.message.chat.id, call.message.message_id,
        parse_mode="HTML",
    )

    try:
        bot.send_message(
            int(deposit["user_id"]),
            f"<b>━━━━ ✅ Deposit Approved ━━━━</b>\n\n"
            f"📋 <b>Deposit ID:</b> <code>#{deposit_id}</code>\n"
            f"👁‍🗨 <b>+{fmt(deposit['views'])} views</b> added to your balance!\n\n"
            f"🎉 Thank you! You can now order views.",
        )
    except Exception as e:
        logger.error(f"Failed to notify user: {e}")


@bot.callback_query_handler(func=lambda c: c.data.startswith("adm_reject:"))
def cb_admin_reject(call):
    if call.from_user.id != ADMIN_USER_ID:
        bot.answer_callback_query(call.id, "⛔ Admin only!", show_alert=True)
        return

    deposit_id = int(call.data.split(":")[1])
    deposit = reject_deposit(deposit_id, admin_note="Rejected by admin")

    if not deposit:
        bot.answer_callback_query(call.id, "⚠️ Already processed!", show_alert=True)
        return

    bot.answer_callback_query(call.id, "❌ Deposit rejected.")

    bot.edit_message_text(
        call.message.text + "\n\n❌ <b>REJECTED</b> by admin",
        call.message.chat.id, call.message.message_id,
        parse_mode="HTML",
    )

    try:
        bot.send_message(
            int(deposit["user_id"]),
            f"<b>━━━━ ❌ Deposit Rejected ━━━━</b>\n\n"
            f"📋 <b>Deposit ID:</b> <code>#{deposit_id}</code>\n\n"
            f"Your deposit was not approved. This could be due to:\n"
            f"• Invalid or incorrect Transaction ID\n"
            f"• Payment amount mismatch\n\n"
            f"📩 Contact {ADMIN_USERNAME} if you believe this is a mistake.",
        )
    except Exception as e:
        logger.error(f"Failed to notify user: {e}")


# ── My Deposits ───────────────────────────────────────

@bot.callback_query_handler(func=lambda c: c.data == "my_deposits")
def cb_my_deposits(call):
    uid = str(call.from_user.id)
    deposits = get_user_deposits(uid, limit=10)
    bot.answer_callback_query(call.id)

    if not deposits:
        bot.send_message(
            call.message.chat.id,
            "📭 You have no deposit history yet.",
        )
        return

    status_icons = {"pending": "⏳", "approved": "✅", "rejected": "❌"}
    method_names = {"bkash": "bKash", "nagad": "Nagad", "binance": "Binance"}

    lines = []
    for dep in deposits:
        icon = status_icons.get(dep["status"], "❓")
        method_name = method_names.get(dep["method"], dep["method"])
        lines.append(
            f"{icon} <b>#{dep['deposit_id']}</b> | "
            f"{method_name} | "
            f"{fmt(dep['views'])} views | "
            f"{dep['status'].upper()}"
        )

    bot.send_message(
        call.message.chat.id,
        f"<b>━━━━ 📜 My Deposits (Last 10) ━━━━</b>\n\n"
        + "\n".join(lines),
    )


# ══════════════════════════════════════════════════════
#  ADMIN COMMANDS
# ══════════════════════════════════════════════════════

@bot.message_handler(commands=["admin"])
def cmd_admin(message):
    if message.from_user.id != ADMIN_USER_ID:
        return

    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("📊 Statistics", callback_data="adm_stats"),
        InlineKeyboardButton("⏳ Pending Deposits", callback_data="adm_pending"),
        InlineKeyboardButton("📢 Broadcast", callback_data="adm_broadcast_start"),
        InlineKeyboardButton("💰 Add Balance", callback_data="adm_addbal_start"),
    )

    bot.reply_to(
        message,
        "<b>━━━━ 🔐 Admin Panel ━━━━</b>\n\n"
        "Choose an action:",
        reply_markup=markup,
    )


@bot.callback_query_handler(func=lambda c: c.data == "adm_stats")
def cb_admin_stats(call):
    if call.from_user.id != ADMIN_USER_ID:
        return
    bot.answer_callback_query(call.id)

    total_users = get_user_count()
    dep_stats = get_total_deposits_stats()
    order_stats = get_total_orders_stats()

    bot.send_message(
        call.message.chat.id,
        f"<b>━━━━ 📊 Bot Statistics ━━━━</b>\n\n"
        f"👥 <b>Total Users:</b> {fmt(total_users)}\n\n"
        f"<b>💰 Deposits:</b>\n"
        f"  • Total: {dep_stats['total']}\n"
        f"  • Approved: {dep_stats['approved']}\n"
        f"  • Pending: {dep_stats['pending']}\n"
        f"  • Rejected: {dep_stats['rejected']}\n"
        f"  • Total BDT: ৳{fmt(dep_stats['total_bdt'] or 0)}\n"
        f"  • Total USD: ${dep_stats['total_usd'] or 0}\n\n"
        f"<b>📦 Orders:</b>\n"
        f"  • Total: {order_stats['total']}\n"
        f"  • Total Views: {fmt(order_stats['total_views'] or 0)}",
    )


@bot.callback_query_handler(func=lambda c: c.data == "adm_pending")
def cb_admin_pending(call):
    if call.from_user.id != ADMIN_USER_ID:
        return
    bot.answer_callback_query(call.id)

    pending = get_pending_deposits()
    if not pending:
        bot.send_message(call.message.chat.id, "✅ No pending deposits!")
        return

    for dep in pending[:20]:
        user = get_user(dep["user_id"])
        username = user["username"] if user else "Unknown"
        method_names = {"bkash": "bKash", "nagad": "Nagad", "binance": "Binance"}

        admin_markup = InlineKeyboardMarkup(row_width=2)
        admin_markup.add(
            InlineKeyboardButton("✅ Approve", callback_data=f"adm_approve:{dep['deposit_id']}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"adm_reject:{dep['deposit_id']}"),
        )

        bot.send_message(
            call.message.chat.id,
            f"⏳ <b>Deposit #{dep['deposit_id']}</b>\n"
            f"👤 @{username} (ID: <code>{dep['user_id']}</code>)\n"
            f"💳 {method_names.get(dep['method'], dep['method'])}\n"
            f"📦 {fmt(dep['views'])} views\n"
            f"💵 {'$' + str(dep['amount_usd']) if dep['method'] == 'binance' else '৳' + fmt(dep['amount_bdt'])}\n"
            f"🧾 TrxID: <code>{dep['trx_id']}</code>",
            reply_markup=admin_markup,
        )


# ── Admin: Broadcast ──────────────────────────────────

@bot.callback_query_handler(func=lambda c: c.data == "adm_broadcast_start")
def cb_admin_broadcast_start(call):
    if call.from_user.id != ADMIN_USER_ID:
        return
    bot.answer_callback_query(call.id)
    user_state[call.from_user.id] = {"step": "admin_broadcast", "data": {}}
    bot.send_message(
        call.message.chat.id,
        "📢 <b>Broadcast</b>\n\nSend the message you want to broadcast to all users:",
        reply_markup=cancel_markup(),
    )


@bot.message_handler(func=lambda m: user_state.get(m.from_user.id, {}).get("step") == "admin_broadcast")
def step_admin_broadcast(message):
    if message.from_user.id != ADMIN_USER_ID:
        return

    if message.text == "✘ Cancel":
        handle_cancel(message)
        return

    clear_state(message.from_user.id)
    broadcast_text = message.text
    user_ids = get_all_user_ids()
    success, failed = 0, 0

    bot.reply_to(message, f"📢 Broadcasting to {len(user_ids)} users...",
                 reply_markup=main_menu_markup())

    for uid in user_ids:
        try:
            bot.send_message(int(uid), broadcast_text, parse_mode="HTML")
            success += 1
        except Exception:
            failed += 1

    bot.send_message(
        message.chat.id,
        f"📢 <b>Broadcast Complete</b>\n\n"
        f"✅ Sent: {success}\n❌ Failed: {failed}",
    )


# ── Admin: Add Balance ────────────────────────────────

@bot.callback_query_handler(func=lambda c: c.data == "adm_addbal_start")
def cb_admin_addbal_start(call):
    if call.from_user.id != ADMIN_USER_ID:
        return
    bot.answer_callback_query(call.id)
    user_state[call.from_user.id] = {"step": "admin_addbal", "data": {}}
    bot.send_message(
        call.message.chat.id,
        "💰 <b>Add Balance</b>\n\n"
        "Send in format: <code>USER_ID AMOUNT</code>\n"
        "Example: <code>123456789 5000</code>",
        reply_markup=cancel_markup(),
    )


@bot.message_handler(func=lambda m: user_state.get(m.from_user.id, {}).get("step") == "admin_addbal")
def step_admin_addbal(message):
    if message.from_user.id != ADMIN_USER_ID:
        return

    if message.text == "✘ Cancel":
        handle_cancel(message)
        return

    parts = message.text.strip().split()
    if len(parts) != 2:
        bot.reply_to(message, "❌ Invalid format. Use: <code>USER_ID AMOUNT</code>")
        return

    target_uid, amount_str = parts
    if not amount_str.isdigit():
        bot.reply_to(message, "❌ Amount must be a number.")
        return

    if not user_exists(target_uid):
        bot.reply_to(message, "❌ User not found.")
        return

    amount = int(amount_str)
    add_balance(target_uid, amount)
    clear_state(message.from_user.id)

    bot.reply_to(
        message,
        f"✅ Added <b>{fmt(amount)}</b> views to user <code>{target_uid}</code>",
        reply_markup=main_menu_markup(),
    )

    try:
        bot.send_message(
            int(target_uid),
            f"🎉 <b>+{fmt(amount)} views</b> added to your balance by admin!",
        )
    except Exception:
        pass


# ── Admin Quick Commands ──────────────────────────────

@bot.message_handler(commands=["ban"])
def cmd_ban(message):
    if message.from_user.id != ADMIN_USER_ID:
        return
    parts = message.text.split()
    if len(parts) != 2:
        bot.reply_to(message, "Usage: /ban USER_ID")
        return
    target = parts[1]
    if user_exists(target):
        ban_user(target)
        bot.reply_to(message, f"🚫 User <code>{target}</code> has been banned.")
    else:
        bot.reply_to(message, "❌ User not found.")


@bot.message_handler(commands=["unban"])
def cmd_unban(message):
    if message.from_user.id != ADMIN_USER_ID:
        return
    parts = message.text.split()
    if len(parts) != 2:
        bot.reply_to(message, "Usage: /unban USER_ID")
        return
    target = parts[1]
    if user_exists(target):
        unban_user(target)
        bot.reply_to(message, f"✅ User <code>{target}</code> has been unbanned.")
    else:
        bot.reply_to(message, "❌ User not found.")


# ══════════════════════════════════════════════════════
#  CATCH-ALL
# ══════════════════════════════════════════════════════

@bot.message_handler(func=lambda m: True, content_types=["text"])
def handle_unknown(message):
    if message.from_user.id not in user_state:
        bot.reply_to(
            message,
            "🤖 Please use the menu buttons below to navigate.",
            reply_markup=main_menu_markup(),
        )


# ══════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════

if __name__ == "__main__":
    init_database()
    logger.info("🤖 Bot is starting...")

    while True:
        try:
            logger.info("✅ Bot is running! Polling...")
            bot.infinity_polling(timeout=60, long_polling_timeout=60)
        except Exception as e:
            logger.error(f"Bot polling failed: {e}")
            try:
                bot.send_message(ADMIN_USER_ID, f"⚠️ Bot error: {e}")
            except Exception:
                pass
            time.sleep(10)