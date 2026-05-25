"""
╔══════════════════════════════════════════════════════════╗
║           ربات هم‌فاز — نسخه نهایی بازنویسی شده        ║
╚══════════════════════════════════════════════════════════╝
"""

import sqlite3
import logging
import csv
import os
import asyncio
from datetime import datetime, timedelta

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
    ChatMember
)
from telegram.constants import ParseMode
from telegram.error import NetworkError, TimedOut
from telegram.ext import (
    ApplicationBuilder, ContextTypes, CommandHandler,
    MessageHandler, CallbackQueryHandler, ConversationHandler, filters
)

# ══════════════════════════════════════════════════════════
#  ۱. تنظیمات — فقط این بخش رو ویرایش کن
# ══════════════════════════════════════════════════════════
TOKEN     = '8360983813:AAGTx7aI4rW-CSbZN6_epxnevFEEG3Ruc8c'
ADMIN_ID  = 1617627229
DB_PATH   = 'hamfaz.db'

# Channel Lock — برای غیرفعال کردن: None بذار
FORCE_JOIN_CHANNEL = None  # مثال: '@hamfaz_official'

# تعداد ریپورت برای بن خودکار
AUTO_BAN_THRESHOLD = 3

AD_TEXT = (
    "📢 <b>اسپانسر ربات هم‌فاز:</b>\n\n"
    "🎲 <b>بهترین سایت تخته نرد آنلاین</b>\n"
    "💰 هم سرگرمی، هم درآمد!\n\n"
    "🏆 همین الان با حرفه‌ای‌ها بازی کن:\n"
    "🌐 <b>https://Tajgammon.com</b>"
)

# ══════════════════════════════════════════════════════════
#  ۲. ترجمه‌ها
# ══════════════════════════════════════════════════════════
TRANS = {
    "Male": "پسر 👦", "Female": "دختر 👧",
    "-18": "زیر ۱۸ سال 🍼", "18-25": "۱۸ تا ۲۵ سال 🧑‍🎓",
    "25-35": "۲۵ تا ۳۵ سال 👨‍💼", "+35": "بالای ۳۵ سال 👴",
    "Tehran": "تهران/کرج 🏙", "City": "مراکز استان 🏢",
    "Other": "سایر شهرها 🏡", "Abroad": "خارج از ایران 🌍",
    "Single": "سینگل 🦅", "InRel": "توی رابطه ❤️",
    "Married": "متاهل 💍", "Complicated": "پیچیده 🌀",
    "Game": "گیم و تکنولوژی 🎮", "Movie": "فیلم و سریال 🎬",
    "Art": "هنر و موزیک 🎨", "Tech": "برنامه‌نویسی 💻",
    "Sport": "ورزش ⚽️", "Trade": "بیزنس و ترید 💸",
    "Rap": "رپ و هیپ‌هاپ 🤘", "Pop": "پاپ و سنتی 🎻",
    "Rock": "راک و متال 🎸", "Electro": "الکترونیک 🎧",
    "Extrovert": "برونگرا 🗣", "Introvert": "درونگرا 🧘",
    "Logical": "منطقی 🧠", "Emotional": "احساسی ❤️",
    "Vac_Cafe": "کافه و بام تهران ☕️", "Vac_Shomal": "ویلای شمال 🌲",
    "Vac_Dubai": "سفر دبی/ترکیه ✈️", "Vac_Home": "گیم تو خونه 🎮",
    "Phone_Apple": "فقط اپل 🍏", "Phone_Android": "اندروید 🤖",
    "Phone_None": "فرقی نداره 🤷"
}

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════
#  ۳. استیت‌های مکالمه
# ══════════════════════════════════════════════════════════
(
    S_WELCOME, S_GENDER, S_AGE, S_LOCATION, S_STATUS,
    S_INTEREST, S_MUSIC, S_PERSONALITY, S_VACATION, S_PHONE,
    S_ANON_MSG,
    S_VIP_GENDER, S_VIP_LOCATION,
    S_BC_GENDER, S_BC_AGE, S_BC_MSG
) = range(16)

# ══════════════════════════════════════════════════════════
#  ۴. حافظه مشترک
# ══════════════════════════════════════════════════════════
_lock           = asyncio.Lock()
waiting_queue   = []   # [user_id]
vip_queue       = []   # [(user_id, gender_filter, location_filter)]
connected_pairs = {}   # {user_id: partner_id}
last_partner    = {}   # {user_id: partner_id}
spam_tracker    = {}   # {user_id: [timestamps]}
pending_karma   = {}   # {voter_id: target_id}

# ══════════════════════════════════════════════════════════
#  ۵. دیتابیس
# ══════════════════════════════════════════════════════════
def db():
    return sqlite3.connect(DB_PATH)

