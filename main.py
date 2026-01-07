# -*- coding: utf-8 -*-
"""
بوت الخدمات المالية المتكامل مع التحقق الآلي من سيرياتيل كاش
نسخة Railway الجاهزة مع نظام منع التكرار
"""

import json
import os
import shutil
import tempfile
import time
import threading
from datetime import datetime
import zipfile
from difflib import SequenceMatcher
import asyncio
import re
import random
import sys
from typing import Dict, Any, Optional, List, Tuple

# === مكتبات التحقق الآلي ===
try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    import undetected_chromedriver as uc
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    print("⚠️ تنبيه: Selenium غير مثبت. سيتم تعطيل التحقق الآلي.")

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
TOKEN = os.getenv("BOT_TOKEN", "").strip()
if not TOKEN:
    raise RuntimeError("❌ BOT_TOKEN مطلوب في Environment Variables")

SUPER_ADMIN_ID = int(os.getenv("SUPER_ADMIN_ID", "0") or "0")
if not SUPER_ADMIN_ID:
    raise RuntimeError("❌ SUPER_ADMIN_ID مطلوب")

DATA_DIR = os.getenv("DATA_DIR", "/app/data")
os.makedirs(DATA_DIR, exist_ok=True)

# تعريفات الملفات
ADMINS_FILE = os.path.join(DATA_DIR, "admins.json")
USERS_FILE = os.path.join(DATA_DIR, "users.json")
REQUIRED_CHANNEL = os.getenv("REQUIRED_CHANNEL", "@broichancy")
REQUIRED_CHANNEL_URL = "https://t.me/broichancy"
BALANCES_FILE = os.path.join(DATA_DIR, "balances.json")
ORDERS_FILE = os.path.join(DATA_DIR, "orders.json")
HISTORY_FILE = os.path.join(DATA_DIR, "history.json")
ADMINLOG_FILE = os.path.join(DATA_DIR, "admin_log.json")
BANS_FILE = os.path.join(DATA_DIR, "bans.json")
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")
MAINT_FILE = os.path.join(DATA_DIR, "maintenance.json")
BACKUP_DIR = os.path.join(DATA_DIR, "backups")
EISH_FILE = os.path.join(DATA_DIR, "eishancy_accounts.json")
EISH_POOL_FILE = os.path.join(DATA_DIR, "eishancy_pool.json")
REF_FILE = os.path.join(DATA_DIR, "referrals.json")
SYRIATEL_ACCOUNTS_FILE = os.path.join(DATA_DIR, "syriatel_accounts.json")
VERIFIED_TX_FILE = os.path.join(DATA_DIR, "verified_transactions.json")

os.makedirs(BACKUP_DIR, exist_ok=True)

DEFAULT_SETTINGS = {
    "syriatel_code": "23547",
    "syriatel_codes": ["23547"],
    "min_topup": 15000,
    "min_withdraw": 50000,
    "max_pending": 1,
    "admin_page_size": 6,
    "auto_verify_enabled": False,
    "auto_verify_interval": 300,
    "max_auto_amount": 100000,
    "syriatel_username": "",
    "syriatel_password": "",
    "syriatel_cash_code": "23547",
    "auto_login_enabled": False
}

# =========================
# دوال المساعدة للـ JSON
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
        (MAINT_FILE, {"active": False, "since": None, "by": None}),
        (EISH_FILE, {}),
        (EISH_POOL_FILE, []),
        (REF_FILE, {}),
        (USERS_FILE, {}),
        (ADMINS_FILE, {"super_admin": SUPER_ADMIN_ID, "admins": [SUPER_ADMIN_ID]}),
        (SYRIATEL_ACCOUNTS_FILE, []),
        (VERIFIED_TX_FILE, {}),
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
# إعدادات
# =========================
def get_settings() -> Dict[str, Any]:
    s = _load_json(SETTINGS_FILE)
    merged = DEFAULT_SETTINGS.copy()
    if isinstance(s, dict):
        merged.update(s)
    return merged

