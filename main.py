
# -*- coding: utf-8 -*-
"""
SlsurveyBot — نسخة نهائية احترافية (مستخدم + أدمن) + اشتراك إجباري

✅ اشتراك إجباري بقناة: @broichancy
- زر: ✅ اشترك بالقناة
- زر: 🔄 تحقق من الاشتراك

✅ Wallet: Balance + Hold (مع حماية من السالب)
✅ شحن رصيد البوت: سيرياتيل كاش فقط (كود 23547) => رقم عملية => مبلغ >= 15000 => طلب للأدمن
✅ سحب رصيد البوت: سيرياتيل كاش فقط => رقم مستلم => مبلغ >= 50000 => حجز فوري (Balance- , Hold+) => الأدمن
✅ عند رفض السحب/شحن إيـشانسي: يرجع الرصيد تلقائيًا

✅ حساب إيـشانسي:
- إنشاء حساب: يُرسل طلب للأدمن مع (username/password) + الأدمن يستطيع "تعديل" ثم "قبول"
- عند قبول الأدمن: يتم حفظ الحساب للمستخدم (مرة واحدة فقط)
- منع إنشاء أكثر من حساب (إذا لديه حساب محفوظ)
- شحن إيـشانسي: يتأكد من وجود حساب + رصيد كافي + حجز فوري، وعند القبول تثبيت الخصم
- سحب من إيـشانسي إلى رصيد البوت: يتأكد من وجود حساب، وعند القبول يضاف الرصيد للمستخدم

✅ منع أكثر من طلب معلّق للمستخدم
✅ JSON تخزين كامل
✅ لوحة أدمن Inline احترافية + تعديل بيانات إنشاء إيـشانسي

المتطلبات:
pip install python-telegram-bot==21.6
"""

import json
import os
import time
import asyncio
import re
from typing import Dict, Any, Optional, List, Tuple

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from telegram.constants import ChatMemberStatus
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ChatMemberHandler,
    ContextTypes,
    ConversationHandler,
    filters,
)

# =========================
# إعدادات أساسية
# =========================
TOKEN = (os.getenv("BOT_TOKEN") or os.getenv("TOKEN") or "").strip()

if not TOKEN:

    raise RuntimeError("BOT_TOKEN (or TOKEN) env var is required")

SUPER_ADMIN_ID = int(os.getenv("SUPER_ADMIN_ID", "0") or "0")
if not SUPER_ADMIN_ID:
    raise RuntimeError("SUPER_ADMIN_ID env var is required (your Telegram numeric ID)")
ADMIN_ID = SUPER_ADMIN_ID
  # السوبر أدمن (يستطيع تعيين/إزالة أدمن)
DATA_DIR = os.getenv("DATA_DIR", "data")
os.makedirs(DATA_DIR, exist_ok=True)

ADMINS_FILE   = os.path.join(DATA_DIR, "admins.json")
USERS_FILE    = os.path.join(DATA_DIR, "users.json")
# ✅ قناة الاشتراك الإجباري
REQUIRED_CHANNEL = os.getenv("REQUIRED_CHANNEL", "@broichancy")
REQUIRED_CHANNEL_URL = "https://t.me/broichancy"

BALANCES_FILE = os.path.join(DATA_DIR, "balances.json")
ORDERS_FILE   = os.path.join(DATA_DIR, "orders.json")
HISTORY_FILE  = os.path.join(DATA_DIR, "history.json")
ADMINLOG_FILE = os.path.join(DATA_DIR, "admin_log.json")
BANS_FILE     = os.path.join(DATA_DIR, "bans.json")
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")
EISH_FILE     = os.path.join(DATA_DIR, "eishancy_accounts.json")
EISH_POOL_FILE = os.path.join(DATA_DIR, "eishancy_pool.json")  # list of {username,password,status,assigned_to,assigned_at}
REF_FILE       = os.path.join(DATA_DIR, "referrals.json")      # {referrer_id: {points:int, referrals:int, referred:[uids]}}  # {uid:{username,password,created_at}}

DEFAULT_SETTINGS = {
    "syriatel_code": "23547",
    "min_topup": 15000,
    "min_withdraw": 50000,
    "max_pending": 1,
    "admin_page_size": 6
}

# =========================
# أزرار المستخدم
# =========================
BTN_EISHANCY = "حساب ايشانسي"
BTN_BALANCE  = "رصيدي"
BTN_REFERRALS = "🎁 الإحالات"
BTN_BACK     = "رجوع للقائمة الرئيسية"

BTN_CREATE   = "إنشاء حساب"
BTN_E_TOPUP  = "شحن حساب ايشانسي"
BTN_E_WITH   = "سحب من حساب ايشانسي"
BTN_E_DEL    = "حذف حساب ايشانسي"
BTN_EISH_SITE = "🌐 موقع iChancy"

BTN_BOT_TOPUP    = "شحن رصيد في البوت"
BTN_BOT_WITHDRAW = "سحب رصيد من البوت"

BTN_SYRIATEL = "سيرياتيل كاش"
BTN_SHAM     = "شام كاش"

BTN_CONFIRM  = "✅ تأكيد"
BTN_CANCEL   = "❌ إلغاء"

# =========================
# Callback (اشتراك إجباري)
# =========================
CB_CHECK_JOIN = "JOIN:CHECK"

# =========================
# حالات المحادثة (User)
# =========================
(
    ST_MAIN,
    ST_EISH_ACTION,
    ST_E_USER,
    ST_E_PASS,
    ST_BAL_MENU,
    ST_TOPUP_METHOD,
    ST_TOPUP_TXID,
    ST_WITHDRAW_METHOD,
    ST_WITHDRAW_NUMBER,
    ST_AMOUNT,
    ST_CONFIRM,
) = range(11)

# =========================
# JSON Helpers (بدون recursion)
# =========================
def _ensure_data_files():
    os.makedirs(DATA_DIR, exist_ok=True)
    files = [
        (BALANCES_FILE, {}),
        (ORDERS_FILE, {}),
        (HISTORY_FILE, {}),
        (ADMINLOG_FILE, []),
        (BANS_FILE, {}),
        (SETTINGS_FILE, DEFAULT_SETTINGS),
        (EISH_FILE, {}),
        (EISH_POOL_FILE, []),
        (REF_FILE, {}),
        (USERS_FILE, {}),  # {uid: {username, first_name, last_name, joined_at, last_seen, active}}
        (ADMINS_FILE, {"super_admin": int(SUPER_ADMIN_ID), "admins": [int(SUPER_ADMIN_ID)]}),
    ]
    for path, default in files:
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as f:
                json.dump(default, f, ensure_ascii=False, indent=2)

def _load_json(path: str):
    _ensure_data_files()
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        if path.endswith("admin_log.json"):
            return []
        if path.endswith("settings.json"):
            return DEFAULT_SETTINGS.copy()
        return {}

def _save_json(path: str, data):
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)

# =========================
# Settings
# =========================
def get_settings() -> Dict[str, Any]:
    s = _load_json(SETTINGS_FILE)
    merged = DEFAULT_SETTINGS.copy()
    if isinstance(s, dict):
        merged.update({k: s.get(k, merged[k]) for k in merged.keys()})

    merged["min_topup"] = int(merged["min_topup"])
    merged["min_withdraw"] = int(merged["min_withdraw"])
    merged["max_pending"] = int(merged["max_pending"])
    merged["admin_page_size"] = int(merged["admin_page_size"])
    merged["syriatel_code"] = str(merged["syriatel_code"]).strip()

    _save_json(SETTINGS_FILE, merged)
    return merged

def set_settings(updates: Dict[str, Any]) -> Dict[str, Any]:
    s = get_settings()
    s.update(updates)
    _save_json(SETTINGS_FILE, s)
    return s

# =========================
# Wallet
# =========================
def get_wallet(uid: int) -> Tuple[int, int]:
    balances = _load_json(BALANCES_FILE)
    w = balances.get(str(uid), {"balance": 0, "hold": 0})
    return int(w.get("balance", 0)), int(w.get("hold", 0))

def set_wallet(uid: int, balance: int, hold: int) -> None:
    balances = _load_json(BALANCES_FILE)
    balances[str(uid)] = {"balance": int(balance), "hold": int(hold)}
    _save_json(BALANCES_FILE, balances)

def adjust_wallet(uid: int, delta_balance: int = 0, delta_hold: int = 0) -> Tuple[int, int]:
    b, h = get_wallet(uid)
    nb = b + int(delta_balance)
    nh = h + int(delta_hold)
    if nb < 0 or nh < 0:
        raise ValueError(f"Wallet would go negative: uid={uid}, balance={nb}, hold={nh}")
    set_wallet(uid, nb, nh)
    return get_wallet(uid)

# =========================
# Users registry (ensure)
# =========================
def ensure_user_registered(uid: int) -> None:
    """Ensure user appears in balances/history so broadcast & سجل المشتركين include them."""
    uid_s = str(uid)
    balances = _load_json(BALANCES_FILE)
    if uid_s not in balances:
        balances[uid_s] = {"balance": 0, "hold": 0}
        _save_json(BALANCES_FILE, balances)
    hist = _load_json(HISTORY_FILE)
    if isinstance(hist, dict) and uid_s not in hist:
        hist[uid_s] = []
        _save_json(HISTORY_FILE, hist)

# =========================
# Eishancy Account
# =========================

# =========================
# User profiles (persist username/seen for admin panel)
# =========================
def get_user_profile(uid: int) -> Dict[str, Any]:
    users = _load_json(USERS_FILE)
    return users.get(str(uid), {})

def upsert_user_profile(user) -> None:
    """Persist minimal user info (called on any interaction)."""
    try:
        uid = int(user.id)
    except Exception:
        return
    users = _load_json(USERS_FILE)
    key = str(uid)
    now = int(time.time())
    cur = users.get(key, {})
    if not cur:
        cur = {
            "user_id": uid,
            "joined_at": now,
            "points": 0,
            "referrals": 0,
            "referred_by": None,
        }
    cur.update({
        "user_id": uid,
        "username": getattr(user, "username", None),
        "first_name": getattr(user, "first_name", None),
        "last_name": getattr(user, "last_name", None),
        "last_seen": now,
        "active": True,
    })
    users[key] = cur
    _save_json(USERS_FILE, users)

def mark_user_inactive(uid: int) -> None:
    users = _load_json(USERS_FILE)
    key = str(uid)
    cur = users.get(key, {"user_id": uid, "joined_at": int(time.time())})
    cur["active"] = False
    cur["last_seen"] = int(time.time())
    users[key] = cur
    _save_json(USERS_FILE, users)

def set_user_active(uid: int) -> None:
    users = _load_json(USERS_FILE)
    key = str(uid)
    cur = users.get(key, {"user_id": uid, "joined_at": int(time.time())})
    cur["active"] = True
    cur["last_seen"] = int(time.time())
    users[key] = cur
    _save_json(USERS_FILE, users)


# =========================
# Referrals (points)
# =========================
def _ref_obj() -> Dict[str, Any]:
    return _load_json(REF_FILE)

def get_points(uid: int) -> int:
    users = _load_json(USERS_FILE)
    return int(users.get(str(uid), {}).get("points", 0) or 0)

def add_points(uid: int, delta: int) -> None:
    users = _load_json(USERS_FILE)
    key = str(uid)
    cur = users.get(key, {"user_id": uid, "joined_at": int(time.time())})
    cur["points"] = max(0, int(cur.get("points", 0) or 0) + int(delta))
    users[key] = cur
    _save_json(USERS_FILE, users)

def add_referral(referrer_id: int, referred_id: int) -> bool:
    """Grant referral once per referred user. Returns True if granted."""
    if referrer_id == referred_id:
        return False
    users = _load_json(USERS_FILE)
    rkey = str(referred_id)
    cur = users.get(rkey)
    if not cur:
        # should exist, but be safe
        cur = {"user_id": referred_id, "joined_at": int(time.time()), "points": 0, "referrals": 0, "referred_by": None}
    if cur.get("referred_by") is not None:
        return False
    # mark referred_by
    cur["referred_by"] = int(referrer_id)
    users[rkey] = cur
    _save_json(USERS_FILE, users)
    # grant points to referrer
    users2 = _load_json(USERS_FILE)
    fkey = str(referrer_id)
    fcur = users2.get(fkey, {"user_id": referrer_id, "joined_at": int(time.time()), "points": 0, "referrals": 0, "referred_by": None})
    fcur["points"] = int(fcur.get("points", 0) or 0) + 10
    fcur["referrals"] = int(fcur.get("referrals", 0) or 0) + 1
    users2[fkey] = fcur
    _save_json(USERS_FILE, users2)
    return True