def init_db():
    with db() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id     INTEGER PRIMARY KEY,
                username    TEXT    DEFAULT '',
                gender      TEXT    DEFAULT '',
                age         TEXT    DEFAULT '',
                location    TEXT    DEFAULT '',
                status      TEXT    DEFAULT '',
                interest    TEXT    DEFAULT '',
                music       TEXT    DEFAULT '',
                personality TEXT    DEFAULT '',
                vacation    TEXT    DEFAULT '',
                phone       TEXT    DEFAULT '',
                coins       INTEGER DEFAULT 0,
                invites     INTEGER DEFAULT 0,
                karma       INTEGER DEFAULT 0,
                reports     INTEGER DEFAULT 0,
                is_banned   INTEGER DEFAULT 0,
                joined_at   TEXT    DEFAULT (datetime('now'))
            )
        ''')
        conn.commit()

def user_exists(uid):
    with db() as conn:
        r = conn.execute(
            "SELECT 1 FROM users WHERE user_id=? AND is_banned=0", (uid,)
        ).fetchone()
    return r is not None

def is_banned(uid):
    with db() as conn:
        r = conn.execute(
            "SELECT is_banned FROM users WHERE user_id=?", (uid,)
        ).fetchone()
    return r and r[0] == 1

def get_user(uid):
    with db() as conn:
        conn.row_factory = sqlite3.Row
        r = conn.execute("SELECT * FROM users WHERE user_id=?", (uid,)).fetchone()
    return dict(r) if r else None

def save_user(uid, username, data):
    with db() as conn:
        old = conn.execute(
            "SELECT coins, invites, karma FROM users WHERE user_id=?", (uid,)
        ).fetchone()
        coins   = old[0] if old else 0
        invites = old[1] if old else 0
        karma   = old[2] if old else 0
        conn.execute("""
            INSERT OR REPLACE INTO users
                (user_id, username, gender, age, location, status,
                 interest, music, personality, vacation, phone,
                 coins, invites, karma, reports, is_banned)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,0,0)
        """, (
            uid, username,
            data.get('gender',''), data.get('age',''),
            data.get('location',''), data.get('status',''),
            data.get('interest',''), data.get('music',''),
            data.get('personality',''), data.get('vacation',''),
            data.get('phone',''),
            coins, invites, karma
        ))
        conn.commit()

def add_coins(uid, amount):
    with db() as conn:
        conn.execute(
            "UPDATE users SET coins=coins+?, invites=invites+1 WHERE user_id=?",
            (amount, uid)
        )
        conn.commit()

def deduct_coins(uid, amount):
    with db() as conn:
        conn.execute(
            "UPDATE users SET coins=coins-? WHERE user_id=?", (amount, uid)
        )
        conn.commit()

def get_coins(uid):
    with db() as conn:
        r = conn.execute(
            "SELECT coins FROM users WHERE user_id=?", (uid,)
        ).fetchone()
    return r[0] if r else 0

def add_karma(uid, delta):
    with db() as conn:
        conn.execute(
            "UPDATE users SET karma=karma+? WHERE user_id=?", (delta, uid)
        )
        conn.commit()

def add_report(uid):
    """ریپورت اضافه می‌کنه — اگه به حد رسید True برمیگردونه"""
    with db() as conn:
        conn.execute(
            "UPDATE users SET reports=reports+1 WHERE user_id=?", (uid,)
        )
        r = conn.execute(
            "SELECT reports FROM users WHERE user_id=?", (uid,)
        ).fetchone()
        banned = False
        if r and r[0] >= AUTO_BAN_THRESHOLD:
            conn.execute(
                "UPDATE users SET is_banned=1 WHERE user_id=?", (uid,)
            )
            banned = True
        conn.commit()
    return banned

def set_ban(uid, val):
    with db() as conn:
        conn.execute(
            "UPDATE users SET is_banned=?, reports=0 WHERE user_id=?", (val, uid)
        )
        conn.commit()

def get_stats():
    with db() as conn:
        total   = conn.execute("SELECT COUNT(*) FROM users WHERE is_banned=0").fetchone()[0]
        males   = conn.execute("SELECT COUNT(*) FROM users WHERE gender='Male' AND is_banned=0").fetchone()[0]
        females = conn.execute("SELECT COUNT(*) FROM users WHERE gender='Female' AND is_banned=0").fetchone()[0]
        today   = conn.execute(
            "SELECT COUNT(*) FROM users WHERE joined_at>=datetime('now','-1 day') AND is_banned=0"
        ).fetchone()[0]
        banned  = conn.execute("SELECT COUNT(*) FROM users WHERE is_banned=1").fetchone()[0]
        top3    = conn.execute(
            "SELECT interest, COUNT(*) c FROM users WHERE is_banned=0 GROUP BY interest ORDER BY c DESC LIMIT 3"
        ).fetchall()
    return total, males, females, today, banned, top3

def get_filtered_users(gender=None, age=None):
    q = "SELECT user_id FROM users WHERE is_banned=0"
    p = []
    if gender and gender != 'all':
        q += " AND gender=?"; p.append(gender)
    if age and age != 'all':
        q += " AND age=?";    p.append(age)
    with db() as conn:
        rows = conn.execute(q, p).fetchall()
    return [r[0] for r in rows]

# ══════════════════════════════════════════════════════════
#  ۶. ابزارهای کمکی
# ══════════════════════════════════════════════════════════
def is_spamming(uid, limit=10, window=60):
    now    = datetime.now()
    cutoff = now - timedelta(seconds=window)
    times  = [t for t in spam_tracker.get(uid, []) if t > cutoff]
    spam_tracker[uid] = times
    if len(times) >= limit:
        return True
    spam_tracker[uid].append(now)
    return False

async def safe_send(bot, chat_id, text, **kwargs):
    """ارسال پیام با مقاومت در برابر خطاهای شبکه"""
    for attempt in range(3):
        try:
            return await bot.send_message(chat_id=chat_id, text=text, **kwargs)
        except (NetworkError, TimedOut):
            if attempt < 2:
                await asyncio.sleep(1)
        except Exception as e:
            logger.warning(f"safe_send error: {e}")
            break
    return None

async def check_member(uid, bot):
    if not FORCE_JOIN_CHANNEL:
        return True
    try:
        m = await bot.get_chat_member(FORCE_JOIN_CHANNEL, uid)
        return m.status in [ChatMember.MEMBER, ChatMember.ADMINISTRATOR, ChatMember.OWNER]
    except:
        return True

def profile_card(uid):
    """پروفایل کوتاه برای نمایش به طرف مقابل — بدون هیچ اطلاعات شناسایی"""
    u = get_user(uid)
    if not u:
        return "👤 اطلاعات موجود نیست."
    return (
        f"👤 <b>مشخصات هم‌فاز شما:</b>\n\n"
        f"🔸 جنسیت: {TRANS.get(u['gender'],'—')}\n"
        f"🔸 سن: {TRANS.get(u['age'],'—')}\n"
        f"🔸 شهر: {TRANS.get(u['location'],'—')}\n"
        f"🔸 وضعیت: {TRANS.get(u['status'],'—')}\n"
        f"🔸 علاقه: {TRANS.get(u['interest'],'—')}\n"
        f"🔸 موزیک: {TRANS.get(u['music'],'—')}\n"
        f"🔸 شخصیت: {TRANS.get(u['personality'],'—')}\n"
        f"⭐️ کارما: {u['karma']}"
    )

def my_dashboard(uid, bot_username):
    u = get_user(uid)
    if not u:
        return "❌ ابتدا ثبت‌نام کنید."
    ref_link  = f"https://t.me/{bot_username}?start=ref_{uid}"
    anon_link = f"https://t.me/{bot_username}?start=anon_{uid}"
    return (
        f"💳 <b>کارت شناسایی شما در هم‌فاز</b>\n\n"
        f"🔸 جنسیت: {TRANS.get(u['gender'],'')}\n"
        f"🔸 سن: {TRANS.get(u['age'],'')}\n"
        f"🔸 شهر: {TRANS.get(u['location'],'')}\n"
        f"🔸 وضعیت: {TRANS.get(u['status'],'')}\n"
        f"🔸 علاقه: {TRANS.get(u['interest'],'')}\n"
        f"🔸 موزیک: {TRANS.get(u['music'],'')}\n"
        f"🔸 شخصیت: {TRANS.get(u['personality'],'')}\n\n"
        f"📊 <b>آمار فعالیت:</b>\n"
        f"💰 سکه: <b>{u['coins']}</b>\n"
        f"👥 دعوت‌ها: <b>{u['invites']}</b> نفر\n"
        f"⭐️ کارما: <b>{u['karma']}</b>\n\n"
        f"🔗 <b>لینک دعوت (۵ سکه برای هر نفر):</b>\n"
        f"<code>{ref_link}</code>\n\n"
        f"🤫 <b>لینک پیام ناشناس (برای استوری):</b>\n"
        f"<code>{anon_link}</code>"
    )

def main_kb():
    return ReplyKeyboardMarkup([
        [KeyboardButton("➡️ نفر بعدی"),        KeyboardButton("❌ پایان مکالمه")],
        [KeyboardButton("💎 جستجوی VIP"),       KeyboardButton("⏪ ماشین زمان (۱۰ سکه)")],
        [KeyboardButton("👤 پروفایل من")]
    ], resize_keyboard=True)

# ══════════════════════════════════════════════════════════
#  ۷. موتور وصل کردن
# ══════════════════════════════════════════════════════════
async def do_disconnect(uid, bot, notify=True):
    """قطع اتصال ایمن"""
    partner = None
    async with _lock:
        partner = connected_pairs.pop(uid, None)
        if partner:
            connected_pairs.pop(partner, None)
            last_partner[uid]     = partner
            last_partner[partner] = uid
        # از صف‌ها خارج کن
        if uid in waiting_queue:
            waiting_queue.remove(uid)
        for item in list(vip_queue):
            if item[0] == uid:
                vip_queue.remove(item)
                break

    if partner and notify:
        await safe_send(bot, partner, "❌ طرف مقابل مکالمه رو قطع کرد.", reply_markup=main_kb())

    # سوال کارما به طرف مقابل
    if partner:
        pending_karma[partner] = uid
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("👍 خوب بود", callback_data=f"karma_up_{uid}"),
            InlineKeyboardButton("👎 بد بود",  callback_data=f"karma_dn_{uid}")
        ]])
        await safe_send(
            bot, partner,
            "⭐️ <b>چت تموم شد!</b>\nاین آدم چطور بود؟",
            reply_markup=kb,
            parse_mode=ParseMode.HTML
        )
    return partner

async def do_find_match(update, context, gender_f=None, location_f=None, is_vip=False):
    uid  = update.effective_user.id
    bot  = context.bot

    async def send(text, markup=None):
        try:
            if update.callback_query:
                await safe_send(bot, uid, text, reply_markup=markup, parse_mode=ParseMode.HTML)
            else:
                await update.message.reply_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)
        except:
            pass

    # چک کن در صف هست یا نه
    async with _lock:
        in_q = uid in waiting_queue or any(x[0] == uid for x in vip_queue)
    if in_q:
        await send("⏳ <b>شما در صف انتظار هستید!</b>", main_kb())
        return

    u_info  = get_user(uid)
    partner = None

    async with _lock:
        if is_vip:
            # جستجو در صف معمولی با فیلتر
            for candidate in list(waiting_queue):
                if candidate == uid:
                    continue
                ci = get_user(candidate)
                if not ci:
                    continue
                g_ok = (not gender_f)   or ci['gender']   == gender_f
                l_ok = (not location_f) or ci['location'] == location_f
                if g_ok and l_ok:
                    partner = candidate
                    waiting_queue.remove(candidate)
                    break
            # جستجو در صف VIP
            if not partner:
                for item in list(vip_queue):
                    cid, cgf, clf = item
                    if cid == uid:
                        continue
                    ci = get_user(cid)
                    if not ci:
                        continue
                    my_g = (not cgf) or u_info['gender']   == cgf
                    my_l = (not clf) or u_info['location'] == clf
                    th_g = (not gender_f)   or ci['gender']   == gender_f
                    th_l = (not location_f) or ci['location'] == location_f
                    if my_g and my_l and th_g and th_l:
                        partner = cid
                        vip_queue.remove(item)
                        break
        else:
            # صف معمولی — اولین نفر آزاد
            for candidate in list(waiting_queue):
                if candidate != uid:
                    partner = candidate
                    waiting_queue.remove(candidate)
                    break

        if partner:
            connected_pairs[uid]     = partner
            connected_pairs[partner] = uid

    if partner:
        badge = " 💎" if is_vip else ""
        p1 = profile_card(partner)
        p2 = profile_card(uid)
        await safe_send(bot, uid,
            f"😍 <b>هم‌فاز پیدا شد!{badge}</b>\n\n{p1}\n\n💬 <b>حالا سلام کن!</b>",
            reply_markup=main_kb(), parse_mode=ParseMode.HTML)
        await safe_send(bot, partner,
            f"😍 <b>هم‌فاز پیدا شد!{badge}</b>\n\n{p2}\n\n💬 <b>حالا سلام کن!</b>",
            reply_markup=main_kb(), parse_mode=ParseMode.HTML)
    else:
        async with _lock:
            if is_vip:
                vip_queue.append((uid, gender_f, location_f))
            else:
                if uid not in waiting_queue:
                    waiting_queue.append(uid)

        ftxt = ""
        if gender_f or location_f:
            parts = []
            if gender_f:   parts.append(TRANS.get(gender_f, gender_f))
            if location_f: parts.append(TRANS.get(location_f, location_f))
            ftxt = f"\n🔍 فیلتر: {' | '.join(parts)}"

        await send(f"🔍 <b>در حال جستجو...{ftxt}</b>\nمنتظر بمانید.", main_kb())

# ══════════════════════════════════════════════════════════
#  ۸. /start
# ══════════════════════════════════════════════════════════
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid  = update.effective_user.id
    args = context.args or []
    context.user_data.clear()

    if is_banned(uid):
        await update.message.reply_text("🚫 حساب شما به دلیل تخلف مسدود شده است.")
        return ConversationHandler.END

    # مسیر پیام ناشناس
    if args and args[0].startswith('anon_'):
        tid = args[0].split('_', 1)[1]
        context.user_data['anon_target'] = tid
        await update.message.reply_text(
            "✍️ <b>ارسال پیام ناشناس</b>\n\nپیامت رو بفرست (عکس، ویس، ویدیو هم قبوله):",
            reply_markup=ReplyKeyboardRemove(), parse_mode=ParseMode.HTML
        )
        return S_ANON_MSG

    # بررسی Channel Lock
    if not await check_member(uid, context.bot):
        channel = FORCE_JOIN_CHANNEL.lstrip('@')
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("📢 عضویت در کانال", url=f"https://t.me/{channel}"),
            InlineKeyboardButton("✅ عضو شدم!", callback_data="check_join")
        ]])
        await update.message.reply_text(
            "🔒 <b>برای استفاده از هم‌فاز باید عضو کانال اسپانسر بشی!</b>\n\n"
            "بعد از عضویت روی «✅ عضو شدم!» بزن.",
            reply_markup=kb, parse_mode=ParseMode.HTML
        )
        return ConversationHandler.END

    # ذخیره ریفرال
    if args and args[0].startswith('ref_'):
        context.user_data['inviter'] = args[0].split('_', 1)[1]

    # کاربر قبلاً ثبت‌نام کرده
    if user_exists(uid):
        await update.message.reply_text("👋 خوش برگشتی!", reply_markup=main_kb())
        await do_find_match(update, context)
        return ConversationHandler.END

    # کاربر جدید — شروع ثبت‌نام
    await update.message.reply_text("⏳", reply_markup=ReplyKeyboardRemove())
    await update.message.reply_text(
        "👋 <b>به ربات هم‌فاز خوش اومدی!</b>\n\n"
        "اینجا تو رو دقیقاً به کسی وصل می‌کنیم که <b>هم‌فرکانس</b> خودته! 🎯\n\n"
        "آماده‌ای؟",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🚀 بزن بریم!", callback_data="go")
        ]]),
        parse_mode=ParseMode.HTML
    )
    return S_WELCOME

# ══════════════════════════════════════════════════════════
#  ۹. پیام ناشناس
# ══════════════════════════════════════════════════════════
async def handle_anon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    tid = context.user_data.get('anon_target')

    if not tid:
        await update.message.reply_text("❌ خطا، دوباره روی لینک کلیک کنید.")
        return ConversationHandler.END

    try:
        await context.bot.send_message(
            int(tid), "📩 <b>یه پیام ناشناس جدید داری! 👇</b>",
            parse_mode=ParseMode.HTML
        )
        await context.bot.copy_message(chat_id=int(tid), from_chat_id=uid, message_id=update.message.message_id)
    except Exception as e:
        logger.warning(f"anon send: {e}")

    context.user_data.pop('anon_target', None)

    if user_exists(uid):
        await update.message.reply_text("✅ پیامت ناشناس ارسال شد!", reply_markup=main_kb())
        await do_find_match(update, context)
        return ConversationHandler.END
    else:
        await update.message.reply_text(
            "✅ <b>پیامت با موفقیت ارسال شد!</b>\n\n"
            "💡 می‌خوای با آدمایی چت کنی که دقیقاً مثل خودتن؟",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🚀 بزن بریم!", callback_data="go")
            ]]),
            parse_mode=ParseMode.HTML
        )
        return S_WELCOME

# ══════════════════════════════════════════════════════════
#  ۱۰. مراحل ثبت‌نام
# ══════════════════════════════════════════════════════════
def mkb(*rows):
    """ساخت InlineKeyboard از لیست (text, data) ها"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(TRANS.get(d, d), callback_data=d) for d in row]
        for row in rows
    ])

async def q_gender(u, c):
    q = u.callback_query; await q.answer()
    await q.edit_message_text(
        "1️⃣ <b>جنسیتت چیه؟</b>",
        reply_markup=mkb(["Male", "Female"]),
        parse_mode=ParseMode.HTML
    )
    return S_GENDER

async def q_age(u, c):
    q = u.callback_query; await q.answer()
    c.user_data['gender'] = q.data
    await q.edit_message_text(
        "2️⃣ <b>چند سالته؟</b>",
        reply_markup=mkb(["-18", "18-25"], ["25-35", "+35"]),
        parse_mode=ParseMode.HTML
    )
    return S_AGE

async def q_location(u, c):
    q = u.callback_query; await q.answer()
    c.user_data['age'] = q.data
    await q.edit_message_text(
        "3️⃣ <b>کجا زندگی می‌کنی؟</b>",
        reply_markup=mkb(["Tehran", "City"], ["Other", "Abroad"]),
        parse_mode=ParseMode.HTML
    )
    return S_LOCATION

async def q_status(u, c):
    q = u.callback_query; await q.answer()
    c.user_data['location'] = q.data
    await q.edit_message_text(
        "4️⃣ <b>وضعیت تاهل؟</b>",
        reply_markup=mkb(["Single", "InRel"], ["Married", "Complicated"]),
        parse_mode=ParseMode.HTML
    )
    return S_STATUS

async def q_interest(u, c):
    q = u.callback_query; await q.answer()
    c.user_data['status'] = q.data
    await q.edit_message_text(
        "5️⃣ <b>علاقه اصلیت چیه؟</b>",
        reply_markup=mkb(["Game", "Movie"], ["Art", "Tech"], ["Sport", "Trade"]),
        parse_mode=ParseMode.HTML
    )
    return S_INTEREST

async def q_music(u, c):
    q = u.callback_query; await q.answer()
    c.user_data['interest'] = q.data
    await q.edit_message_text(
        "6️⃣ <b>سلیقه موزیکت؟</b>",
        reply_markup=mkb(["Rap", "Pop"], ["Rock", "Electro"]),
        parse_mode=ParseMode.HTML
    )
    return S_MUSIC

async def q_personality(u, c):
    q = u.callback_query; await q.answer()
    c.user_data['music'] = q.data
    await q.edit_message_text(
        "7️⃣ <b>تیپ شخصیتیت؟</b>",
        reply_markup=mkb(["Extrovert", "Introvert"], ["Logical", "Emotional"]),
        parse_mode=ParseMode.HTML
    )
    return S_PERSONALITY

async def q_vacation(u, c):
    q = u.callback_query; await q.answer()
    c.user_data['personality'] = q.data
    await q.edit_message_text(
        "8️⃣ <b>تعطیلات کجا باشی؟ ✈️</b>",
        reply_markup=mkb(["Vac_Cafe", "Vac_Shomal"], ["Vac_Dubai", "Vac_Home"]),
        parse_mode=ParseMode.HTML
    )
    return S_VACATION

async def q_phone(u, c):
    q = u.callback_query; await q.answer()
    c.user_data['vacation'] = q.data
    await q.edit_message_text(
        "9️⃣ <b>طرفدار کدوم برندی؟ 📱</b>",
        reply_markup=mkb(["Phone_Apple", "Phone_Android"], ["Phone_None"]),
        parse_mode=ParseMode.HTML
    )
    return S_PHONE

async def finish_reg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q   = update.callback_query
    uid = q.from_user.id
    await q.answer()

    context.user_data['phone'] = q.data
    username = f"@{q.from_user.username}" if q.from_user.username else "بدون_یوزرنیم"
    save_user(uid, username, context.user_data)

    # پاداش ریفرال — بدون نمایش هیچ اطلاعاتی از کاربر جدید
    inviter_raw = context.user_data.get('inviter')
    if inviter_raw:
        try:
            inviter = int(inviter_raw)
            if inviter != uid:
                add_coins(inviter, 5)
                await safe_send(
                    context.bot, inviter,
                    "🎉 <b>تبریک!</b>\nیک کاربر جدید با لینک دعوت شما ثبت‌نام کرد و <b>۵ سکه طلا</b> به حسابت اضافه شد! 💰",
                    parse_mode=ParseMode.HTML
                )
        except Exception as e:
            logger.warning(f"inviter reward: {e}")

    await q.edit_message_text(
        "✅ <b>پروفایل شما ساخته شد!</b>\n\n🔍 دارم برات هم‌فاز پیدا می‌کنم...",
        parse_mode=ParseMode.HTML
    )
    await do_find_match(update, context)
    return ConversationHandler.END

# ══════════════════════════════════════════════════════════
#  ۱۱. جستجوی VIP
# ══════════════════════════════════════════════════════════
async def vip_step1(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not user_exists(uid):
        await update.message.reply_text("⚠️ ابتدا /start بزن.")
        return
    if uid in connected_pairs:
        await update.message.reply_text("⚠️ اول مکالمه فعلی رو قطع کن.")
        return
    coins = get_coins(uid)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("👦 فقط پسر (۵ سکه)",    callback_data="vg_Male"),
         InlineKeyboardButton("👧 فقط دختر (۵ سکه)",   callback_data="vg_Female")],
        [InlineKeyboardButton("🔀 فرقی نمیکنه (رایگان)", callback_data="vg_any")]
    ])
    await update.message.reply_text(
        f"💎 <b>جستجوی VIP</b>\n💰 موجودی: {coins} سکه\n\nجنسیت طرف مقابل:",
        reply_markup=kb, parse_mode=ParseMode.HTML
    )
    return S_VIP_GENDER

async def vip_gender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    uid = q.from_user.id
    gf  = q.data.replace("vg_", "")
    if gf == "any": gf = None

    if gf and get_coins(uid) < 5:
        await q.edit_message_text(
            "💔 <b>سکه کافی نداری!</b>\nبرای فیلتر جنسیت ۵ سکه لازمه.\n\nدوستاتو دعوت کن تا سکه بگیری!",
            parse_mode=ParseMode.HTML
        )
        return ConversationHandler.END

    context.user_data['vip_g'] = gf
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🏙 تهران/کرج (+۵ سکه)",    callback_data="vl_Tehran"),
         InlineKeyboardButton("🏢 مراکز استان (+۵ سکه)",  callback_data="vl_City")],
        [InlineKeyboardButton("🏡 سایر شهرها (+۵ سکه)",   callback_data="vl_Other"),
         InlineKeyboardButton("🌍 خارج از ایران (+۵ سکه)", callback_data="vl_Abroad")],
        [InlineKeyboardButton("🔀 فرقی نمیکنه (رایگان)",   callback_data="vl_any")]
    ])
    await q.edit_message_text("💎 شهر طرف مقابل:", reply_markup=kb)
    return S_VIP_LOCATION

async def vip_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q   = update.callback_query; await q.answer()
    uid = q.from_user.id
    lf  = q.data.replace("vl_", "")
    if lf == "any": lf = None

    gf   = context.user_data.get('vip_g')
    cost = (5 if gf else 0) + (5 if lf else 0)

    if get_coins(uid) < cost:
        await q.edit_message_text(
            f"💔 <b>سکه کافی نداری!</b>\nهزینه: {cost} سکه | موجودی: {get_coins(uid)} سکه",
            parse_mode=ParseMode.HTML
        )
        return ConversationHandler.END

    if cost > 0:
        deduct_coins(uid, cost)

    badge = []
    if gf: badge.append(TRANS.get(gf, gf))
    if lf: badge.append(TRANS.get(lf, lf))

    await q.edit_message_text(
        f"💎 <b>جستجوی VIP شروع شد!</b>\n"
        f"{'🔸 ' + ' | '.join(badge) if badge else ''}\n"
        f"{'💰 ' + str(cost) + ' سکه کم شد.' if cost else 'رایگان!'}",
        parse_mode=ParseMode.HTML
    )
    await do_find_match(update, context, gf, lf, is_vip=True)
    return ConversationHandler.END

# ══════════════════════════════════════════════════════════
#  ۱۲. کارما و ریپورت
# ══════════════════════════════════════════════════════════
async def cb_karma(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q      = update.callback_query
    voter  = q.from_user.id
    await q.answer()

    parts     = q.data.split('_')   # karma_up_USERID یا karma_dn_USERID
    direction = parts[1]
    target    = int(parts[2])

    if pending_karma.get(voter) != target:
        await q.edit_message_text("⚠️ این امتیاز قبلاً ثبت شده.")
        return

    del pending_karma[voter]

    if direction == 'up':
        add_karma(target, 1)
        await q.edit_message_text("✅ امتیاز مثبت ثبت شد! ⭐️")
    else:
        add_karma(target, -1)
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("🚨 ریپورت تخلف", callback_data=f"report_{target}")
        ]])
        await q.edit_message_text("👎 امتیاز منفی ثبت شد.\nاگه تخلفی رخ داد ریپورت بده:", reply_markup=kb)

async def cb_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q      = update.callback_query
    await q.answer()
    target = int(q.data.split('_')[1])

    was_banned = add_report(target)
    if was_banned:
        await q.edit_message_text("✅ ریپورت ثبت شد. این کاربر به دلیل تخلف‌های مکرر مسدود شد.")
        async with _lock:
            if target in waiting_queue:
                waiting_queue.remove(target)
            p = connected_pairs.pop(target, None)
            if p:
                connected_pairs.pop(p, None)
        await safe_send(context.bot, target, "🚫 حساب شما به دلیل تخلف مسدود شد.")
        await safe_send(context.bot, ADMIN_ID, f"🚨 کاربر {target} به صورت خودکار بن شد (۳ ریپورت).")
    else:
        await q.edit_message_text("✅ ریپورت ثبت شد. ممنون که ربات رو امن‌تر کردی.")

async def cb_check_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q   = update.callback_query
    uid = q.from_user.id
    await q.answer()
    if await check_member(uid, context.bot):
        await q.edit_message_text("✅ عضویت تایید شد! دوباره /start بزن.")
    else:
        await q.answer("❌ هنوز عضو نشدی!", show_alert=True)

# ══════════════════════════════════════════════════════════
#  ۱۳. پنل ادمین
# ══════════════════════════════════════════════════════════
def admin_only(func):
    async def wrapper(update, context):
        if update.effective_user.id != ADMIN_ID:
            return
        return await func(update, context)
    return wrapper

@admin_only
async def cmd_export(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ در حال استخراج...")
    with db() as conn:
        rows    = conn.execute("SELECT * FROM users").fetchall()
        headers = [d[0] for d in conn.execute("SELECT * FROM users LIMIT 0").description]
    fname = 'export.csv'
    with open(fname, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f)
        w.writerow(headers)
        w.writerows(rows)
    with open(fname, 'rb') as f:
        await update.message.reply_document(f, filename="Hamfaz_DB.csv", caption="📊 دیتابیس کامل")
    os.remove(fname)

@admin_only
async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    total, males, females, today, banned, top3 = get_stats()
    online = len(connected_pairs) // 2
    queue  = len(waiting_queue) + len(vip_queue)
    top_txt = "\n".join(
        [f"  • {TRANS.get(r[0], r[0])}: {r[1]} نفر" for r in top3]
    ) or "—"
    await update.message.reply_text(
        f"📊 <b>آمار لحظه‌ای هم‌فاز</b>\n\n"
        f"👥 کل کاربران: <b>{total}</b>\n"
        f"👦 پسر: <b>{males}</b> | 👧 دختر: <b>{females}</b>\n"
        f"🆕 ثبت‌نام امروز: <b>{today}</b>\n"
        f"🚫 بن‌شده: <b>{banned}</b>\n\n"
        f"🟢 در حال چت: <b>{online}</b> زوج\n"
        f"⏳ در صف: <b>{queue}</b> نفر\n\n"
        f"🏆 محبوب‌ترین علایق:\n{top_txt}",
        parse_mode=ParseMode.HTML
    )

@admin_only
async def cmd_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("استفاده: /ban USER_ID")
        return
    try:
        uid = int(context.args[0])
        set_ban(uid, 1)
        await update.message.reply_text(f"✅ کاربر {uid} بن شد.")
        await safe_send(context.bot, uid, "🚫 حساب شما مسدود شده است.")
    except:
        await update.message.reply_text("❌ آیدی نامعتبر")

@admin_only
async def cmd_unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("استفاده: /unban USER_ID")
        return
    try:
        uid = int(context.args[0])
        set_ban(uid, 0)
        await update.message.reply_text(f"✅ کاربر {uid} از بن درآمد.")
    except:
        await update.message.reply_text("❌ آیدی نامعتبر")

# ── Broadcast با فیلتر ──
@admin_only
async def cmd_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("👦 فقط پسرها",  callback_data="bcg_Male"),
         InlineKeyboardButton("👧 فقط دخترها", callback_data="bcg_Female")],
        [InlineKeyboardButton("👥 همه",         callback_data="bcg_all")]
    ])
    await update.message.reply_text(
        "📢 <b>پیام همگانی هدفمند</b>\n\nمرحله ۱: مخاطب رو انتخاب کن:",
        reply_markup=kb, parse_mode=ParseMode.HTML
    )
    return S_BC_GENDER

async def bc_gender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    context.user_data['bc_g'] = q.data.replace("bcg_", "")
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("18-25",    callback_data="bca_18-25"),
         InlineKeyboardButton("25-35",    callback_data="bca_25-35")],
        [InlineKeyboardButton("زیر ۱۸",   callback_data="bca_-18"),
         InlineKeyboardButton("بالای ۳۵", callback_data="bca_+35")],
        [InlineKeyboardButton("همه سنین", callback_data="bca_all")]
    ])
    await q.edit_message_text("📢 مرحله ۲: بازه سنی:", reply_markup=kb)
    return S_BC_AGE

async def bc_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    context.user_data['bc_a'] = q.data.replace("bca_", "")
    await q.edit_message_text("📢 مرحله ۳: پیام، عکس یا ویدیوت رو بفرست:\n(/cancel برای لغو)")
    return S_BC_MSG

async def bc_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return ConversationHandler.END
    g   = context.user_data.get('bc_g', 'all')
    a   = context.user_data.get('bc_a', 'all')
    ids = get_filtered_users(
        gender=None if g == 'all' else g,
        age=None    if a == 'all' else a
    )
    await update.message.reply_text(f"⏳ در حال ارسال به {len(ids)} کاربر...")
    sent = failed = 0
    for uid in ids:
        try:
            await context.bot.copy_message(chat_id=uid, from_chat_id=update.effective_user.id, message_id=update.message.message_id)
            sent += 1
        except:
            failed += 1
        await asyncio.sleep(0.05)
    await update.message.reply_text(f"✅ تموم شد!\n✔️ موفق: {sent} | ❌ ناموفق: {failed}")
    return ConversationHandler.END

async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ لغو شد.", reply_markup=main_kb())
    return ConversationHandler.END

# ══════════════════════════════════════════════════════════
#  ۱۴. هندلر اصلی چت
# ══════════════════════════════════════════════════════════
async def main_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_user:
        return

    uid  = update.effective_user.id
    text = update.message.text

    # بن چک
    if is_banned(uid):
        await update.message.reply_text("🚫 حساب شما مسدود است.")
        return

    # ──── دکمه‌های کیبورد ────
    if text == "👤 پروفایل من":
        await update.message.reply_text(
            my_dashboard(uid, context.bot.username),
            parse_mode=ParseMode.HTML, reply_markup=main_kb()
        )
        return

    if text == "💎 جستجوی VIP":
        await vip_step1(update, context)
        return

    if text == "⏪ ماشین زمان (۱۰ سکه)":
        if uid in connected_pairs:
            await update.message.reply_text("⚠️ اول مکالمه فعلی رو قطع کن.")
            return
        pid = last_partner.get(uid)
        if not pid:
            await update.message.reply_text("🤔 هنوز با کسی چت نکردی!")
            return
        coins = get_coins(uid)
        if coins < 10:
            ref = f"https://t.me/{context.bot.username}?start=ref_{uid}"
            await update.message.reply_text(
                f"💰 <b>سکه کافی نداری!</b>\nداری: {coins} | نیاز: ۱۰\n\n"
                f"👇 با دعوت دوستات سکه بگیر:\n<code>{ref}</code>",
                parse_mode=ParseMode.HTML
            )
            return
        if pid in connected_pairs:
            await update.message.reply_text("😔 نفر قبلی الان مشغوله. (سکه کم نشد)")
            return
        deduct_coins(uid, 10)
        async with _lock:
            if uid in waiting_queue: waiting_queue.remove(uid)
            if pid in waiting_queue: waiting_queue.remove(pid)
            connected_pairs[uid] = pid
            connected_pairs[pid] = uid
        await update.message.reply_text(
            "✨ <b>ماشین زمان کار کرد!</b> ۱۰ سکه کم شد.",
            parse_mode=ParseMode.HTML, reply_markup=main_kb()
        )
        await safe_send(context.bot, pid, "✨ نفر قبلی دوباره وصل شد! 😉", reply_markup=main_kb())
        return

    if text in ("➡️ نفر بعدی", "❌ پایان مکالمه"):
        if text == "➡️ نفر بعدی" and is_spamming(uid):
            await update.message.reply_text("⏳ خیلی سریع! کمی صبر کن.", reply_markup=main_kb())
            return
        await do_disconnect(uid, context.bot, notify=True)
        if text == "➡️ نفر بعدی":
            try:
                await update.message.reply_text(AD_TEXT, parse_mode=ParseMode.HTML)
            except:
                pass
            await do_find_match(update, context)
        else:
            await update.message.reply_text("⛔️ مکالمه قطع شد.", reply_markup=main_kb())
        return

    # ──── پیام‌های چت ────
    if uid in connected_pairs:
        partner = connected_pairs.get(uid)

        # فیلتر فوروارد
        if getattr(update.message, 'forward_origin', None):
            await update.message.reply_text("⚠️ ارسال پیام فوروارد مجاز نیست.")
            return

        # فیلتر لینک و منشن
        if update.message.entities:
            bad = {"url", "text_link", "mention"}
            for e in update.message.entities:
                if e.type in bad:
                    await update.message.reply_text("⚠️ ارسال لینک و منشن مجاز نیست.")
                    return

        # ارسال پیام — سازگار با همه نسخه‌های کتابخانه
        try:
            await context.bot.copy_message(
                chat_id=partner,
                from_chat_id=uid,
                message_id=update.message.message_id
            )
        except Exception as e:
            logger.warning(f"[CHAT] ERROR {uid}->{partner}: {e}")
            if "bot was blocked" in str(e).lower() or "user is deactivated" in str(e).lower():
                await update.message.reply_text("❌ مخاطب ربات رو بلاک کرده.")
                async with _lock:
                    connected_pairs.pop(uid, None)
                    connected_pairs.pop(partner, None)
                    last_partner[uid]     = partner
                    last_partner[partner] = uid

    else:
        in_q = uid in waiting_queue or any(x[0] == uid for x in vip_queue)
        if not in_q:
            if not user_exists(uid):
                await update.message.reply_text("⚠️ ابتدا /start بزن.")
            else:
                await update.message.reply_text(
                    "وصل نیستی. دکمه 'نفر بعدی' رو بزن!",
                    reply_markup=main_kb()
                )

# ══════════════════════════════════════════════════════════
#  ۱۵. راه‌اندازی
# ══════════════════════════════════════════════════════════
if __name__ == '__main__':
    init_db()

    app = ApplicationBuilder().token(TOKEN).build()

    # ── Conversation ثبت‌نام ──
    reg = ConversationHandler(
        entry_points=[CommandHandler('start', cmd_start)],
        states={
            S_ANON_MSG:  [MessageHandler(filters.ALL & ~filters.COMMAND, handle_anon)],
            S_WELCOME:   [CallbackQueryHandler(q_gender,    pattern='^go$')],
            S_GENDER:    [CallbackQueryHandler(q_age,       pattern='^(Male|Female)$')],
            S_AGE:       [CallbackQueryHandler(q_location,  pattern='^(-18|18-25|25-35|[+]35)$')],
            S_LOCATION:  [CallbackQueryHandler(q_status,    pattern='^(Tehran|City|Other|Abroad)$')],
            S_STATUS:    [CallbackQueryHandler(q_interest,  pattern='^(Single|InRel|Married|Complicated)$')],
            S_INTEREST:  [CallbackQueryHandler(q_music,     pattern='^(Game|Movie|Art|Tech|Sport|Trade)$')],
            S_MUSIC:     [CallbackQueryHandler(q_personality, pattern='^(Rap|Pop|Rock|Electro)$')],
            S_PERSONALITY:[CallbackQueryHandler(q_vacation, pattern='^(Extrovert|Introvert|Logical|Emotional)$')],
            S_VACATION:  [CallbackQueryHandler(q_phone,     pattern='^(Vac_Cafe|Vac_Shomal|Vac_Dubai|Vac_Home)$')],
            S_PHONE:     [CallbackQueryHandler(finish_reg,  pattern='^(Phone_Apple|Phone_Android|Phone_None)$')],
        },
        fallbacks=[CommandHandler('start', cmd_start), CommandHandler('cancel', cmd_cancel)],
        allow_reentry=True
    )

    # ── Conversation VIP ──
    vip = ConversationHandler(
        entry_points=[CallbackQueryHandler(vip_gender, pattern='^vg_')],
        states={
            S_VIP_LOCATION: [CallbackQueryHandler(vip_location, pattern='^vl_')],
        },
        fallbacks=[CommandHandler('cancel', cmd_cancel)],
        allow_reentry=True
    )

    # ── Conversation Broadcast ──
    bc = ConversationHandler(
        entry_points=[CommandHandler('broadcast', cmd_broadcast)],
        states={
            S_BC_GENDER: [CallbackQueryHandler(bc_gender, pattern='^bcg_')],
            S_BC_AGE:    [CallbackQueryHandler(bc_age,    pattern='^bca_')],
            S_BC_MSG:    [MessageHandler(filters.ALL & ~filters.COMMAND, bc_send)],
        },
        fallbacks=[CommandHandler('cancel', cmd_cancel)],
        allow_reentry=True
    )

    # ── ثبت handler ها — ترتیب مهمه ──
    app.add_handler(CommandHandler('export',    cmd_export))
    app.add_handler(CommandHandler('stats',     cmd_stats))
    app.add_handler(CommandHandler('ban',       cmd_ban))
    app.add_handler(CommandHandler('unban',     cmd_unban))
    app.add_handler(reg)
    app.add_handler(vip)
    app.add_handler(bc)
    app.add_handler(CallbackQueryHandler(cb_check_join, pattern='^check_join$'))
    app.add_handler(CallbackQueryHandler(cb_karma,      pattern='^karma_'))
    app.add_handler(CallbackQueryHandler(cb_report,     pattern='^report_'))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, main_handler))

    print("🚀 ربات هم‌فاز — نسخه نهایی در حال اجراست...")
    app.run_polling(drop_pending_updates=True)