def set_settings(updates: Dict[str, Any]) -> Dict[str, Any]:
    s = get_settings()
    s.update(updates)
    _save_json(SETTINGS_FILE, s)
    return s

# =========================
# أدمن
# =========================
def get_admin_ids() -> List[int]:
    obj = _load_json(ADMINS_FILE)
    if not isinstance(obj, dict):
        obj = {"super_admin": SUPER_ADMIN_ID, "admins": [SUPER_ADMIN_ID]}
    obj.setdefault("super_admin", SUPER_ADMIN_ID)
    obj.setdefault("admins", [SUPER_ADMIN_ID])
    return [int(x) for x in obj.get("admins", [])]

ADMIN_IDS = get_admin_ids()

def is_admin(uid: int) -> bool:
    return uid in set(get_admin_ids())

def is_super_admin(uid: int) -> bool:
    obj = _load_json(ADMINS_FILE)
    try:
        return int(uid) == int(obj.get("super_admin", SUPER_ADMIN_ID))
    except Exception:
        return False

async def notify_admins(context: ContextTypes.DEFAULT_TYPE, text: str, reply_markup=None, order_id: str | None = None):
    admin_msgs = []
    for aid in ADMIN_IDS:
        try:
            msg = await context.bot.send_message(chat_id=aid, text=text, reply_markup=reply_markup)
            admin_msgs.append({"chat_id": aid, "message_id": msg.message_id})
        except Exception:
            pass
    if order_id and admin_msgs:
        order = get_order(order_id) or {}
        existing = order.get("admin_msgs") or []
        if isinstance(existing, list):
            existing.extend(admin_msgs)
        else:
            existing = admin_msgs
        update_order(order_id, {"admin_msgs": existing})

# =========================
# محفظة
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
# مستخدمين
# =========================
def get_user_profile(uid: int) -> Dict[str, Any]:
    users = _load_json(USERS_FILE)
    return users.get(str(uid), {})

def upsert_user_profile(user) -> None:
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

def get_all_user_ids() -> List[int]:
    uids: set[int] = set()
    def add_keys(d):
        if isinstance(d, dict):
            for k in d.keys():
                if str(k).isdigit():
                    uids.add(int(k))
    add_keys(_load_json(BALANCES_FILE))
    add_keys(_load_json(USERS_FILE))
    add_keys(_load_json(HISTORY_FILE))
    add_keys(_load_json(EISH_FILE))
    add_keys(_load_json(BANS_FILE))
    orders = _load_json(ORDERS_FILE)
    if isinstance(orders, dict):
        for o in orders.values():
            try:
                uids.add(int(o.get("user_id")))
            except Exception:
                pass
    uids.discard(SUPER_ADMIN_ID)
    return sorted(uids)

# =========================
# طلبات
# =========================
def make_order_id(prefix: str) -> str:
    return f"{prefix}-{int(time.time() * 1000)}-{random.randint(1000, 9999)}"

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

# =========================
# إدارة العمليات المحققة (منع التكرار)
# =========================
class VerifiedTransactionsManager:
    def __init__(self):
        self.verified_tx = self.load_verified_transactions()
    
    def load_verified_transactions(self):
        data = _load_json(VERIFIED_TX_FILE)
        if not isinstance(data, dict):
            return {}
        return data
    
    def save_verified_transactions(self):
        _save_json(VERIFIED_TX_FILE, self.verified_tx)
    
    def is_transaction_verified(self, transaction_id, amount=None, cash_code=None):
        tx_data = self.verified_tx.get(transaction_id)
        if not tx_data:
            return False
        if amount and tx_data.get("amount") != amount:
            return False
        if cash_code and tx_data.get("cash_code") != cash_code:
            return False
        return True
    
    def add_verified_transaction(self, transaction_id, amount, cash_code, user_id, order_id):
        self.verified_tx[transaction_id] = {
            "transaction_id": transaction_id,
            "amount": amount,
            "cash_code": cash_code,
            "user_id": user_id,
            "order_id": order_id,
            "verified_at": int(time.time()),
            "verified_by": "auto_system",
            "status": "verified"
        }
        self.save_verified_transactions()
    
    def get_transaction_info(self, transaction_id):
        return self.verified_tx.get(transaction_id)