def referral_link(bot_username: str, uid: int) -> str:
    return f"https://t.me/{bot_username}?start=ref_{uid}"

# =========================
# Admins (multi-admin)
# =========================
def _load_admins_obj() -> Dict[str, Any]:
    obj = _load_json(ADMINS_FILE)
    # normalize
    if not isinstance(obj, dict):
        obj = {"super_admin": int(SUPER_ADMIN_ID), "admins": [int(SUPER_ADMIN_ID)]}
    obj.setdefault("super_admin", int(SUPER_ADMIN_ID))
    obj.setdefault("admins", [int(obj.get("super_admin", SUPER_ADMIN_ID))])
    # ensure super present
    sa = int(obj.get("super_admin", SUPER_ADMIN_ID))
    admins = obj.get("admins", [])
    if sa not in admins:
        admins.append(sa)
    obj["admins"] = sorted({int(x) for x in admins})
    _save_json(ADMINS_FILE, obj)
    return obj

def get_admin_ids() -> List[int]:
    obj = _load_admins_obj()
    return list(obj.get("admins", []))

def is_admin(uid: int) -> bool:
    try:
        uid = int(uid)
    except Exception:
        return False
    return uid in set(get_admin_ids())

def is_super_admin(uid: int) -> bool:
    obj = _load_admins_obj()
    try:
        return int(uid) == int(obj.get("super_admin", SUPER_ADMIN_ID))
    except Exception:
        return False

def add_admin(uid: int) -> bool:
    obj = _load_admins_obj()
    admins = set(int(x) for x in obj.get("admins", []))
    admins.add(int(uid))
    obj["admins"] = sorted(admins)
    _save_json(ADMINS_FILE, obj)
    return True

def remove_admin(uid: int) -> bool:
    obj = _load_admins_obj()
    sa = int(obj.get("super_admin", SUPER_ADMIN_ID))
    uid = int(uid)
    if uid == sa:
        return False
    admins = set(int(x) for x in obj.get("admins", []))
    admins.discard(uid)
    obj["admins"] = sorted(admins)
    _save_json(ADMINS_FILE, obj)
    return True

async def notify_admins(context: ContextTypes.DEFAULT_TYPE, text: str, reply_markup=None, order_id: str | None = None):
    """Send to all admins; if order_id provided, store message ids for cleanup."""
    admin_msgs = []
    for aid in get_admin_ids():
        try:
            msg = await context.bot.send_message(chat_id=aid, text=text, reply_markup=reply_markup)
            admin_msgs.append({"chat_id": aid, "message_id": msg.message_id})
        except Exception:
            pass
    if order_id and admin_msgs:
        # append to existing
        order = get_order(order_id) or {}
        existing = order.get("admin_msgs") or []
        if isinstance(existing, list):
            existing.extend(admin_msgs)
        else:
            existing = admin_msgs
        update_order(order_id, {"admin_msgs": existing})

async def cleanup_order_admin_messages(context: ContextTypes.DEFAULT_TYPE, order: Dict[str, Any]):
    msgs = order.get("admin_msgs") or []
    if not isinstance(msgs, list):
        return
    for it in msgs:
        try:
            chat_id = it.get("chat_id")
            mid = it.get("message_id")
            if chat_id and mid:
                # prefer removing buttons; if not possible, try delete
                try:
                    await context.bot.edit_message_reply_markup(chat_id=chat_id, message_id=mid, reply_markup=None)
                except Exception:
                    try:
                        await context.bot.delete_message(chat_id=chat_id, message_id=mid)
                    except Exception:
                        pass
        except Exception:
            pass

def get_eish(uid: int) -> Optional[Dict[str, Any]]:
    data = _load_json(EISH_FILE)
    return data.get(str(uid))

def set_eish(uid: int, username: str, password: str):
    data = _load_json(EISH_FILE)
    data[str(uid)] = {
        "username": username,
        "password": password,
        "created_at": int(time.time())
    }
    _save_json(EISH_FILE, data)


def delete_eish(uid: int) -> bool:
    data = _load_json(EISH_FILE)
    if str(uid) in data:
        data.pop(str(uid), None)
        _save_json(EISH_FILE, data)
        return True
    return False

# =========================
# Bans
# =========================
def is_banned(uid: int) -> Tuple[bool, str]:
    bans = _load_json(BANS_FILE)
    info = bans.get(str(uid), {})
    if info.get("banned"):
        return True, info.get("reason", "محظور")
    return False, ""

def ban_user(uid: int, reason: str):
    bans = _load_json(BANS_FILE)
    bans[str(uid)] = {"banned": True, "reason": reason, "ts": int(time.time())}
    _save_json(BANS_FILE, bans)

def unban_user(uid: int):
    bans = _load_json(BANS_FILE)
    if str(uid) in bans:
        bans[str(uid)] = {"banned": False, "reason": "", "ts": int(time.time())}
        _save_json(BANS_FILE, bans)

# =========================
# History + Admin log
# =========================
def add_history(uid: int, event: Dict[str, Any]):
    hist = _load_json(HISTORY_FILE)
    key = str(uid)
    hist.setdefault(key, [])
    hist[key].append(event)
    hist[key] = hist[key][-200:]
    _save_json(HISTORY_FILE, hist)

def get_history(uid: int) -> List[Dict[str, Any]]:
    hist = _load_json(HISTORY_FILE)
    return hist.get(str(uid), [])

def admin_log(event: Dict[str, Any]):
    log = _load_json(ADMINLOG_FILE)
    if not isinstance(log, list):
        log = []
    log.append(event)
    log = log[-500:]
    _save_json(ADMINLOG_FILE, log)

# =========================
# Orders
# =========================
def make_order_id(prefix: str) -> str:
    return f"{prefix}-{time.time_ns()}"

def add_order(order: Dict[str, Any]):
    orders = _load_json(ORDERS_FILE)
    orders[order["order_id"]] = order
    _save_json(ORDERS_FILE, orders)

def get_order(order_id: str) -> Optional[Dict[str, Any]]:
    return _load_json(ORDERS_FILE).get(order_id)

def update_order(order_id: str, updates: Dict[str, Any]):
    orders = _load_json(ORDERS_FILE)
    if order_id in orders:
        orders[order_id].update(updates)
        _save_json(ORDERS_FILE, orders)

def list_orders() -> List[Dict[str, Any]]:
    orders = _load_json(ORDERS_FILE)
    vals = list(orders.values())
    return sorted(vals, key=lambda x: int(x.get("created_at", 0)), reverse=True)

def pending_for_user(uid: int) -> List[Dict[str, Any]]:
    return [o for o in list_orders() if o.get("user_id") == uid and o.get("status") == "pending"]

def has_pending_lock(uid: int) -> bool:
    s = get_settings()
    return len(pending_for_user(uid)) >= int(s["max_pending"])

def rollback_order_if_exceeds_pending(uid: int, order_id: str) -> bool:
    s = get_settings()
    if len(pending_for_user(uid)) > int(s["max_pending"]):
        orders = _load_json(ORDERS_FILE)
        orders.pop(order_id, None)
        _save_json(ORDERS_FILE, orders)
        return True
    return False

# =========================
# Users registry (for broadcast)
# =========================
def get_all_user_ids() -> List[int]:
    """Collect all known user IDs from stored JSON files (best-effort)."""
    uids: set[int] = set()

    def add_keys(d):
        if isinstance(d, dict):
            for k in d.keys():
                if str(k).isdigit():
                    uids.add(int(k))

    # balances keys
    add_keys(_load_json(BALANCES_FILE))

    # users keys
    add_keys(_load_json(USERS_FILE))

    # history keys
    add_keys(_load_json(HISTORY_FILE))

    # eishancy accounts keys
    add_keys(_load_json(EISH_FILE))

    # bans keys
    add_keys(_load_json(BANS_FILE))

    # orders user_id values
    orders = _load_json(ORDERS_FILE)
    if isinstance(orders, dict):
        for o in orders.values():
            try:
                uids.add(int(o.get("user_id")))
            except Exception:
                pass

    # remove admin
    uids.discard(int(ADMIN_ID))
    return sorted(uids)


# =========================
# Validators
# =========================
def is_pos_int(s: str) -> bool:
    return s.isdigit() and int(s) > 0

def is_reasonable_txid(s: str) -> bool:
    return s.isdigit() and 6 <= len(s) <= 20

def is_reasonable_phone(s: str) -> bool:
    return s.isdigit() and 7 <= len(s) <= 14

def safe_text(s: str) -> str:
    return (s or "").strip()

# =========================
# اشتراك إجباري: UI + تحقق
# =========================
def ik_join_required():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ اشترك بالقناة", url=REQUIRED_CHANNEL_URL)],
        [InlineKeyboardButton("🔄 تحقق من الاشتراك", callback_data=CB_CHECK_JOIN)],
    ])

async def is_user_joined(context: ContextTypes.DEFAULT_TYPE, uid: int) -> bool:
    try:
        m = await context.bot.get_chat_member(chat_id=REQUIRED_CHANNEL, user_id=uid)
        return m.status in (ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER)
    except Exception:
        return False

async def ensure_joined(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    uid = update.effective_user.id
    ok = await is_user_joined(context, uid)
    if not ok:
        await update.effective_message.reply_text(
            "⚠️ لاستخدام البوت يجب الاشتراك بالقناة أولاً:\n"
            f"{REQUIRED_CHANNEL}\n\n"
            "بعد الاشتراك اضغط زر (🔄 تحقق من الاشتراك).",
            reply_markup=ik_join_required()
        )
        return False
    return True

async def guard_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    uid = update.effective_user.id
    banned, reason = is_banned(uid)
    if banned:
        await update.effective_message.reply_text(f"⛔ حسابك محظور.\nالسبب: {reason}")
        return False
    if not await ensure_joined(update, context):
        return False
    ensure_user_registered(uid)
    upsert_user_profile(update.effective_user)
    set_user_active(uid)
    return True

async def cb_check_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if not q:
        return
    await q.answer()

    uid = q.from_user.id
    ok = await is_user_joined(context, uid)
    if not ok:
        await q.message.reply_text(
            "❌ لم يتم العثور على اشتراكك بالقناة بعد.\n"
            "اشترك أولاً ثم اضغط (🔄 تحقق من الاشتراك) مرة ثانية.",
            reply_markup=ik_join_required()
        )
        return

    await q.message.reply_text(
        "✅ تم التحقق! أهلاً بك 👋\nاختر أحد الخيارات من الأسفل:",
        reply_markup=kb_main()
    )

# (اختياري) حدث ترك القناة — يحتاج البوت أدمن بالقناة
async def on_channel_member_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        chat = update.chat_member.chat
        new_status = update.chat_member.new_chat_member.status
        old_status = update.chat_member.old_chat_member.status
        user = update.chat_member.from_user
    except Exception:
        return

    if (chat.username or "").lower() != REQUIRED_CHANNEL.lstrip("@").lower():
        return

    left_now = new_status in ("left", "kicked") and old_status not in ("left", "kicked")
    if left_now:
        admin_log({"ts": int(time.time()), "admin_id": ADMIN_ID, "action": "left_required_channel", "uid": user.id})
        try:
            await notify_admins(context, text=f"ℹ️ المستخدم {user.id} ترك القناة الإلزامية. سيتم منعه تلقائيًا عند استخدام البوت.")
        except Exception:
            pass

# =========================
# UI Keyboards (User)
# =========================
def kb_main():
    return ReplyKeyboardMarkup(
        [[KeyboardButton(BTN_EISHANCY), KeyboardButton(BTN_BALANCE)],
         [KeyboardButton(BTN_REFERRALS)]],
        resize_keyboard=True
    )

def kb_back():
    return ReplyKeyboardMarkup([[KeyboardButton(BTN_BACK)]], resize_keyboard=True)

def kb_eish_actions():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton(BTN_CREATE), KeyboardButton(BTN_E_TOPUP)],
            [KeyboardButton(BTN_E_WITH), KeyboardButton(BTN_E_DEL)],
            [KeyboardButton(BTN_EISH_SITE)],
            [KeyboardButton(BTN_BACK)]
        ],
        resize_keyboard=True
    )

def kb_balance_menu():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton(BTN_BOT_TOPUP), KeyboardButton(BTN_BOT_WITHDRAW)],
            [KeyboardButton(BTN_BACK)]
        ],
        resize_keyboard=True
    )

def kb_methods():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton(BTN_SYRIATEL), KeyboardButton(BTN_SHAM)],
            [KeyboardButton(BTN_BACK)]
        ],
        resize_keyboard=True
    )