tx_manager = VerifiedTransactionsManager()

async def check_transaction_duplicate(transaction_id, amount, cash_code, user_id):
    if tx_manager.is_transaction_verified(transaction_id, amount, cash_code):
        return {
            "allowed": False,
            "reason": "تم التحقق من هذا الرقم مسبقاً",
            "existing_data": tx_manager.get_transaction_info(transaction_id)
        }
    return {"allowed": True}

# =========================
# نظام الدخول المتخفي إلى سيرياتيل
# =========================
class StealthSyriatelLogin:
    def __init__(self):
        self.driver = None
        self.logged_in = False
    
    async def init_stealth_driver(self):
        if not SELENIUM_AVAILABLE:
            return False
        try:
            options = uc.ChromeOptions()
            options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('--window-size=1920,1080')
            options.add_argument('--disable-blink-features=AutomationControlled')
            
            if os.path.exists('/usr/bin/google-chrome-stable'):
                options.binary_location = '/usr/bin/google-chrome-stable'
            
            user_agents = [
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            ]
            selected_agent = random.choice(user_agents)
            options.add_argument(f'--user-agent={selected_agent}')
            
            self.driver = uc.Chrome(options=options)
            return True
        except Exception as e:
            print(f"❌ فشل تهيئة المتصفح: {e}")
            return False
    
    async def human_like_login(self, username, password):
        if not self.driver:
            if not await self.init_stealth_driver():
                return False
        try:
            print("🔑 جاري تسجيل الدخول إلى سيرياتيل...")
            self.driver.get("https://cash.syriatel.sy/")
            await asyncio.sleep(5)
            
            try:
                username_field = self.driver.find_element(By.NAME, "username")
                password_field = self.driver.find_element(By.NAME, "password")
                username_field.send_keys(username)
                await asyncio.sleep(1)
                password_field.send_keys(password)
                await asyncio.sleep(1)
                
                login_button = self.driver.find_element(By.XPATH, "//button[@type='submit']")
                login_button.click()
                await asyncio.sleep(8)
                
                current_url = self.driver.current_url
                page_source = self.driver.page_source.lower()
                
                if "dashboard" in current_url or "home" in current_url or "مرحباً" in page_source:
                    self.logged_in = True
                    print("✅ تم تسجيل الدخول بنجاح")
                    return True
                return False
            except Exception as e:
                print(f"❌ خطأ في عملية الدخول: {e}")
                return False
        except Exception as e:
            print(f"❌ خطأ عام في الدخول: {e}")
            return False
    
    async def stealth_check_transaction(self, transaction_id, amount, cash_code):
        if not self.logged_in or not self.driver:
            return False
        try:
            self.driver.get("https://cash.syriatel.sy/transactions")
            await asyncio.sleep(5)
            
            page_source = self.driver.page_source
            patterns = [
                rf'{transaction_id}',
                rf'رقم العملية[\s:]*{transaction_id}',
                rf'{amount}',
                rf'مبلغ[\s:]*{amount}',
            ]
            
            for pattern in patterns:
                if re.search(pattern, page_source, re.IGNORECASE):
                    print(f"✅ تم العثور على التحويل: {transaction_id}")
                    return True
            
            return False
        except Exception as e:
            print(f"❌ خطأ في البحث عن التحويل: {e}")
            return False
    
    async def logout(self):
        if self.driver and self.logged_in:
            try:
                self.driver.get("https://cash.syriatel.sy/logout")
                await asyncio.sleep(3)
            except:
                pass
            self.logged_in = False
    
    async def close(self):
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
            self.driver = None
            self.logged_in = False

stealth_login = StealthSyriatelLogin()