def kb_confirm():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton(BTN_CONFIRM), KeyboardButton(BTN_CANCEL)],
            [KeyboardButton(BTN_BACK)]
        ],
        resize_keyboard=True
    )

# =========================
# UI (Admin Inline)
# =========================
def ik_admin_home():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📥 الطلبات المعلقة", callback_data="AD:PENDING:0"),
         InlineKeyboardButton("📜 آخر الطلبات", callback_data="AD:LAST:0")],
        [InlineKeyboardButton("🔎 بحث OrderID", callback_data="AD:SEARCH"),
         InlineKeyboardButton("👤 إدارة مستخدم", callback_data="AD:USER")],
        [InlineKeyboardButton("📊 إحصائيات", callback_data="AD:STATS"),
         InlineKeyboardButton("⚙️ إعدادات", callback_data="AD:SETTINGS")],
        [InlineKeyboardButton("👥 سجل المشتركين", callback_data="AD:USERS:0"),
         InlineKeyboardButton("📣 رسالة جماعية", callback_data="AD:BCAST")],
        [InlineKeyboardButton("🗂 مخزون إيـشانسي", callback_data="AD:EPOOL")],
        [InlineKeyboardButton("🧾 تصدير مختصر", callback_data="AD:EXPORT")]
    ])


def ik_copy_creds():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 نسخ اسم المستخدم", callback_data="COPY:USER"),
         InlineKeyboardButton("📋 نسخ كلمة المرور", callback_data="COPY:PASS")],
        [InlineKeyboardButton("⬅️ رجوع", callback_data="EISH:MENU")]
    ])

def ik_suggest_accept():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ موافق", callback_data="EISH:ACCEPT"),
         InlineKeyboardButton("✏️ اكتب اسم آخر", callback_data="EISH:RETRY")],
        [InlineKeyboardButton("⬅️ رجوع", callback_data="EISH:MENU")]
    ])

def ik_epool_home():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ إضافة حسابات بالجملة", callback_data="AD:EPOOL:ADD"),
         InlineKeyboardButton("📋 المتاح", callback_data="AD:EPOOL:AVAIL")],
        [InlineKeyboardButton("📦 الموزع", callback_data="AD:EPOOL:ASSIGNED"),
         InlineKeyboardButton("📊 إحصائيات المخزون", callback_data="AD:EPOOL:STATS")],
        [InlineKeyboardButton("⬅️ رجوع", callback_data="AD:HOME")]
    ])
def ik_admin_back():
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ رجوع", callback_data="AD:HOME")]])

def ik_order_actions(order_id: str, allow_edit: bool = False):
    rows = [
        [InlineKeyboardButton("✅ قبول", callback_data=f"OD:APPROVE:{order_id}"),
         InlineKeyboardButton("❌ رفض", callback_data=f"OD:REJECT:{order_id}")],
    ]
    if allow_edit:
        rows.append([InlineKeyboardButton("✏️ تعديل البيانات", callback_data=f"OD:EDIT:{order_id}")])
    rows += [
        [InlineKeyboardButton("👤 المستخدم", callback_data=f"OD:USER:{order_id}"),
         InlineKeyboardButton("🧾 السجل", callback_data=f"OD:HIST:{order_id}")],
        [InlineKeyboardButton("⬅️ رجوع", callback_data="AD:PENDING:0")]
    ]
    return InlineKeyboardMarkup(rows)

def ik_pagination(base: str, page: int, has_prev: bool, has_next: bool):
    btns = []
    if has_prev:
        btns.append(InlineKeyboardButton("⬅️ السابق", callback_data=f"{base}:{page-1}"))
    btns.append(InlineKeyboardButton(f"📄 {page+1}", callback_data="AD:HOME"))
    if has_next:
        btns.append(InlineKeyboardButton("التالي ➡️", callback_data=f"{base}:{page+1}"))
    return InlineKeyboardMarkup([btns, [InlineKeyboardButton("⬅️ رجوع", callback_data="AD:HOME")]])

# =========================
# رسائل UX
# =========================
def msg_pending_notice() -> str:
    return "⏳ تم استلام طلبك وجارٍ مراجعته من قبل الإدارة.\nسيتم إشعارك فور اتخاذ القرار."

def msg_support() -> str:
    return "📞 شام كاش: تواصل مع الدعم."

# =========================
# User handlers
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
            if not await guard_user(update, context):
                return ConversationHandler.END

            # referral payload: /start ref_<uid>
            try:
                args = getattr(context, "args", []) or []
                if args:
                    payload = args[0]
                    if isinstance(payload, str) and payload.startswith("ref_"):
                        ref_uid = int(payload.split("_", 1)[1])
                        granted = add_referral(ref_uid, update.effective_user.id)
                        if granted:
                            try:
                                await context.bot.send_message(chat_id=ref_uid, text="🎉 لديك إحالة جديدة! تم إضافة 10 نقاط إلى رصيد نقاطك.")
                            except Exception:
                                pass
            except Exception:
                pass

            context.user_data.clear()
            await update.message.reply_text(
        "أهلًا وسهلاً بكم في بوت الخدمات 👋\nاختر أحد الخيارات من الأسفل:",
                reply_markup=kb_main()
            )
            return ST_MAIN

async def go_home(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await guard_user(update, context):
        return ConversationHandler.END

    context.user_data.clear()
    if update.message:
        await update.message.reply_text("✅ رجعناك للقائمة الرئيسية", reply_markup=kb_main())
    return ST_MAIN

async def show_balance_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await guard_user(update, context):
        return ConversationHandler.END

    uid = update.effective_user.id
    b, h = get_wallet(uid)
    await update.message.reply_text(
        f"💰 رصيدك الحالي: {b}\n"
        f"⏳ رصيد محجوز: {h}\n\n"
        "اختر العملية التي تريدها:",
        reply_markup=kb_balance_menu()
    )
    return ST_BAL_MENU

async def smart_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await guard_user(update, context):
        return ConversationHandler.END

    text = safe_text(update.message.text)

    if text == BTN_BACK:
        return await go_home(update, context)

    if text in (BTN_EISHANCY, BTN_BALANCE):
        return await main_menu(update, context)

    if text in (BTN_CREATE, BTN_E_TOPUP, BTN_E_WITH, BTN_E_DEL):
        return await eish_choose_action(update, context)

    if text in (BTN_BOT_TOPUP, BTN_BOT_WITHDRAW):
        return await balance_menu(update, context)

    if text in (BTN_SYRIATEL, BTN_SHAM):
        flow = context.user_data.get("flow")
        if flow == "bot_topup":
            return await topup_choose_method(update, context)
        if flow == "bot_withdraw":
            return await withdraw_choose_method(update, context)
        return await show_balance_menu(update, context)

    return await main_menu(update, context)

async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await guard_user(update, context):
        return ConversationHandler.END

    uid = update.effective_user.id
    text = safe_text(update.message.text)

    if text == BTN_EISHANCY:
        e = get_eish(uid)
        extra = f"\n\n👤 حسابك الحالي: {e.get('username')}\n✅ الحالة: محفوظ" if e else ""
        await update.message.reply_text("اختر الإجراء الذي تريد تنفيذه:" + extra, reply_markup=kb_eish_actions())
        return ST_EISH_ACTION

    if text == BTN_BALANCE:
        return await show_balance_menu(update, context)

    if text == BTN_REFERRALS:
        uid = update.effective_user.id
        bot_user = (await context.bot.get_me()).username
        pts = get_points(uid)
        link = referral_link(bot_user, uid)
        msg = (
            f"🎁 نظام الإحالات\n\n"
            f"⭐ نقاطك الحالية: {pts}\n"
            f"🎯 كل إحالة = 10 نقاط\n"
            f"💳 عند 100 نقطة يمكنك الاستبدال بـ 10000\n\n"
            f"🔗 رابط الإحالة الخاص بك:\n{link}"
        )
        # show redeem button if eligible
        if pts >= 100:
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("✅ استبدال 100 نقطة = 10000", callback_data="RF:REDEEM")]])
            await update.message.reply_text(msg, reply_markup=kb)
        else:
            await update.message.reply_text(msg, reply_markup=kb_main())
        return ST_MAIN

    await update.message.reply_text("❌ الرجاء اختيار خيار صحيح", reply_markup=kb_main())
    return ST_MAIN

# ------- Eishancy -------
async def eish_choose_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await guard_user(update, context):
        return ConversationHandler.END

    uid = update.effective_user.id
    text = safe_text(update.message.text)

    if text == BTN_BACK:
        return await go_home(update, context)

    if has_pending_lock(uid):
        await update.message.reply_text(
            "⚠️ لديك طلب معلّق بالفعل.\nيرجى انتظار قبول/رفض الإدارة قبل إنشاء طلب جديد.",
            reply_markup=kb_eish_actions()
        )
        return ST_EISH_ACTION

    context.user_data.clear()
    context.user_data["flow"] = "eishancy"
    context.user_data["action"] = text

    if text == BTN_CREATE:
        if get_eish(uid):
            await update.message.reply_text("⚠️ لديك حساب إيـشانسي محفوظ بالفعل ولا يمكنك إنشاء أكثر من حساب.", reply_markup=kb_eish_actions())
            return ST_EISH_ACTION
        await update.message.reply_text("✅ اكتب اسم المستخدم المطلوب (مثال: bro_ahmad22):", reply_markup=kb_back())
        return ST_E_USER

    if text == BTN_E_TOPUP:
        if not get_eish(uid):
            await update.message.reply_text("⚠️ لازم تعمل (إنشاء حساب) إيـشانسي أولاً قبل الشحن.", reply_markup=kb_eish_actions())
            return ST_EISH_ACTION
        context.user_data["amount_min"] = 1
        await update.message.reply_text("اكتب مبلغ الشحن (بالأرقام فقط):", reply_markup=kb_back())
        return ST_AMOUNT

    if text == BTN_E_WITH:
        if not get_eish(uid):
            await update.message.reply_text("⚠️ لازم تعمل (إنشاء حساب) إيـشانسي أولاً قبل السحب.", reply_markup=kb_eish_actions())
            return ST_EISH_ACTION
        context.user_data["amount_min"] = 1
        await update.message.reply_text("اكتب المبلغ المطلوب سحبه من إيـشانسي (بالأرقام فقط):", reply_markup=kb_back())
        return ST_AMOUNT

    if text == BTN_EISH_SITE:
        await update.message.reply_text("🔗 رابط الموقع الرسمي:\nhttps://www.ichancy.com", reply_markup=kb_eish_actions())
        return ST_EISH_ACTION

    # حذف حساب إيـشانسي (يسمح للمستخدم بحذف حسابه المحفوظ)
    if text == BTN_E_DEL:
        if not get_eish(uid):
            await update.message.reply_text("ℹ️ لا يوجد لديك حساب إيـشانسي محفوظ لحذفه.", reply_markup=kb_eish_actions())
            return ST_EISH_ACTION

        context.user_data["flow"] = "eishancy"
        context.user_data["action"] = BTN_E_DEL
        e = get_eish(uid)
        context.user_data["confirm_text"] = (
            "⚠️ هل أنت متأكد أنك تريد حذف حساب إيـشانسي المحفوظ؟\n\n"
            f"👤 حسابك الحالي: {e.get('username','-')}\n\n"
            "ملاحظة: يمكنك إنشاء حساب جديد لاحقًا من داخل البوت."
        )
        await update.message.reply_text(context.user_data["confirm_text"], reply_markup=kb_confirm())
        return ST_CONFIRM

    
    await update.message.reply_text("❌ الرجاء اختيار خيار صحيح", reply_markup=kb_eish_actions())
    return ST_EISH_ACTION

async def eish_get_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await guard_user(update, context):
        return ConversationHandler.END

    uid = update.effective_user.id
    text = safe_text(update.message.text)
    if text == BTN_BACK:
        return await go_home(update, context)
    if not text:
        await update.message.reply_text("❌ اسم المستخدم غير صالح، حاول مجددًا.")
        return ST_E_USER

    # Validate format: prefix + number (example: bro_ahmad22)
    pref, num = _parse_prefix_num(text)
    if not pref:
        await update.message.reply_text(
            "❌ الاسم غير مطابق للصيغة المطلوبة.\n"
            "يرجى اختيار اسم مثل:\n"
            "bro_ahmad22\n"
            "bro_omar10\n\n"
            "اكتب اسم مستخدم جديد:",
            reply_markup=kb_back()
        )
        return ST_E_USER

    if get_eish(uid):
        await update.message.reply_text(
            "⚠️ لديك حساب إيـشانسي محفوظ بالفعل ولا يمكنك إنشاء أكثر من حساب.",
            reply_markup=kb_eish_actions()
        )
        return ST_EISH_ACTION

    assigned = await assign_pool_account(uid, text)
    if assigned:
        set_eish(uid, assigned["username"], assigned["password"])
        context.user_data["last_username"] = assigned["username"]
        context.user_data["last_password"] = assigned["password"]
        await update.message.reply_text(
            "✅ تم تجهيز حسابك بنجاح:\n\n"
            f"```\nUsername: {assigned['username']}\nPassword: {assigned['password']}\n```",
            parse_mode="Markdown",
            reply_markup=ik_copy_creds()
        )
        return ST_EISH_ACTION

    sug = suggest_pool_account(text)
    if not sug:
        pool = _load_pool()
        examples = [a.get("username") for a in pool if a.get("status") == "available" and isinstance(a.get("username"), str)]
        examples = [e for e in examples if e][:3]
        ex_txt = "\n".join(examples) if examples else "bro_ahmad22\nbro_omar10"
        await update.message.reply_text(
            "❌ الاسم الذي اخترته غير متوفر حاليًا.\n\n"
            "يرجى اختيار اسم مطابق للأسماء المتاحة، على سبيل المثال:\n"
            f"{ex_txt}\n\n"
            "اكتب اسم مستخدم جديد:",
            reply_markup=kb_back()
        )
        return ST_E_USER

    context.user_data["suggest_username"] = sug["username"]
    await update.message.reply_text(
        "❌ الاسم الذي أدخلته غير متوفر حاليًا.\n\n"
        f"✅ نقترح عليك هذا الحساب المتاح:\n{sug['username']}\n\n"
        "هل تريد اعتماده؟",
        reply_markup=ik_suggest_accept()
    )
    return ST_E_USER