# =========================
# معالجة التحقق الناجح
# =========================
async def process_verified_transaction(order, verification_method="auto"):
    order_id = order.get("order_id")
    tx_id = order.get("tx_id", "").strip()
    amount = order.get("amount", 0)
    cash_code = order.get("syriatel_code", "23547")
    user_id = order.get("user_id")
    
    if not tx_id:
        return False
    
    # إضافة العملية إلى السجل المحققة
    tx_manager.add_verified_transaction(
        transaction_id=tx_id,
        amount=amount,
        cash_code=cash_code,
        user_id=user_id,
        order_id=order_id
    )
    
    # تحديث حالة الطلب
    update_order(order_id, {
        "status": "completed",
        "verified_at": int(time.time()),
        "verified_by": verification_method,
        "duplicate_check": "passed"
    })
    
    # تحديث رصيد المستخدم
    try:
        balance, hold = get_wallet(user_id)
        set_wallet(user_id, balance + amount, hold)
    except Exception as e:
        print(f"❌ فشل تحديث الرصيد: {e}")
        return False
    
    return True

# =========================
# مهمة التحقق الآلي المتخفي
# =========================
async def stealth_auto_verification_job(context: ContextTypes.DEFAULT_TYPE):
    username = os.getenv("SYRIATEL_USERNAME", "").strip()
    password = os.getenv("SYRIATEL_PASSWORD", "").strip()
    cash_code = os.getenv("SYRIATEL_CASH_CODE", "23547").strip()
    
    if not username or not password:
        return
    
    if os.getenv("AUTO_LOGIN_ENABLED", "false").lower() != "true":
        return
    
    print("🔍 بدء جولة التحقق الآلي...")
    
    # جلب الطلبات المعلقة
    orders = _load_json(ORDERS_FILE)
    pending_orders = {k: v for k, v in orders.items() 
                     if v.get("status") == "pending" 
                     and v.get("type") == "bot_topup"
                     and v.get("created_at", 0) > time.time() - 86400}
    
    if not pending_orders:
        return
    
    max_checks = int(os.getenv("MAX_CHECKS_PER_SESSION", "5"))
    orders_to_check = list(pending_orders.items())[:max_checks]
    
    # محاولة الدخول
    if not stealth_login.logged_in:
        print("🔑 محاولة الدخول إلى سيرياتيل...")
        login_success = await stealth_login.human_like_login(username, password)
        if not login_success:
            return
    
    # التحقق من كل طلب
    verified_count = 0
    for order_id, order in orders_to_check:
        try:
            transaction_id = order.get("tx_id", "").strip()
            amount = order.get("amount", 0)
            
            if not transaction_id or amount <= 0:
                continue
            
            # فحص التكرار أولاً
            if tx_manager.is_transaction_verified(transaction_id, amount, cash_code):
                print(f"🚨 تخطي: {transaction_id} محققة مسبقاً")
                update_order(order_id, {
                    "status": "rejected",
                    "rejected_at": int(time.time()),
                    "reject_reason": "تكرار رقم العملية"
                })
                continue
            
            # البحث في سيرياتيل
            print(f"🔎 فحص: {transaction_id}")
            found = await stealth_login.stealth_check_transaction(transaction_id, amount, cash_code)
            
            if found:
                success = await process_verified_transaction(order, "stealth_auto")
                if success:
                    # إشعار المستخدم
                    try:
                        await context.bot.send_message(
                            chat_id=order.get("user_id"),
                            text=f"✅ تم التحقق من تحويلك!\nتم إضافة {amount} لرصيدك."
                        )
                    except:
                        pass
                    
                    verified_count += 1
                    print(f"✅ تم التحقق: {order_id}")
            
            await asyncio.sleep(random.uniform(2, 4))
            
        except Exception as e:
            print(f"❌ خطأ: {e}")
    
    if verified_count > 0:
        print(f"🎯 تم التحقق من {verified_count} طلب")
    
    await stealth_login.logout()

# =========================
# دوال iChancy Pool
# =========================
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

# =========================
# دوال إضافية
# =========================
def is_banned(uid: int) -> Tuple[bool, str]:
    bans = _load_json(BANS_FILE)
    info = bans.get(str(uid), {})
    if info.get("banned"):
        return True, info.get("reason", "")
    return False, ""

def add_history(uid: int, event: Dict[str, Any]):
    hist = _load_json(HISTORY_FILE)
    key = str(uid)
    hist.setdefault(key, [])
    hist[key].append(event)
    hist[key] = hist[key][-200:]
    _save_json(HISTORY_FILE, hist)

def safe_text(s: str) -> str:
    return (s or "").strip()

def is_pos_int(s: str) -> bool:
    return s.isdigit() and int(s) > 0

def is_reasonable_txid(s: str) -> bool:
    return s.isdigit() and 6 <= len(s) <= 20

def is_reasonable_phone(s: str) -> bool:
    return s.isdigit() and 7 <= len(s) <= 14

# =========================
# حالات المحادثة
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
    ST_TOPUP_CODE,
    ST_CONFIRM,
    ST_DUPLICATE_CHECK,
) = range(13)

# =========================
# أزرار
# =========================
BTN_EISHANCY = "حساب ايشانسي"
BTN_BALANCE = "رصيدي"
BTN_REFERRALS = "🎁 الإحالات"
BTN_BACK = "⬅️ رجوع"
BTN_MY_EISH = "👤 حسابي"
BTN_CREATE = "🆕 إنشاء حساب"
BTN_E_TOPUP = "💳 شحن إيـشانسي"
BTN_E_WITH = "💸 سحب من إيـشانسي"
BTN_E_DEL = "🗑️ حذف الحساب"
BTN_EISH_SITE = "🌐 موقع iChancy"
BTN_BOT_TOPUP = "شحن رصيد في البوت"
BTN_BOT_WITHDRAW = "سحب رصيد من البوت"
BTN_SYRIATEL = "سيرياتيل كاش"
BTN_SHAM = "شام كاش"
BTN_CONFIRM = "✅ تأكيد"
BTN_CANCEL = "❌ إلغاء"

# =========================
# لوحات المفاتيح
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
            [KeyboardButton(BTN_MY_EISH), KeyboardButton(BTN_CREATE)],
            [KeyboardButton(BTN_E_TOPUP), KeyboardButton(BTN_E_WITH)],
            [KeyboardButton(BTN_E_DEL), KeyboardButton(BTN_EISH_SITE)],
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
# دوال التحقق من الاشتراك
# =========================
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
            f"⚠️ اشترك بالقناة أولاً: {REQUIRED_CHANNEL}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ اشترك", url=REQUIRED_CHANNEL_URL)],
                [InlineKeyboardButton("🔄 تحقق", callback_data="JOIN:CHECK")]
            ])
        )
        return False
    return True

# =========================
# معالجات المستخدم الرئيسية
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "أهلًا وسهلاً! اختر من القائمة:",
        reply_markup=kb_main()
    )
    return ST_MAIN