async def eish_get_pass(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Password is now auto-assigned from the iChancy pool.
    await update.message.reply_text(
        "✅ النظام الجديد لا يطلب كلمة مرور. اختر (إنشاء حساب) وأدخل اسم المستخدم فقط.",
        reply_markup=kb_eish_actions()
    )
    return ST_EISH_ACTION

async def eish_topup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await guard_user(update, context):
        return ConversationHandler.END

    text = safe_text(update.message.text)
    if text == BTN_BACK:
        return await go_home(update, context)
    if not text:
        await update.message.reply_text("❌ كلمة المرور غير صالحة، حاول مجددًا.")
        return ST_E_PASS

    context.user_data["password"] = text
    context.user_data["confirm_text"] = (
        "هل تريد تأكيد طلب إنشاء الحساب؟\n\n"
        f"اسم المستخدم: {context.user_data['username']}\n"
        f"كلمة المرور: {context.user_data['password']}\n\n"
        "ملاحظة: سيتم إرسال الطلب للأدمن، وقد يقوم بتعديل البيانات قبل اعتمادها."
    )
    await update.message.reply_text(context.user_data["confirm_text"], reply_markup=kb_confirm())
    return ST_CONFIRM

# ------- Balance Menu -------
async def balance_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await guard_user(update, context):
        return ConversationHandler.END

    uid = update.effective_user.id
    text = safe_text(update.message.text)

    if text == BTN_BACK:
        return await go_home(update, context)

    if text == BTN_BOT_TOPUP:
        if has_pending_lock(uid):
            await update.message.reply_text(
                "⚠️ لديك طلب معلّق بالفعل.\nيرجى انتظار قبول/رفض الإدارة قبل إنشاء طلب جديد.",
                reply_markup=kb_balance_menu()
            )
            return ST_BAL_MENU

        context.user_data.clear()
        context.user_data["flow"] = "bot_topup"
        await update.message.reply_text("اختر طريقة الشحن:", reply_markup=kb_methods())
        return ST_TOPUP_METHOD

    if text == BTN_BOT_WITHDRAW:
        if has_pending_lock(uid):
            await update.message.reply_text(
                "⚠️ لديك طلب معلّق بالفعل.\nيرجى انتظار قبول/رفض الإدارة قبل إنشاء طلب جديد.",
                reply_markup=kb_balance_menu()
            )
            return ST_BAL_MENU

        context.user_data.clear()
        context.user_data["flow"] = "bot_withdraw"
        await update.message.reply_text("اختر طريقة السحب:", reply_markup=kb_methods())
        return ST_WITHDRAW_METHOD

    await update.message.reply_text("❌ الرجاء اختيار خيار صحيح", reply_markup=kb_balance_menu())
    return ST_BAL_MENU

# ------- Topup (bot) -------
async def topup_choose_method(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await guard_user(update, context):
        return ConversationHandler.END

    text = safe_text(update.message.text)
    if text == BTN_BACK:
        return await go_home(update, context)

    if text == BTN_SHAM:
        await update.message.reply_text(msg_support(), reply_markup=kb_balance_menu())
        return ST_BAL_MENU

    if text == BTN_SYRIATEL:
        s = get_settings()
        context.user_data["method"] = "SYRIATEL"
        context.user_data["syriatel_code"] = s["syriatel_code"]
        await update.message.reply_text(
            f"✅ قم بإرسال المبلغ عبر التحويل اليدوي إلى الكود:\n{s['syriatel_code']}\n\n"
            "الآن اكتب رقم عملية التحويل:",
            reply_markup=kb_back()
        )
        return ST_TOPUP_TXID

    await update.message.reply_text("❌ الرجاء اختيار خيار صحيح", reply_markup=kb_methods())
    return ST_TOPUP_METHOD

async def topup_get_txid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await guard_user(update, context):
        return ConversationHandler.END

    text = safe_text(update.message.text)
    if text == BTN_BACK:
        return await go_home(update, context)

    if not is_reasonable_txid(text):
        await update.message.reply_text("❌ رقم العملية غير صالح. أدخل أرقام فقط (من 6 إلى 20 رقم).")
        return ST_TOPUP_TXID

    s = get_settings()
    context.user_data["tx_id"] = text
    context.user_data["amount_min"] = int(s["min_topup"])
    await update.message.reply_text(
        f"اكتب قيمة المبلغ (بالأرقام فقط) — الحد الأدنى للشحن هو {s['min_topup']}:",
        reply_markup=kb_back()
    )
    return ST_AMOUNT

# ------- Withdraw (bot) -------
async def withdraw_choose_method(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await guard_user(update, context):
        return ConversationHandler.END

    text = safe_text(update.message.text)
    if text == BTN_BACK:
        return await go_home(update, context)

    if text == BTN_SHAM:
        await update.message.reply_text(msg_support(), reply_markup=kb_balance_menu())
        return ST_BAL_MENU

    if text == BTN_SYRIATEL:
        context.user_data["method"] = "SYRIATEL"
        await update.message.reply_text("✅ اكتب الرقم الذي سيتم إرسال المبلغ عليه (رقم سيرياتيل):", reply_markup=kb_back())
        return ST_WITHDRAW_NUMBER

    await update.message.reply_text("❌ الرجاء اختيار خيار صحيح", reply_markup=kb_methods())
    return ST_WITHDRAW_METHOD

async def withdraw_get_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await guard_user(update, context):
        return ConversationHandler.END

    text = safe_text(update.message.text)
    if text == BTN_BACK:
        return await go_home(update, context)

    if not is_reasonable_phone(text):
        await update.message.reply_text("❌ الرقم غير صالح. أدخل أرقام فقط (من 7 إلى 14 رقم).")
        return ST_WITHDRAW_NUMBER

    s = get_settings()
    context.user_data["payout_number"] = text
    context.user_data["amount_min"] = int(s["min_withdraw"])
    await update.message.reply_text(
        f"اكتب قيمة المبلغ (بالأرقام فقط) — الحد الأدنى للسحب هو {s['min_withdraw']}:",
        reply_markup=kb_back()
    )
    return ST_AMOUNT

# ------- Amount (shared) -------
async def get_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await guard_user(update, context):
        return ConversationHandler.END

    text = safe_text(update.message.text)
    if text == BTN_BACK:
        return await go_home(update, context)

    if not is_pos_int(text):
        await update.message.reply_text("❌ الرجاء إدخال مبلغ صحيح (أرقام فقط) وأكبر من 0")
        return ST_AMOUNT

    amount = int(text)
    min_needed = int(context.user_data.get("amount_min", 1))
    if amount < min_needed:
        await update.message.reply_text(f"❌ الحد الأدنى لهذه العملية هو {min_needed}. اكتب مبلغًا أكبر:")
        return ST_AMOUNT

    uid = update.effective_user.id
    flow = context.user_data.get("flow")
    action = context.user_data.get("action")

    if flow == "bot_withdraw":
        balance, _ = get_wallet(uid)
        if amount > balance:
            await update.message.reply_text(f"❌ رصيدك غير كافٍ. رصيدك الحالي: {balance}\nاكتب مبلغًا أصغر:")
            return ST_AMOUNT

    if flow == "eishancy" and action == BTN_E_TOPUP:
        balance, _ = get_wallet(uid)
        if amount > balance:
            await update.message.reply_text(f"❌ رصيدك غير كافٍ. رصيدك الحالي: {balance}\nاكتب مبلغًا أصغر:")
            return ST_AMOUNT

    context.user_data["amount"] = amount

    s = get_settings()
    if flow == "bot_topup":
        context.user_data["confirm_text"] = (
            "هل تريد تأكيد طلب الشحن؟\n\n"
            "الطريقة: سيرياتيل كاش\n"
            f"كود التحويل: {context.user_data.get('syriatel_code', s['syriatel_code'])}\n"
            f"رقم العملية: {context.user_data.get('tx_id')}\n"
            f"المبلغ: {amount}"
        )
    elif flow == "bot_withdraw":
        context.user_data["confirm_text"] = (
            "هل تريد تأكيد طلب السحب؟\n\n"
            "الطريقة: سيرياتيل كاش\n"
            f"الرقم المستلم: {context.user_data.get('payout_number')}\n"
            f"المبلغ: {amount}\n\n"
            "ملاحظة: سيتم حجز المبلغ فور الإرسال ويُعاد تلقائيًا إذا تم الرفض."
        )
    elif flow == "eishancy":
        if action == BTN_E_TOPUP:
            e = get_eish(uid)
            context.user_data["confirm_text"] = "\n".join([
                "هل تريد تأكيد شحن حساب إيـشانسي؟",
                "",
                f"حساب إيـشانسي: {e.get('username') if e else '-'}",
                f"المبلغ: {amount}",
                "",
                "ملاحظة: سيتم حجز المبلغ من رصيد البوت فور الإرسال.",
            ])
        elif action == BTN_E_WITH:
            e = get_eish(uid)
            context.user_data["confirm_text"] = "\n".join([
                "هل تريد تأكيد سحب من حساب إيـشانسي إلى رصيد البوت؟",
                "",
                f"حساب إيـشانسي: {e.get('username') if e else '-'}",
                f"المبلغ: {amount}",
                "",
                "ملاحظة: عند موافقة الأدمن سيتم إضافة المبلغ إلى رصيدك داخل البوت.",
            ])
        else:
            context.user_data["confirm_text"] = f"هل تريد تأكيد العملية بالمبلغ: {amount} ؟"
    else:
        context.user_data["confirm_text"] = f"هل تريد تأكيد العملية بالمبلغ: {amount} ؟"

    await update.message.reply_text(context.user_data["confirm_text"], reply_markup=kb_confirm())
    return ST_CONFIRM

# ------- Confirm (shared) -------
async def confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await guard_user(update, context):
        return ConversationHandler.END

    text = safe_text(update.message.text)
    if text == BTN_BACK:
        return await go_home(update, context)

    uid = update.effective_user.id

    if text == BTN_CANCEL:
        context.user_data.clear()
        await update.message.reply_text("❌ تم إلغاء العملية.", reply_markup=kb_main())
        return ST_MAIN

    if text != BTN_CONFIRM:
        await update.message.reply_text("❌ اختر (✅ تأكيد) أو (❌ إلغاء).", reply_markup=kb_confirm())
        return ST_CONFIRM

    flow = context.user_data.get("flow")
    user = update.effective_user
    # إنشاء حساب إيـشانسي (مخزون تلقائي)
    # تم استبدال النظام القديم (طلب للأدمن) بنظام مخزون حسابات.
    # المستخدم يحصل على الحساب فورًا من المخزون داخل eish_get_user / user_cb.


    # حذف حساب إيـشانسي
    if flow == "eishancy" and context.user_data.get("action") == BTN_E_DEL:
        if delete_eish(uid):
            add_history(uid, {"ts": int(time.time()), "event": "deleted", "type": "eish_delete", "order_id": "-", "amount": 0})
            await update.message.reply_text("✅ تم حذف حساب إيـشانسي المحفوظ بنجاح.", reply_markup=kb_main())
        else:
            await update.message.reply_text("ℹ️ لا يوجد لديك حساب إيـشانسي محفوظ.", reply_markup=kb_main())
        context.user_data.clear()
        return ST_MAIN

    # شحن إيـشانسي: حجز فوري + تثبيت عند القبول
    if flow == "eishancy" and context.user_data.get("action") == BTN_E_TOPUP:
        e = get_eish(uid)
        if not e:
            context.user_data.clear()
            await update.message.reply_text("⚠️ لازم تعمل (إنشاء حساب) إيـشانسي أولاً.", reply_markup=kb_main())
            return ST_MAIN

        amount = int(context.user_data.get("amount", 0))
        balance, _ = get_wallet(uid)
        if amount <= 0 or amount > balance:
            context.user_data.clear()
            await update.message.reply_text("❌ لا يمكن تنفيذ الطلب (مبلغ غير صالح أو رصيد غير كافٍ).", reply_markup=kb_main())
            return ST_MAIN

        try:
            adjust_wallet(uid, delta_balance=-amount, delta_hold=+amount)
        except ValueError:
            context.user_data.clear()
            await update.message.reply_text("❌ حدث خطأ في الرصيد. حاول لاحقًا أو تواصل مع الدعم.", reply_markup=kb_main())
            return ST_MAIN

        order_id = make_order_id("EIST")
        order = {
            "order_id": order_id,
            "type": "eish_topup",
            "status": "pending",
            "user_id": uid,
            "username": user.username or "",
            "eish_username": e.get("username", ""),
            "amount": amount,
            "created_at": int(time.time()),
        }
        add_order(order)

        if rollback_order_if_exceeds_pending(uid, order_id):
            try:
                adjust_wallet(uid, delta_hold=-amount, delta_balance=+amount)
            except Exception:
                pass
            context.user_data.clear()
            await update.message.reply_text("⚠️ لديك طلب معلّق بالفعل. تم إلغاء الطلب الجديد.", reply_markup=kb_main())
            return ST_MAIN

        add_history(uid, {"ts": int(time.time()), "event": "created", "type": "eish_topup", "order_id": order_id, "amount": amount})

        admin_msg = (
            "📩 طلب شحن حساب إيـشانسي:\n"
            f"OrderID: {order_id}\n"
            f"UserID: {uid}\n"
            f"Eishancy Username: {order['eish_username']}\n"
            f"المبلغ: {amount}\n\n"
            "تنبيه: تم حجز المبلغ من رصيد المستخدم داخل البوت."
        )
        await notify_admins(context, text=admin_msg, reply_markup=ik_order_actions(order_id, allow_edit=False), order_id=order_id)

        context.user_data.clear()
        await update.message.reply_text(msg_pending_notice() + "\n\n⏳ تم حجز المبلغ من رصيدك مؤقتًا.", reply_markup=kb_main())
        return ST_MAIN

    # سحب من إيـشانسي إلى رصيد البوت: عند القبول يضاف
    if flow == "eishancy" and context.user_data.get("action") == BTN_E_WITH:
        e = get_eish(uid)
        if not e:
            context.user_data.clear()
            await update.message.reply_text("⚠️ لازم تعمل (إنشاء حساب) إيـشانسي أولاً.", reply_markup=kb_main())
            return ST_MAIN

        amount = int(context.user_data.get("amount", 0))
        if amount <= 0:
            context.user_data.clear()
            await update.message.reply_text("❌ مبلغ غير صالح.", reply_markup=kb_main())
            return ST_MAIN

        order_id = make_order_id("EISW")
        order = {
            "order_id": order_id,
            "type": "eish_withdraw_to_bot",
            "status": "pending",
            "user_id": uid,
            "username": user.username or "",
            "eish_username": e.get("username", ""),
            "amount": amount,
            "created_at": int(time.time()),
        }
        add_order(order)

        if rollback_order_if_exceeds_pending(uid, order_id):
            context.user_data.clear()
            await update.message.reply_text("⚠️ لديك طلب معلّق بالفعل. تم إلغاء الطلب الجديد.", reply_markup=kb_main())
            return ST_MAIN

        add_history(uid, {"ts": int(time.time()), "event": "created", "type": "eish_withdraw_to_bot", "order_id": order_id, "amount": amount})

        admin_msg = (
            "📩 طلب سحب من إيـشانسي إلى رصيد البوت:\n"
            f"OrderID: {order_id}\n"
            f"UserID: {uid}\n"
            f"Eishancy Username: {order['eish_username']}\n"
            f"المبلغ: {amount}\n\n"
            "ملاحظة: عند القبول سيتم إضافة المبلغ إلى رصيد المستخدم داخل البوت."
        )
        await notify_admins(context, text=admin_msg, reply_markup=ik_order_actions(order_id, allow_edit=False), order_id=order_id)

        context.user_data.clear()
        await update.message.reply_text(msg_pending_notice(), reply_markup=kb_main())
        return ST_MAIN

    # شحن رصيد البوت
    if flow == "bot_topup":
        s = get_settings()
        order_id = make_order_id("TOP")
        tx_id = context.user_data.get("tx_id")
        amount = int(context.user_data.get("amount", 0))

        order = {
            "order_id": order_id,
            "type": "bot_topup",
            "method": "SYRIATEL",
            "status": "pending",
            "user_id": uid,
            "username": user.username or "",
            "tx_id": tx_id,
            "syriatel_code": context.user_data.get("syriatel_code", s["syriatel_code"]),
            "amount": amount,
            "created_at": int(time.time()),
        }
        add_order(order)

        if rollback_order_if_exceeds_pending(uid, order_id):
            context.user_data.clear()
            await update.message.reply_text("⚠️ لديك طلب معلّق بالفعل. تم إلغاء الطلب الجديد.", reply_markup=kb_main())
            return ST_MAIN

        add_history(uid, {"ts": int(time.time()), "event": "created", "type": "bot_topup", "order_id": order_id, "amount": amount})

        admin_text = (
            "📩 طلب شحن رصيد البوت:\n"
            f"OrderID: {order_id}\n"
            "الطريقة: سيرياتيل كاش\n"
            f"كود التحويل: {order['syriatel_code']}\n"
            f"رقم العملية: {tx_id}\n"
            f"المبلغ: {amount}\n"
            f"UserID: {uid}"
        )
        await notify_admins(context, text=admin_text, reply_markup=ik_order_actions(order_id, allow_edit=False), order_id=order_id)

        context.user_data.clear()
        await update.message.reply_text(msg_pending_notice(), reply_markup=kb_main())
        return ST_MAIN

    # سحب رصيد البوت: حجز فوري
    if flow == "bot_withdraw":
        order_id = make_order_id("WDR")
        payout = context.user_data.get("payout_number")
        amount = int(context.user_data.get("amount", 0))

        try:
            adjust_wallet(uid, delta_balance=-amount, delta_hold=+amount)
        except ValueError:
            context.user_data.clear()
            await update.message.reply_text("❌ حدث خطأ في الرصيد. حاول لاحقًا أو تواصل مع الدعم.", reply_markup=kb_main())
            return ST_MAIN

        order = {
            "order_id": order_id,
            "type": "bot_withdraw",
            "method": "SYRIATEL",
            "status": "pending",
            "user_id": uid,
            "username": user.username or "",
            "payout_number": payout,
            "amount": amount,
            "created_at": int(time.time()),
        }
        add_order(order)

        if rollback_order_if_exceeds_pending(uid, order_id):
            try:
                adjust_wallet(uid, delta_hold=-amount, delta_balance=+amount)
            except Exception:
                pass
            context.user_data.clear()
            await update.message.reply_text("⚠️ لديك طلب معلّق بالفعل. تم إلغاء الطلب الجديد.", reply_markup=kb_main())
            return ST_MAIN

        add_history(uid, {"ts": int(time.time()), "event": "created", "type": "bot_withdraw", "order_id": order_id, "amount": amount})

        admin_text = (
            "📩 طلب سحب رصيد البوت:\n"
            f"OrderID: {order_id}\n"
            "الطريقة: سيرياتيل كاش\n"
            f"الرقم المستلم: {payout}\n"
            f"المبلغ: {amount}\n"
            f"UserID: {uid}\n\n"
            "تنبيه: تم حجز المبلغ من رصيد المستخدم مباشرة."
        )
        await notify_admins(context, text=admin_text, reply_markup=ik_order_actions(order_id, allow_edit=False), order_id=order_id)

        context.user_data.clear()
        await update.message.reply_text(msg_pending_notice() + "\n\n⏳ تم حجز المبلغ من رصيدك مؤقتًا.", reply_markup=kb_main())
        return ST_MAIN

    context.user_data.clear()
    await update.message.reply_text("✅ تم.", reply_markup=kb_main())
    return ST_MAIN

# =========================
# Admin: /admin
# =========================
async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ هذا القسم للأدمن فقط.")
        return
    context.user_data.pop("admin_mode", None)
    await update.message.reply_text("لوحة الأدمن ✅", reply_markup=ik_admin_home())

# =========================
# Admin callback
# =========================
async def admin_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if not q:
        return
    await q.answer()

    if not is_admin(q.from_user.id):
        await q.message.reply_text("❌ هذا القسم للأدمن فقط.")
        return

    data = q.data or ""

    if data == "AD:HOME":
        context.user_data.pop("admin_mode", None)
        await q.message.reply_text("لوحة الأدمن ✅", reply_markup=ik_admin_home())
        return

    if data == "AD:EPOOL":
        await q.message.reply_text("🗂 إدارة مخزون حسابات إيـشانسي", reply_markup=ik_epool_home())
        return

    if data.startswith("AD:EPOOL:"):
        sub = data.split(":", 2)[2]
        if sub == "ADD":
            context.user_data["admin_mode"] = "EPOOL_ADD"
            await q.message.reply_text(
                "➕ أرسل الحسابات بالجملة بهذا الشكل (سطر لكل حساب):\n"
                "username:password\n\n"
                "مثال:\n"
                "bro_ahmad22:bbb123bb\n"
                "bro_omar10:pass999\n",
                reply_markup=ik_admin_back()
            )
            return
        if sub == "STATS":
            st = pool_stats()
            await q.message.reply_text(
                f"📊 إحصائيات المخزون\n\n"
                f"إجمالي: {st['total']}\n"
                f"متاح: {st['available']}\n"
                f"موزع: {st['assigned']}",
                reply_markup=ik_epool_home()
            )
            return
        if sub in ("AVAIL","ASSIGNED"):
            pool = _load_pool()
            want = "available" if sub == "AVAIL" else "assigned"
            items = [a for a in pool if a.get("status")==want]
            lines = []
            for a in items[:40]:
                if want=="available":
                    lines.append(f"- {a.get('username')}")
                else:
                    lines.append(f"- {a.get('username')} -> {a.get('assigned_to')}")
            body = "\n".join(lines) if lines else "لا يوجد."
            title = "📋 الحسابات المتاحة" if want=="available" else "📦 الحسابات الموزعة"
            await q.message.reply_text(title + "\n\n" + body, reply_markup=ik_epool_home())
            return

    if data.startswith("AD:PENDING:"):
        page = int(data.split(":")[-1])
        s = get_settings()
        per_page = int(s["admin_page_size"])
        orders = [o for o in list_orders() if o.get("status") == "pending"]
        start = page * per_page
        chunk = orders[start:start+per_page]
        has_prev = page > 0
        has_next = start + per_page < len(orders)

        if not chunk:
            await q.message.reply_text("لا يوجد طلبات معلّقة حاليًا ✅", reply_markup=ik_admin_home())
            return

        await q.message.reply_text(f"📥 الطلبات المعلقة — العدد: {len(orders)}", reply_markup=ik_pagination("AD:PENDING", page, has_prev, has_next))

        for o in chunk:
            t = o.get("type")
            if t == "eish_create":
                text = (
                    "🆕 طلب إنشاء إيـشانسي\n"
                    f"OrderID: {o['order_id']}\n"
                    f"UserID: {o['user_id']}\n"
                    f"Username: {o.get('eish_username','')}\n"
                    f"Password: {o.get('eish_password','')}"
                )
            elif t == "eish_topup":
                text = (
                    "💳 طلب شحن إيـشانسي\n"
                    f"OrderID: {o['order_id']}\n"
                    f"UserID: {o['user_id']}\n"
                    f"Eishancy Username: {o.get('eish_username','')}\n"
                    f"Amount: {o.get('amount')}\n"
                    "⚠️ محجوز من رصيد المستخدم"
                )
            elif t == "eish_withdraw_to_bot":
                text = (
                    "⬇️ سحب من إيـشانسي إلى رصيد البوت\n"
                    f"OrderID: {o['order_id']}\n"
                    f"UserID: {o['user_id']}\n"
                    f"Eishancy Username: {o.get('eish_username','')}\n"
                    f"Amount: {o.get('amount')}\n"
                    "✅ عند القبول سيتم إضافة الرصيد للمستخدم"
                )
            elif t == "bot_topup":
                text = (
                    "➕ شحن رصيد البوت\n"
                    f"OrderID: {o['order_id']}\n"
                    f"UserID: {o['user_id']}\n"
                    f"Amount: {o.get('amount')}\n"
                    f"TxID: {o.get('tx_id','')}"
                )
            elif t == "bot_withdraw":
                text = (
                    "➖ سحب رصيد البوت\n"
                    f"OrderID: {o['order_id']}\n"
                    f"UserID: {o['user_id']}\n"
                    f"Amount: {o.get('amount')}\n"
                    f"Payout: {o.get('payout_number','')}\n"
                    "⚠️ محجوز من رصيد المستخدم"
                )
            else:
                text = str(o)

            allow_edit = (t == "eish_create")
            await q.message.reply_text(text, reply_markup=ik_order_actions(o["order_id"], allow_edit=allow_edit))
        return

    if data.startswith("AD:LAST:"):
        page = int(data.split(":")[-1])
        per_page = 10
        orders = list_orders()
        start = page * per_page
        chunk = orders[start:start+per_page]
        has_prev = page > 0
        has_next = start + per_page < len(orders)

        if not chunk:
            await q.message.reply_text("لا يوجد طلبات بعد.", reply_markup=ik_admin_home())
            return

        lines = [f"📜 آخر الطلبات (صفحة {page+1})"]
        for o in chunk:
            lines.append(f"- {o['order_id']} | {o['type']} | {o['status']} | {o.get('amount',0)} | UID:{o['user_id']}")
        await q.message.reply_text("\n".join(lines), reply_markup=ik_pagination("AD:LAST", page, has_prev, has_next))
        return

    if data == "AD:SEARCH":
        context.user_data["admin_mode"] = "SEARCH"
        await q.message.reply_text("أرسل OrderID للبحث (مثال: TOP-... أو WDR-... أو EISC-...)", reply_markup=ik_admin_back())
        return

    if data == "AD:USER":
        context.user_data["admin_mode"] = "USER"
        await q.message.reply_text("أرسل UserID لإدارته (أرقام فقط).", reply_markup=ik_admin_back())
        return


    if data.startswith("AD:USERS:"):
        page = int(data.split(":")[-1])
        s = get_settings()
        per_page = int(s.get("admin_page_size", 6))
        uids = get_all_user_ids()

        if not uids:
            await q.message.reply_text("لا يوجد مشتركين بعد.", reply_markup=ik_admin_home())
            return

        start = page * per_page
        chunk = uids[start:start + per_page]
        has_prev = page > 0
        has_next = start + per_page < len(uids)

        rows = []
        for uid in chunk:
            b, h = get_wallet(uid)
            e = get_eish(uid)
            tag = "✅" if e else "—"
            prof = get_user_profile(uid)
            un = prof.get("username") or ""
            name = (prof.get("first_name") or "").strip()
            shown = (f"@{un} " if un else "") + (name + " " if name else "")
            rows.append([InlineKeyboardButton(f"{uid} | {shown}B:{b} H:{h} | E:{tag}", callback_data=f"AD:UINFO:{uid}:{page}")])

        nav = []
        if has_prev:
            nav.append(InlineKeyboardButton("⬅️ السابق", callback_data=f"AD:USERS:{page-1}"))
        nav.append(InlineKeyboardButton(f"📄 {page+1}", callback_data="AD:HOME"))
        if has_next:
            nav.append(InlineKeyboardButton("التالي ➡️", callback_data=f"AD:USERS:{page+1}"))
        rows.append(nav)
        rows.append([InlineKeyboardButton("⬅️ رجوع", callback_data="AD:HOME")])

        await q.message.reply_text(f"👥 سجل المشتركين — العدد: {len(uids)}", reply_markup=InlineKeyboardMarkup(rows))
        return

    if data.startswith("AD:UINFO:"):
        _, _, uid_s, page_s = data.split(":")
        uid = int(uid_s)
        page = int(page_s)

        prof = get_user_profile(uid)
        un = prof.get("username") or "-"
        fn = (prof.get("first_name") or "-")
        ln = (prof.get("last_name") or "")
        last_seen = prof.get("last_seen")
        last_seen_s = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(int(last_seen))) if last_seen else "-"
        pcount = len(pending_for_user(uid))
        admin_flag = '✅' if is_admin(uid) else '—'

        b, h = get_wallet(uid)
        banned, reason = is_banned(uid)
        e = get_eish(uid)
        e_user = e.get("username") if e else "-"

        kb_rows = [[InlineKeyboardButton("⚙️ إدارة", callback_data=f"AD:USERID:{uid}")]]
        if is_super_admin(q.from_user.id):
            kb_rows.append([InlineKeyboardButton("🛡️ تبديل أدمن", callback_data=f"AD:TOGADMIN:{uid}:{page}")])
        kb_rows.append([InlineKeyboardButton("⬅️ رجوع للسجل", callback_data=f"AD:USERS:{page}"), InlineKeyboardButton("⬅️ الرئيسية", callback_data="AD:HOME")])

        await q.message.reply_text(
            "👤 معلومات المشترك:\n"
            f"UID: {uid}\n"
            f"👤 @{un} | {fn} {ln}\n"
            f"🕒 Last seen: {last_seen_s}\n"
            f"🛡️ Admin: {admin_flag}\n"
            f"🧩 Pending orders: {pcount}\n"
            f"💰 Balance: {b}\n"
            f"⏳ Hold: {h}\n"
            f"🧾 Eishancy: {e_user}\n"
            f"🚫 Banned: {banned}\n"
            f"Reason: {reason or '-'}",
            reply_markup=InlineKeyboardMarkup(kb_rows)
        )
        return


    if data.startswith("AD:TOGADMIN:"):
        _, _, uid_s, page_s = data.split(":")
        uid = int(uid_s)
        page = int(page_s)
        if not is_super_admin(q.from_user.id):
            await q.message.reply_text("❌ هذه العملية للسوبر أدمن فقط.", reply_markup=ik_admin_home())
            return
        if is_admin(uid):
            ok = remove_admin(uid)
            msg = "✅ تم إزالة صلاحية الأدمن." if ok else "❌ لا يمكن إزالة السوبر أدمن."
        else:
            add_admin(uid)
            msg = "✅ تم تعيينه كأدمن."
        await q.message.reply_text(msg, reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ رجوع للمستخدم", callback_data=f"AD:UINFO:{uid}:{page}")],
            [InlineKeyboardButton("⬅️ رجوع للسجل", callback_data=f"AD:USERS:{page}")],
            [InlineKeyboardButton("⬅️ الرئيسية", callback_data="AD:HOME")]
        ]))
        return

        return

    if data.startswith("AD:USERID:"):
        uid = int(data.split(":")[-1])
        b, h = get_wallet(uid)
        banned, reason = is_banned(uid)
        e = get_eish(uid)
        e_name = e.get("username") if e else "-"
        context.user_data["admin_mode"] = f"USERCTX:{uid}"
        await q.message.reply_text(
            f"👤 إدارة مستخدم:\nUID: {uid}\n💰 Balance: {b}\n⏳ Hold: {h}\n"
            f"🧾 Eishancy: {e_name}\n"
            f"🚫 Banned: {banned}\nReason: {reason or '-'}\n\n"
            "أوامر تحكم:\nADJ +1000 سبب\nADJ -500 سبب\nBAN السبب\nUNBAN\nHIST",
            reply_markup=ik_admin_home()
        )
        return

    if data == "AD:STATS":
        orders = list_orders()
        pending = sum(1 for o in orders if o.get("status") == "pending")
        approved = sum(1 for o in orders if o.get("status") == "approved")
        rejected = sum(1 for o in orders if o.get("status") == "rejected")
        balances = _load_json(BALANCES_FILE)
        total_balance = sum(int(v.get("balance", 0)) for v in balances.values()) if isinstance(balances, dict) else 0
        total_hold = sum(int(v.get("hold", 0)) for v in balances.values()) if isinstance(balances, dict) else 0

        await q.message.reply_text(
            "📊 إحصائيات:\n"
            f"📥 معلّق: {pending}\n"
            f"✅ مقبول: {approved}\n"
            f"❌ مرفوض: {rejected}\n\n"
            f"💰 مجموع Balance: {total_balance}\n"
            f"⏳ مجموع Hold: {total_hold}",
            reply_markup=ik_admin_home()
        )
        return

    if data == "AD:SETTINGS":
        s = get_settings()
        context.user_data["admin_mode"] = "SETTINGS"
        await q.message.reply_text(
            "⚙️ الإعدادات الحالية:\n"
            f"- Syriatel Code: {s['syriatel_code']}\n"
            f"- Min Topup: {s['min_topup']}\n"
            f"- Min Withdraw: {s['min_withdraw']}\n"
            f"- Max Pending/User: {s['max_pending']}\n"
            f"- Admin Page Size: {s['admin_page_size']}\n\n"
            "لتعديلها أرسل:\n"
            "SET syriatel_code=23547 min_topup=15000 min_withdraw=50000 max_pending=1 admin_page_size=6",
            reply_markup=ik_admin_home()
        )
        return

    if data == "AD:EXPORT":
        s = get_settings()
        await q.message.reply_text(
            "🧾 Export (مختصر):\n"
            f"required_channel={REQUIRED_CHANNEL}\n"
            f"settings={s}\n"
            "files=[balances.json, orders.json, history.json, bans.json, admin_log.json, eishancy_accounts.json]",
            reply_markup=ik_admin_home()
        )
        return

    
    if data == "AD:BCAST":
        context.user_data["admin_mode"] = "BCAST_COPY_WAIT"
        await q.message.reply_text(
            "📣 رسالة جماعية (نسخ وإرسال)\n\n"
            "أرسل الآن *أي رسالة* تريد توزيعها (نص/صورة/فيديو/ملف...).\n"
            "سأقوم بنسخها وإرسالها إلى *غير المحظورين فقط*.\n"
            "للإلغاء أرسل: إلغاء",
            reply_markup=ik_admin_back(),
            parse_mode="Markdown"
        )
        return


    if data == "AD:BCAST:CANCEL":
        context.user_data.pop("admin_mode", None)
        context.user_data.pop("bcast_src_chat", None)
        context.user_data.pop("bcast_src_mid", None)
        await q.message.reply_text("✅ تم إلغاء الإرسال الجماعي.", reply_markup=ik_admin_home())
        return

    if data == "AD:BCAST:CONFIRM":
        if context.user_data.get("admin_mode") != "BCAST_COPY_CONFIRM":
            await q.message.reply_text("ℹ️ لا يوجد بث جاهز للتأكيد.", reply_markup=ik_admin_home())
            return
        src_chat = context.user_data.get("bcast_src_chat")
        src_mid = context.user_data.get("bcast_src_mid")
        if not src_chat or not src_mid:
            await q.message.reply_text("❌ لم أجد رسالة المصدر للبث.", reply_markup=ik_admin_home())
            context.user_data.pop("admin_mode", None)
            return

        uids = [u for u in get_all_user_ids() if not is_banned(u)[0]]
        ok = 0
        fail = 0
        for uid in uids:
            try:
                await context.bot.copy_message(chat_id=uid, from_chat_id=src_chat, message_id=src_mid)
                ok += 1
            except Exception:
                fail += 1
                try:
                    mark_user_inactive(uid)
                except Exception:
                    pass

        admin_log({"ts": int(time.time()), "admin_id": int(q.from_user.id), "action": "broadcast_copy", "ok": ok, "fail": fail})
        context.user_data.pop("admin_mode", None)
        context.user_data.pop("bcast_src_chat", None)
        context.user_data.pop("bcast_src_mid", None)
        await q.message.reply_text(f"✅ تم إرسال البث.\nنجح: {ok} | فشل: {fail}", reply_markup=ik_admin_home())
        return