async def go_home(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("✅ القائمة الرئيسية", reply_markup=kb_main())
    return ST_MAIN

async def smart_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = safe_text(update.message.text)
    uid = update.effective_user.id
    
    if text == BTN_BACK:
        return await go_home(update, context)
    
    if text == BTN_EISHANCY:
        e = _load_json(EISH_FILE).get(str(uid))
        extra = f"\nحسابك: {e.get('username')}" if e else ""
        await update.message.reply_text("اختر إجراء iChancy:" + extra, reply_markup=kb_eish_actions())
        return ST_EISH_ACTION
    
    if text == BTN_BALANCE:
        b, h = get_wallet(uid)
        await update.message.reply_text(f"💰 رصيدك: {b}\n⏳ محجوز: {h}", reply_markup=kb_balance_menu())
        return ST_BAL_MENU
    
    await update.message.reply_text("❌ خيار غير صحيح", reply_markup=kb_main())
    return ST_MAIN

# =========================
# معالجات الشحن
# =========================
async def balance_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = safe_text(update.message.text)
    
    if text == BTN_BACK:
        return await go_home(update, context)
    
    if text == BTN_BOT_TOPUP:
        context.user_data.clear()
        context.user_data["flow"] = "bot_topup"
        await update.message.reply_text("اختر طريقة:", reply_markup=kb_methods())
        return ST_TOPUP_METHOD
    
    await update.message.reply_text("❌ خيار غير صحيح", reply_markup=kb_balance_menu())
    return ST_BAL_MENU

async def topup_choose_method(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = safe_text(update.message.text)
    
    if text == BTN_BACK:
        return await go_home(update, context)
    
    if text == BTN_SYRIATEL:
        s = get_settings()
        context.user_data["method"] = "SYRIATEL"
        context.user_data["syriatel_code"] = s["syriatel_code"]
        await update.message.reply_text(
            f"أرسل إلى الكود: {s['syriatel_code']}\nثم أدخل رقم العملية:",
            reply_markup=kb_back()
        )
        return ST_TOPUP_TXID
    
    await update.message.reply_text("❌ خيار غير صحيح", reply_markup=kb_methods())
    return ST_TOPUP_METHOD

async def topup_get_txid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = safe_text(update.message.text)
    
    if text == BTN_BACK:
        return await go_home(update, context)
    
    if not is_reasonable_txid(text):
        await update.message.reply_text("❌ رقم غير صالح (6-20 رقم)")
        return ST_TOPUP_TXID
    
    # فحص التكرار
    uid = update.effective_user.id
    tx_info = tx_manager.get_transaction_info(text)
    
    if tx_info:
        if tx_info.get("user_id") == uid:
            await update.message.reply_text(
                f"⚠️ لقد استخدمت هذا الرقم مسبقاً\n\n"
                f"الرقم: `{text}`\n"
                f"المبلغ السابق: {tx_info.get('amount', 0)}\n\n"
                f"هل تريد المتابعة؟ (نعم/لا)",
                parse_mode="Markdown",
                reply_markup=ReplyKeyboardMarkup([
                    [KeyboardButton("نعم"), KeyboardButton("لا")],
                    [KeyboardButton(BTN_BACK)]
                ], resize_keyboard=True)
            )
            context.user_data["checking_duplicate"] = text
            return ST_DUPLICATE_CHECK
        else:
            await update.message.reply_text(
                f"❌ هذا الرقم مستخدم من قبل مستخدم آخر\n\n"
                f"يرجى استخدام رقم عملية مختلف.",
                parse_mode="Markdown"
            )
            return ST_TOPUP_TXID
    
    context.user_data["tx_id"] = text
    s = get_settings()
    await update.message.reply_text(
        f"أدخل المبلغ (الحد الأدنى: {s['min_topup']}):",
        reply_markup=kb_back()
    )
    return ST_AMOUNT

async def handle_duplicate_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = safe_text(update.message.text)
    tx_id = context.user_data.get("checking_duplicate", "")
    
    if text == BTN_BACK:
        return await go_home(update, context)
    
    if text == "نعم":
        # متابعة مع الرقم المكرر
        s = get_settings()
        await update.message.reply_text(
            f"أدخل المبلغ (الحد الأدنى: {s['min_topup']}):",
            reply_markup=kb_back()
        )
        return ST_AMOUNT
    elif text == "لا":
        # إدخال رقم جديد
        await update.message.reply_text(
            "أدخل رقم عملية جديد:",
            reply_markup=kb_back()
        )
        return ST_TOPUP_TXID
    
    await update.message.reply_text("❌ اختر نعم أو لا", reply_markup=kb_back())
    return ST_DUPLICATE_CHECK

async def get_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = safe_text(update.message.text)
    
    if text == BTN_BACK:
        return await go_home(update, context)
    
    if not is_pos_int(text):
        await update.message.reply_text("❌ أدخل رقم صحيح")
        return ST_AMOUNT
    
    amount = int(text)
    uid = update.effective_user.id
    s = get_settings()
    
    if amount < s["min_topup"]:
        await update.message.reply_text(f"❌ الحد الأدنى: {s['min_topup']}")
        return ST_AMOUNT
    
    # التحقق من التكرار النهائي
    tx_id = context.user_data.get("tx_id", "")
    if tx_id:
        duplicate_check = await check_transaction_duplicate(tx_id, amount, s["syriatel_code"], uid)
        
        if not duplicate_check["allowed"]:
            await update.message.reply_text(
                f"❌ **مرفوض**: {duplicate_check['reason']}\n\n"
                f"رقم العملية: `{tx_id}`\n"
                f"المبلغ: {amount}\n\n"
                f"استخدم رقم عملية مختلف.",
                parse_mode="Markdown"
            )
            return ST_TOPUP_TXID
    
    # إنشاء الطلب
    user = update.effective_user
    order_id = make_order_id("TOP")
    order = {
        "order_id": order_id,
        "type": "bot_topup",
        "status": "pending",
        "user_id": uid,
        "username": user.username or "",
        "tx_id": tx_id,
        "syriatel_code": s["syriatel_code"],
        "amount": amount,
        "created_at": int(time.time()),
    }
    add_order(order)
    
    await update.message.reply_text(
        "✅ تم إرسال طلب الشحن\n⏳ جاري التحقق الآلي...",
        reply_markup=kb_main()
    )
    
    # إشعار الأدمن
    admin_msg = f"📩 طلب شحن جديد\nOrderID: {order_id}\nالمبلغ: {amount}\nالمستخدم: {uid}"
    await notify_admins(context, admin_msg, order_id=order_id)
    
    context.user_data.clear()
    return ST_MAIN

# =========================
# معالجات الأدمن
# =========================
def ik_admin_home():
    settings = get_settings()
    auto_status = "✅ مفعل" if settings.get("auto_verify_enabled") else "❌ معطل"
    
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📥 الطلبات المعلقة", callback_data="AD:PENDING:0"),
         InlineKeyboardButton("📜 آخر الطلبات", callback_data="AD:LAST:0")],
        [InlineKeyboardButton(f"🤖 تحقق آلي: {auto_status}", callback_data="AD:AUTO_TOGGLE")],
        [InlineKeyboardButton("📊 إحصائيات", callback_data="AD:STATS"),
         InlineKeyboardButton("⚙️ إعدادات", callback_data="AD:SETTINGS")],
        [InlineKeyboardButton("🔍 فحص تكرار", callback_data="AD:CHECK_DUPLICATE")]
    ])