# تعديل بيانات إنشاء إيـشانسي
    if data.startswith("OD:EDIT:"):
        order_id = data.split(":")[2]
        order = get_order(order_id)
        if not order:
            await q.message.reply_text("❌ الطلب غير موجود.", reply_markup=ik_admin_home())
            return
        if order.get("type") != "eish_create":
            await q.message.reply_text("ℹ️ زر التعديل مخصص لطلبات إنشاء إيـشانسي فقط.", reply_markup=ik_admin_home())
            return
        context.user_data["admin_mode"] = f"EDITCREATE:{order_id}"
        await q.message.reply_text(
            "✏️ أرسل البيانات الجديدة بهذا الشكل:\n"
            "username password\n\n"
            "مثال:\nSleman123 Pass@123",
            reply_markup=ik_admin_home()
        )
        return

    # قبول/رفض
    if data.startswith("OD:APPROVE:") or data.startswith("OD:REJECT:"):
        action, order_id = data.split(":")[1], data.split(":")[2]
        order = get_order(order_id)
        if not order:
            await q.message.reply_text("❌ الطلب غير موجود.", reply_markup=ik_admin_home())
            return
        if order.get("status") != "pending":
            await q.message.reply_text(f"ℹ️ هذا الطلب حالته: {order.get('status')}", reply_markup=ik_admin_home())
            return

        uid = int(order["user_id"])
        amount = int(order.get("amount", 0))
        now = int(time.time())
        acting_admin = int(q.from_user.id)

        banned, _ = is_banned(uid)
        if banned and action == "APPROVE":
            await q.message.reply_text("⛔ المستخدم محظور. لا يمكن القبول.", reply_markup=ik_admin_home())
            return

        # APPROVE
        if action == "APPROVE":
            if order["type"] == "bot_topup":
                adjust_wallet(uid, delta_balance=+amount)
                update_order(order_id, {"status": "approved", "approved_at": now, "admin_id": acting_admin})
                await cleanup_order_admin_messages(context, get_order(order_id) or order)
                add_history(uid, {"ts": now, "event": "approved", "type": "bot_topup", "order_id": order_id, "amount": amount})
                admin_log({"ts": now, "admin_id": acting_admin, "action": "approve_bot_topup", "order_id": order_id, "uid": uid, "amount": amount})
                b, h = get_wallet(uid)
                await q.message.reply_text(f"✅ تم قبول {order_id} وإضافة الرصيد.", reply_markup=ik_admin_home())
                await context.bot.send_message(chat_id=uid, text=f"✅ تم قبول طلب الشحن.\nالمبلغ: {amount}\nرصيدك الآن: {b}\n⏳ محجوز: {h}")
                return

            if order["type"] == "bot_withdraw":
                adjust_wallet(uid, delta_hold=-amount)
                update_order(order_id, {"status": "approved", "approved_at": now, "admin_id": acting_admin})
                await cleanup_order_admin_messages(context, get_order(order_id) or order)
                add_history(uid, {"ts": now, "event": "approved", "type": "bot_withdraw", "order_id": order_id, "amount": amount})
                admin_log({"ts": now, "admin_id": acting_admin, "action": "approve_bot_withdraw", "order_id": order_id, "uid": uid, "amount": amount})
                b, h = get_wallet(uid)
                await q.message.reply_text(f"✅ تم قبول {order_id} (تم تثبيت الخصم).", reply_markup=ik_admin_home())
                await context.bot.send_message(chat_id=uid, text=f"✅ تم قبول طلب السحب.\nالمبلغ: {amount}\nرصيدك الآن: {b}\n⏳ محجوز: {h}")
                return

            if order["type"] == "eish_topup":
                adjust_wallet(uid, delta_hold=-amount)
                update_order(order_id, {"status": "approved", "approved_at": now, "admin_id": acting_admin})
                await cleanup_order_admin_messages(context, get_order(order_id) or order)
                add_history(uid, {"ts": now, "event": "approved", "type": "eish_topup", "order_id": order_id, "amount": amount})
                admin_log({"ts": now, "admin_id": acting_admin, "action": "approve_eish_topup", "order_id": order_id, "uid": uid, "amount": amount})
                b, h = get_wallet(uid)
                await q.message.reply_text(f"✅ تم قبول {order_id} وتثبيت الخصم.", reply_markup=ik_admin_home())
                await context.bot.send_message(chat_id=uid, text=f"✅ تم قبول شحن إيـشانسي.\nالمبلغ: {amount}\nرصيدك الآن: {b}\n⏳ محجوز: {h}")
                return

            if order["type"] == "eish_withdraw_to_bot":
                adjust_wallet(uid, delta_balance=+amount)
                update_order(order_id, {"status": "approved", "approved_at": now, "admin_id": acting_admin})
                await cleanup_order_admin_messages(context, get_order(order_id) or order)
                add_history(uid, {"ts": now, "event": "approved", "type": "eish_withdraw_to_bot", "order_id": order_id, "amount": amount})
                admin_log({"ts": now, "admin_id": acting_admin, "action": "approve_eish_withdraw_to_bot", "order_id": order_id, "uid": uid, "amount": amount})
                b, h = get_wallet(uid)
                await q.message.reply_text(f"✅ تم قبول {order_id} وتمت إضافة الرصيد.", reply_markup=ik_admin_home())
                await context.bot.send_message(chat_id=uid, text=f"✅ تم قبول السحب من إيـشانسي.\nتمت إضافة: {amount}\nرصيدك الآن: {b}\n⏳ محجوز: {h}")
                return

            if order["type"] == "eish_create":
                if get_eish(uid):
                    await q.message.reply_text("⚠️ هذا المستخدم لديه حساب محفوظ بالفعل. ارفض الطلب أو احذف الحساب يدويًا.", reply_markup=ik_admin_home())
                    return

                u = safe_text(order.get("eish_username"))
                p = safe_text(order.get("eish_password"))
                if not u or not p:
                    await q.message.reply_text("❌ بيانات الحساب ناقصة. عدّل الطلب أولاً.", reply_markup=ik_admin_home())
                    return

                set_eish(uid, u, p)
                update_order(order_id, {"status": "approved", "approved_at": now, "admin_id": acting_admin})
                await cleanup_order_admin_messages(context, get_order(order_id) or order)
                add_history(uid, {"ts": now, "event": "approved", "type": "eish_create", "order_id": order_id, "amount": 0})
                admin_log({"ts": now, "admin_id": acting_admin, "action": "approve_eish_create", "order_id": order_id, "uid": uid})

                await q.message.reply_text(f"✅ تم قبول {order_id} وحفظ الحساب.", reply_markup=ik_admin_home())
                await context.bot.send_message(
                    chat_id=uid,
                    text=(
                        "✅ تم اعتماد حساب إيـشانسي الخاص بك.\n\n"
                        f"👤 Username: {u}\n"
                        f"🔑 Password: {p}\n\n"
                        "يمكنك الآن استخدام شحن/سحب إيـشانسي."
                    )
                )
                return

        # REJECT
        if action == "REJECT":
            if order["type"] in ("bot_topup", "eish_withdraw_to_bot", "eish_create"):
                update_order(order_id, {"status": "rejected", "rejected_at": now, "admin_id": acting_admin})
                await cleanup_order_admin_messages(context, get_order(order_id) or order)
                add_history(uid, {"ts": now, "event": "rejected", "type": order["type"], "order_id": order_id, "amount": amount})
                admin_log({"ts": now, "admin_id": acting_admin, "action": f"reject_{order['type']}", "order_id": order_id, "uid": uid, "amount": amount})
                await q.message.reply_text(f"❌ تم رفض {order_id}.", reply_markup=ik_admin_home())
                await context.bot.send_message(chat_id=uid, text=f"❌ تم رفض طلبك.\nOrderID: {order_id}\nإذا كنت ترى خطأ، تواصل مع الدعم.")
                return

            if order["type"] in ("bot_withdraw", "eish_topup"):
                try:
                    adjust_wallet(uid, delta_hold=-amount, delta_balance=+amount)
                except Exception:
                    pass
                update_order(order_id, {"status": "rejected", "rejected_at": now, "admin_id": ADMIN_ID})
                await cleanup_order_admin_messages(context, get_order(order_id) or order)
                add_history(uid, {"ts": now, "event": "rejected", "type": order["type"], "order_id": order_id, "amount": amount})
                admin_log({"ts": now, "admin_id": ADMIN_ID, "action": f"reject_{order['type']}", "order_id": order_id, "uid": uid, "amount": amount})
                b, h = get_wallet(uid)
                await q.message.reply_text(f"❌ تم رفض {order_id} وإرجاع الرصيد.", reply_markup=ik_admin_home())
                await context.bot.send_message(chat_id=uid, text=f"❌ تم رفض طلبك.\nتم إرجاع المبلغ: {amount}\nرصيدك الآن: {b}\n⏳ محجوز: {h}")
                return

    if data.startswith("OD:USER:"):
        order_id = data.split(":")[2]
        order = get_order(order_id)
        if not order:
            await q.message.reply_text("❌ الطلب غير موجود.", reply_markup=ik_admin_home())
            return
        uid = int(order["user_id"])
        b, h = get_wallet(uid)
        banned, reason = is_banned(uid)
        e = get_eish(uid)
        e_name = e.get("username") if e else "-"

        context.user_data["admin_mode"] = f"USERCTX:{uid}"
        await q.message.reply_text(
            f"👤 المستخدم:\nUID: {uid}\n💰 Balance: {b}\n⏳ Hold: {h}\n"
            f"🧾 Eishancy: {e_name}\n"
            f"🚫 Banned: {banned}\nReason: {reason or '-'}\n\n"
            "أوامر تحكم:\nADJ +1000 سبب\nADJ -500 سبب\nBAN السبب\nUNBAN\nHIST",
            reply_markup=ik_admin_home()
        )
        return

    if data.startswith("OD:HIST:"):
        order_id = data.split(":")[2]
        order = get_order(order_id)
        if not order:
            await q.message.reply_text("❌ الطلب غير موجود.", reply_markup=ik_admin_home())
            return
        uid = int(order["user_id"])
        hist = get_history(uid)[-10:]
        lines = [f"🧾 آخر 10 سجلات للمستخدم UID:{uid}:"]
        for e in hist:
            ts = int(e.get("ts", 0))
            dt = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts)) if ts else "-"
            lines.append(f"- {e.get('event')} | {e.get('type')} | {e.get('order_id')} | {e.get('amount')} | {dt}")
        await q.message.reply_text("\n".join(lines), reply_markup=ik_admin_home())
        return