async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ للأدمن فقط")
        return
    
    await update.message.reply_text("👑 لوحة الأدمن", reply_markup=ik_admin_home())

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = query.from_user.id
    
    if not is_admin(user_id):
        return
    
    if data == "AD:AUTO_TOGGLE":
        settings = get_settings()
        new_status = not settings.get("auto_verify_enabled", False)
        set_settings({"auto_verify_enabled": new_status})
        
        status_text = "✅ مفعل" if new_status else "❌ معطل"
        await query.edit_message_text(f"🤖 التحقق الآلي: {status_text}")
    
    elif data == "AD:STATS":
        orders = list_orders()
        pending = sum(1 for o in orders if o.get("status") == "pending")
        completed = sum(1 for o in orders if o.get("status") == "completed")
        verified_count = len(tx_manager.verified_tx)
        
        await query.edit_message_text(
            f"📊 الإحصائيات:\n\n"
            f"📥 معلق: {pending}\n"
            f"✅ مكتمل: {completed}\n"
            f"🔢 عمليات محققة: {verified_count}\n"
            f"👥 مستخدمين: {len(get_all_user_ids())}"
        )
    
    elif data == "AD:CHECK_DUPLICATE":
        await query.edit_message_text(
            "🔍 للتحقق من تكرار رقم عملية:\n"
            "استخدم الأمر: /checktx رقم_العملية\n\n"
            "مثال:\n/checktx 123456789",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ رجوع", callback_data="AD:HOME")]
            ])
        )
    
    elif data == "AD:HOME":
        await query.edit_message_text("👑 لوحة الأدمن", reply_markup=ik_admin_home())

# أوامر الأدمن الإضافية
async def check_transaction_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """فحص تكرار رقم عملية"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ للأدمن فقط")
        return
    
    args = context.args
    if not args:
        await update.message.reply_text(
            "📝 استخدام الأمر:\n/checktx رقم_العملية\n\nمثال:\n/checktx 123456789"
        )
        return
    
    tx_id = args[0].strip()
    tx_info = tx_manager.get_transaction_info(tx_id)
    
    if tx_info:
        tx_time = time.ctime(tx_info.get("verified_at", 0))
        await update.message.reply_text(
            f"🚨 **رقم العملية مستخدم مسبقاً!**\n\n"
            f"📋 الرقم: `{tx_id}`\n"
            f"💰 المبلغ: {tx_info.get('amount', 0)}\n"
            f"👤 المستخدم: {tx_info.get('user_id', 'غير معروف')}\n"
            f"📄 OrderID: {tx_info.get('order_id', 'غير معروف')}\n"
            f"🕒 الوقت: {tx_time}\n\n"
            f"⛔ **يجب رفض أي طلب جديد بهذا الرقم**",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            f"✅ **رقم العملية غير مستخدم**\n\n"
            f"📋 الرقم: `{tx_id}`\n"
            f"📊 الحالة: متاح للاستخدام",
            parse_mode="Markdown"
        )

# =========================
# بناء التطبيق
# =========================
def build_app():
    _ensure_data_files()
    
    app = ApplicationBuilder().token(TOKEN).build()
    
    # جدولة المهام
    AUTO_VERIFY_INTERVAL = int(os.getenv("AUTO_VERIFY_INTERVAL", "300"))
    if AUTO_VERIFY_INTERVAL > 0:
        app.job_queue.run_repeating(stealth_auto_verification_job, 
                                   interval=AUTO_VERIFY_INTERVAL, 
                                   first=60)
        print(f"✅ تم جدولة التحقق الآلي كل {AUTO_VERIFY_INTERVAL} ثانية")
    
    # Conversation Handler
    user_conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            ST_MAIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, smart_router)],
            ST_EISH_ACTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u,c: ST_EISH_ACTION)],
            ST_BAL_MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, balance_menu)],
            ST_TOPUP_METHOD: [MessageHandler(filters.TEXT & ~filters.COMMAND, topup_choose_method)],
            ST_TOPUP_TXID: [MessageHandler(filters.TEXT & ~filters.COMMAND, topup_get_txid)],
            ST_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_amount)],
            ST_DUPLICATE_CHECK: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_duplicate_check)],
        },
        fallbacks=[CommandHandler("start", start)]
    )
    
    app.add_handler(user_conv)
    app.add_handler(CommandHandler("admin", cmd_admin))
    app.add_handler(CommandHandler("checktx", check_transaction_command))
    app.add_handler(CallbackQueryHandler(admin_callback, pattern=r"^AD:"))
    
    return app

# =========================
# التشغيل الرئيسي
# =========================
def main():
    print("=" * 50)
    print("🚀 بدء تشغيل بوت التلغرام")
    print(f"👑 السوبر أدمن: {SUPER_ADMIN_ID}")
    print(f"📁 البيانات: {DATA_DIR}")
    print(f"🤖 التحقق الآلي: {'✅ متاح' if SELENIUM_AVAILABLE else '❌ غير متاح'}")
    print("=" * 50)
    
    # التحقق من بيانات سيرياتيل
    syriatel_user = os.getenv("SYRIATEL_USERNAME", "")
    syriatel_pass = os.getenv("SYRIATEL_PASSWORD", "")
    
    if syriatel_user and syriatel_pass:
        print("✅ بيانات سيرياتيل موجودة (آمنة في Environment Variables)")
    else:
        print("⚠️ تحذير: بيانات سيرياتيل غير موجودة")
        print("   أضف SYRIATEL_USERNAME و SYRIATEL_PASSWORD في Railway Variables")
    
    app = build_app()
    
    try:
        app.run_polling(drop_pending_updates=True)
    except KeyboardInterrupt:
        print("\n🛑 إيقاف البوت...")
        asyncio.run(stealth_login.close())
    except Exception as e:
        print(f"❌ خطأ: {e}")
        asyncio.run(stealth_login.close())

if __name__ == "__main__":
    main()