# =========================
# Admin text handler (ONLY admin)
# =========================
async def admin_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    text = safe_text(update.message.text)
    mode = context.user_data.get("admin_mode", "")
    if not mode:
        return

    if mode == "EPOOL_ADD":
        lines = [ln for ln in text.splitlines() if ln.strip()]
        res = add_pool_bulk(lines)
        context.user_data.pop("admin_mode", None)
        st = pool_stats()
        await update.message.reply_text(
            f"✅ تم تحديث المخزون.\n\n"
            f"مضاف: {res['added']}\n"
            f"متجاهل/مكرر: {res['skipped']}\n\n"
            f"📊 الآن: إجمالي {st['total']} | متاح {st['available']} | موزع {st['assigned']}",
            reply_markup=ik_admin_home()
        )
        return

    if mode.startswith("EDITCREATE:"):
        order_id = mode.split(":", 1)[1]
        order = get_order(order_id)
        if not order or order.get("type") != "eish_create" or order.get("status") != "pending":
            context.user_data.pop("admin_mode", None)
            await update.message.reply_text("❌ لا يمكن تعديل هذا الطلب.", reply_markup=ik_admin_home())
            return

        parts = text.split()
        if len(parts) < 2:
            await update.message.reply_text("❌ اكتب بالشكل: username password", reply_markup=ik_admin_home())
            return

        new_user = parts[0].strip()
        new_pass = " ".join(parts[1:]).strip()

        update_order(order_id, {"eish_username": new_user, "eish_password": new_pass})
        admin_log({"ts": int(time.time()), "admin_id": ADMIN_ID, "action": "edit_eish_create", "order_id": order_id})

        uid = int(order["user_id"])
        await context.bot.send_message(
            chat_id=uid,
            text=(
                "✏️ تم تعديل بيانات حساب إيـشانسي من قبل الإدارة.\n\n"
                f"👤 Username: {new_user}\n"
                f"🔑 Password: {new_pass}\n\n"
                "سيتم اعتماد هذه البيانات عند الموافقة النهائية."
            )
        )

        context.user_data.pop("admin_mode", None)

        # عرض ملخص محدث للأدمن بعد التعديل
        await update.message.reply_text(
            "✅ تم تحديث بيانات طلب إنشاء إيـشانسي بنجاح.\n\n"
            f"OrderID: {order_id}\n"
            f"UserID: {uid}\n"
            f"Username: {new_user}\n"
            f"Password: {new_pass}\n\n"
            "الآن اضغط (✅ قبول) لاعتماد الحساب أو (❌ رفض).",
            reply_markup=ik_order_actions(order_id, allow_edit=True)
        )
        return

    
        # BROADCAST
    if mode == "BCAST_COPY_WAIT":
        if text.strip() in ("إلغاء", "الغاء", "cancel", "CANCEL"):
            context.user_data.pop("admin_mode", None)
            await update.message.reply_text("✅ تم إلغاء الإرسال الجماعي.", reply_markup=ik_admin_home())
            return

        # نأخذ الرسالة كما هي ونجهز معاينة/تأكيد
        src_chat = update.effective_chat.id
        src_mid = update.effective_message.message_id
        context.user_data["bcast_src_chat"] = src_chat
        context.user_data["bcast_src_mid"] = src_mid
        context.user_data["admin_mode"] = "BCAST_COPY_CONFIRM"

        uids = [u for u in get_all_user_ids() if not is_banned(u)[0]]
        await update.message.reply_text(
            f"📣 معاينة البث\n\n"
            f"سيتم إرسال *نسخة* من الرسالة أعلاه إلى: *{len(uids)}* مستخدم (غير محظور).\n\n"
            f"اضغط (✅ إرسال) للبدء أو (❌ إلغاء).",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ إرسال", callback_data="AD:BCAST:CONFIRM")],
                [InlineKeyboardButton("❌ إلغاء", callback_data="AD:BCAST:CANCEL")],
                [InlineKeyboardButton("⬅️ الرئيسية", callback_data="AD:HOME")],
            ]),
            parse_mode="Markdown"
        )
        return

    if mode == "SETTINGS" and text.upper().startswith("SET "):
        parts = text[4:].split()
        updates = {}
        for p in parts:
            if "=" not in p:
                continue
            k, v = p.split("=", 1)
            k, v = k.strip(), v.strip()
            if k in (
                "min_topup",
                "min_withdraw",
                "max_pending",
                "admin_page_size",
            ) and v.isdigit():
                updates[k] = int(v)
            elif k == "syriatel_code":
                updates[k] = v
        s = set_settings(updates)
        admin_log({"ts": int(time.time()), "admin_id": ADMIN_ID, "action": "update_settings", "updates": updates})
        context.user_data.pop("admin_mode", None)
        await update.message.reply_text(f"✅ تم تحديث الإعدادات:\n{s}", reply_markup=ik_admin_home())
        return

    if mode == "SEARCH":
        order = get_order(text)
        context.user_data.pop("admin_mode", None)
        if not order:
            await update.message.reply_text("❌ لم يتم العثور على OrderID.", reply_markup=ik_admin_home())
            return
        allow_edit = (order.get("status") == "pending" and order.get("type") == "eish_create")
        await update.message.reply_text(
            f"🔎 نتيجة البحث:\n{order}",
            reply_markup=ik_order_actions(order["order_id"], allow_edit=allow_edit) if order.get("status") == "pending" else ik_admin_home()
        )
        return

    if mode == "USER":
        if not text.isdigit():
            await update.message.reply_text("❌ أرسل UserID أرقام فقط.", reply_markup=ik_admin_home())
            return
        uid = int(text)
        b, h = get_wallet(uid)
        banned, reason = is_banned(uid)
        e = get_eish(uid)
        e_name = e.get("username") if e else "-"
        context.user_data["admin_mode"] = f"USERCTX:{uid}"
        await update.message.reply_text(
            f"👤 إدارة مستخدم:\nUID: {uid}\n💰 Balance: {b}\n⏳ Hold: {h}\n"
            f"🧾 Eishancy: {e_name}\n"
            f"🚫 Banned: {banned}\nReason: {reason or '-'}\n\n"
            "أوامر:\nADJ +1000 سبب\nADJ -500 سبب\nBAN السبب\nUNBAN\nHIST",
            reply_markup=ik_admin_home()
        )
        return

    if mode.startswith("USERCTX:"):
        uid = int(mode.split(":")[1])
        upper = text.upper()

        if upper == "HIST":
            hist = get_history(uid)[-10:]
            lines = [f"🧾 آخر 10 سجلات UID:{uid}:"]
            for e in hist:
                ts = int(e.get("ts", 0))
                dt = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts)) if ts else "-"
                lines.append(f"- {e.get('event')} | {e.get('type')} | {e.get('order_id')} | {e.get('amount')} | {dt}")
            await update.message.reply_text("\n".join(lines), reply_markup=ik_admin_home())
            return

        if upper.startswith("BAN "):
            reason = text[4:].strip() or "بدون سبب"
            ban_user(uid, reason)
            admin_log({"ts": int(time.time()), "admin_id": ADMIN_ID, "action": "ban", "uid": uid, "reason": reason})
            await update.message.reply_text(f"⛔ تم حظر UID:{uid}\nالسبب: {reason}", reply_markup=ik_admin_home())
            return

        if upper == "UNBAN":
            unban_user(uid)
            admin_log({"ts": int(time.time()), "admin_id": ADMIN_ID, "action": "unban", "uid": uid})
            await update.message.reply_text(f"✅ تم فك الحظر عن UID:{uid}", reply_markup=ik_admin_home())
            return

        if upper.startswith("ADJ "):
            rest = text[4:].strip()
            parts = rest.split(maxsplit=1)
            if not parts:
                await update.message.reply_text("❌ مثال: ADJ +1000 سبب", reply_markup=ik_admin_home())
                return
            try:
                delta = int(parts[0])
            except Exception:
                await update.message.reply_text("❌ اكتب رقم صحيح مثل +1000 أو -500", reply_markup=ik_admin_home())
                return
            reason = parts[1] if len(parts) > 1 else "تعديل يدوي"
            b_before, h_before = get_wallet(uid)
            try:
                b_after, h_after = adjust_wallet(uid, delta_balance=delta)
            except ValueError:
                await update.message.reply_text("❌ لا يمكن تعديل الرصيد ليصبح سالب.", reply_markup=ik_admin_home())
                return
            now = int(time.time())
            add_history(uid, {"ts": now, "event": "admin_adjust", "type": "wallet", "order_id": "-", "amount": delta, "reason": reason})

            admin_log({"ts": now, "admin_id": update.effective_user.id if update.effective_user else 0, "action": "adjust_balance", "uid": uid, "delta": delta, "reason": reason})

            await update.message.reply_text(
                "✅ تم تعديل الرصيد.\n"
                f"قبل: Balance={b_before}, Hold={h_before}\n"
                f"بعد:  Balance={b_after}, Hold={h_after}\n"
                f"السبب: {reason}",
                reply_markup=ik_admin_home()
            )
            return

        await update.message.reply_text("ℹ️ أمر غير معروف. استخدم: ADJ / BAN / UNBAN / HIST", reply_markup=ik_admin_home())
        return

# =========================
# Eishancy pool (pre-created accounts)
# =========================
_POOL_LOCK = asyncio.Lock()

def _load_pool() -> List[Dict[str, Any]]:
    data = _load_json(EISH_POOL_FILE)
    if isinstance(data, list):
        return data
    return []

def _save_pool(pool: List[Dict[str, Any]]) -> None:
    _save_json(EISH_POOL_FILE, pool)

def pool_stats() -> Dict[str, int]:
    pool = _load_pool()
    available = sum(1 for a in pool if a.get("status") == "available")
    assigned = sum(1 for a in pool if a.get("status") == "assigned")
    return {"total": len(pool), "available": available, "assigned": assigned}

def add_pool_bulk(lines: List[str]) -> Dict[str, int]:
    """lines: ['user:pass', ...]"""
    pool = _load_pool()
    existing = { (a.get("username") or "").lower() for a in pool }
    added=0
    skipped=0
    for ln in lines:
        ln=ln.strip()
        if not ln or ln.startswith("#"):
            continue
        if ":" not in ln:
            skipped += 1
            continue
        u,p = ln.split(":",1)
        u=u.strip()
        p=p.strip()
        if not u or not p:
            skipped += 1
            continue
        if u.lower() in existing:
            skipped += 1
            continue
        pool.append({"username": u, "password": p, "status": "available", "assigned_to": None, "assigned_at": None})
        existing.add(u.lower())
        added += 1
    _save_pool(pool)
    return {"added": added, "skipped": skipped}

def _parse_prefix_num(s: str):
    m = re.match(r"^([a-zA-Z_]+)(\d+)$", s)
    if not m:
        return None, None
    return m.group(1), int(m.group(2))

def suggest_pool_account(desired_username: str) -> Dict[str, Any] | None:
    """Return best available account dict (not reserved)."""
    pool = _load_pool()
    pref, num = _parse_prefix_num(desired_username)
    if not pref:
        return None
    candidates = [a for a in pool if a.get("status") == "available" and str(a.get("username","")).startswith(pref)]
    if not candidates:
        return None
    # compute closest by number if possible; else first
    def keyfn(a):
        ap, an = _parse_prefix_num(str(a.get("username","")))
        if an is None:
            return (10**9, str(a.get("username","")))
        return (abs(an - num), an)
    candidates.sort(key=keyfn)
    return candidates[0]

async def assign_pool_account(uid: int, username: str) -> Dict[str, Any] | None:
    async with _POOL_LOCK:
        pool = _load_pool()
        # find exact available username
        for a in pool:
            if str(a.get("username","")) == username and a.get("status") == "available":
                a["status"] = "assigned"
                a["assigned_to"] = int(uid)
                a["assigned_at"] = int(time.time())
                _save_pool(pool)
                return a
        return None



# =========================
# Build app
# =========================
def build_app():
    _ensure_data_files()
    get_settings()

    app = ApplicationBuilder().token(TOKEN).build()

    # استثناء رسائل الأدمن من محادثة المستخدم حتى لا تتعارض مع أوامر لوحة الأدمن
    user_text_filter = (filters.TEXT & ~filters.COMMAND & ~filters.User(ADMIN_ID))

    # ✅ زر (تحقق من الاشتراك)
    app.add_handler(CallbackQueryHandler(cb_check_join, pattern=f"^{CB_CHECK_JOIN}$"))

    # Conversation
    user_conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            ST_MAIN: [MessageHandler(user_text_filter, smart_router)],
            ST_EISH_ACTION: [MessageHandler(user_text_filter, eish_choose_action)],
            ST_E_USER: [MessageHandler(user_text_filter, eish_get_user)],
            ST_E_PASS: [MessageHandler(user_text_filter, eish_get_pass)],
            ST_BAL_MENU: [MessageHandler(user_text_filter, balance_menu)],
            ST_TOPUP_METHOD: [MessageHandler(user_text_filter, topup_choose_method)],
            ST_TOPUP_TXID: [MessageHandler(user_text_filter, topup_get_txid)],
            ST_WITHDRAW_METHOD: [MessageHandler(user_text_filter, withdraw_choose_method)],
            ST_WITHDRAW_NUMBER: [MessageHandler(user_text_filter, withdraw_get_number)],
            ST_AMOUNT: [MessageHandler(user_text_filter, get_amount)],
            ST_CONFIRM: [MessageHandler(user_text_filter, confirm)],
        },
        fallbacks=[
            CommandHandler("start", start),
            MessageHandler(filters.Regex(f"^{BTN_BACK}$") & ~filters.User(ADMIN_ID), go_home),
        ],
        allow_reentry=True,
    )
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, admin_text), group=0)

    app.add_handler(user_conv, group=1)

    # Admin
    app.add_handler(CommandHandler("admin", cmd_admin))

    # ✅ نخلي admin_cb يستقبل فقط كولباكات الأدمن الخاصة
    app.add_handler(CallbackQueryHandler(admin_cb, pattern=r"^(AD:|OD:)"))

    
    # (اختياري) حدث ترك القناة — يحتاج البوت أدمن بالقناة
    app.add_handler(ChatMemberHandler(on_channel_member_update, ChatMemberHandler.CHAT_MEMBER))

    return app

def main():
    if TOKEN == "PUT_YOUR_BOT_TOKEN_HERE" or not TOKEN.strip():
        print("ضع توكن البوت داخل BOT_TOKEN (env) أو داخل TOKEN في الكود.")
        return
    app = build_app()
    print("البوت يعمل الآن...")
    app.run_polling()

if __name__ == "__main__":
    main()
