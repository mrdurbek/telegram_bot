# -*- coding: utf-8 -*-
import telebot
import sqlite3
from telebot import types
import json
import random
import datetime
import os
import threading

# Try to import Flask (optional for health checks)
try:
    from flask import Flask
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False

# Simple HTTP server fallback
from http.server import BaseHTTPRequestHandler, HTTPServer

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"PUBG UC Bot is running")

def run_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), HealthHandler)
    server.serve_forever()

# Bot Configuration
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = "@swKoMBaT"
GROUP_ID = "@swKoMBaT1"
YOUTUBE_LINK = "https://youtube.com/@swkombat?si=5vVIGfj_NYx-yJLK"
ADMIN_IDS = [6322816106]
DB_NAME = "bot.db"

bot = telebot.TeleBot(BOT_TOKEN)

# --- DATABASE INIT ---
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT
        )
    ''')
    conn.commit()
    conn.close()

# --- JSON FILES HANDLING ---
def load_json(filename):
    try:
        with open(filename, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_json(filename, data):
    with open(filename, 'w') as f:
        json.dump(data, f, indent=4)

# Initialize JSON files if they don't exist
for file in ["users.json", "competitions.json", "devices.json"]:
    if not os.path.exists(file):
        save_json(file, {})

# --- SUBSCRIPTION CHECK ---
def check_subscription(user_id):
    try:
        channel = bot.get_chat_member(CHANNEL_ID, user_id)
        group = bot.get_chat_member(GROUP_ID, user_id)
        return channel.status in ["member", "administrator", "creator"] and group.status in ["member", "administrator", "creator"]
    except Exception as e:
        print(f"Subscription check error: {e}")
        return False

def send_subscription_prompt(user_id):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📢 Kanalga obuna bo'lish", url=f"https://t.me/{CHANNEL_ID[1:]}"))
    markup.add(types.InlineKeyboardButton("👥 Guruhga obuna bo'lish", url=f"https://t.me/{GROUP_ID[1:]}"))
    markup.add(types.InlineKeyboardButton("📺 YouTube kanalga obuna bo'lish", url=YOUTUBE_LINK))
    markup.add(types.InlineKeyboardButton("✅ Obuna bo'ldim", callback_data="check_sub"))
    
    text = (
        "🔒 Botdan foydalanish uchun quyidagilarga obuna bo'ling:\n\n"
        f"{CHANNEL_ID} - Telegram kanal\n"
        f"{GROUP_ID} - Telegram guruh\n"
        f"{YOUTUBE_LINK} - YouTube kanal\n\n"
        "Obuna bo'lgach, '✅ Obuna bo'ldim' tugmasini bosing."
    )
    bot.send_message(user_id, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "check_sub")
def check_sub_callback(call):
    if check_subscription(call.from_user.id):
        bot.send_message(call.from_user.id, "✅ Obuna tasdiqlandi!")
        start(call.message)
    else:
        bot.send_message(call.from_user.id, "❌ Obuna aniqlanmadi. Iltimos, tekshirib qayta urinib ko'ring.")

# --- MAIN MENU ---
def main_menu(user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("📨 Referal havola", "📊 Referal reyting")
    markup.row("🎁 Konkurslar", "💰 UC balans")
    markup.row("💸 UC yechish")
    return markup

# --- REFERRAL SYSTEM ---
def add_user(user_id, ref_id=None):
    users = load_json("users.json")
    if str(user_id) not in users:
        users[str(user_id)] = {
            "uc": 0,
            "ref": str(ref_id) if ref_id else None,
            "refs": [],
            "joined": str(datetime.date.today())
        }
        if ref_id and str(ref_id) in users:
            users[str(ref_id)]["refs"].append(str(user_id))
            users[str(ref_id)]["uc"] += 3
        save_json("users.json", users)

# --- REFERRAL LINK ---
@bot.message_handler(func=lambda msg: msg.text == "📨 Referal havola")
def send_ref_link(message):
    link = f"https://t.me/{bot.get_me().username}?start={message.from_user.id}"
    bot.send_message(message.chat.id, f"🔗 Referal havolangiz:\n{link}")

# --- UC BALANCE ---
@bot.message_handler(func=lambda msg: msg.text == "💰 UC balans")
def send_uc(message):
    users = load_json("users.json")
    uc = users.get(str(message.from_user.id), {}).get("uc", 0)
    bot.send_message(message.chat.id, f"💰 Sizning balansingiz: {uc} UC")

# --- UC WITHDRAWAL ---
@bot.message_handler(func=lambda msg: msg.text == "💸 UC yechish")
def request_uc_withdraw(message):
    users = load_json("users.json")
    uc = users.get(str(message.from_user.id), {}).get("uc", 0)
    if uc < 60:
        bot.send_message(message.chat.id, "❌ UC yechish uchun kamida 60 UC kerak.")
        return
    
    markup = types.InlineKeyboardMarkup()
    for amount in [60, 120, 180, 325]:
        if uc >= amount:
            markup.add(types.InlineKeyboardButton(f"{amount} UC", callback_data=f"withdraw_{amount}"))
    bot.send_message(message.chat.id, "💳 Yechmoqchi bo'lgan UC miqdorini tanlang:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("withdraw_"))
def handle_withdraw(call):
    amount = int(call.data.split("_")[1])
    msg = bot.send_message(call.from_user.id, f"🔢 PUBG ID raqamingizni yuboring:")
    bot.register_next_step_handler(msg, confirm_withdraw, amount)

def confirm_withdraw(message, amount):
    pubg_id = message.text.strip()
    user_id = message.from_user.id
    users = load_json("users.json")
    
    if users.get(str(user_id), {}).get("uc", 0) < amount:
        bot.send_message(user_id, "❌ Sizda yetarli UC mavjud emas.")
        return
    
    users[str(user_id)]["uc"] -= amount
    save_json("users.json", users)
    
    for admin in ADMIN_IDS:
        bot.send_message(admin, f"📥 @{message.from_user.username} ({user_id})\n💸 {amount} UC so'radi.\n🔢 PUBG ID: {pubg_id}")
    
    bot.send_message(user_id, f"✅ So'rovingiz qabul qilindi. Tez orada UC yuboriladi.")

# --- COMPETITIONS ---
@bot.message_handler(func=lambda m: m.from_user.id in ADMIN_IDS and m.text == "🎁 Konkurslar")
def admin_competitions_menu(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("🆕 Yangi konkurs yaratish")
    markup.row("🔙 Ortga")
    bot.send_message(message.chat.id, "Admin: nima qilamiz?", reply_markup=markup)

@bot.message_handler(func=lambda m: m.from_user.id in ADMIN_IDS and m.text == "🆕 Yangi konkurs yaratish")
def ask_competition_image(message):
    msg = bot.send_message(message.chat.id, "Konkurs rasm yuboring:")
    bot.register_next_step_handler(msg, process_comp_image)

def process_comp_image(message):
    if not message.photo:
        return bot.send_message(message.chat.id, "Iltimos, rasm yuboring:")
    
    file_id = message.photo[-1].file_id
    msg = bot.send_message(message.chat.id, "Konkurs tugash vaqtini yuboring (YYYY-MM-DD HH:MM):")
    bot.register_next_step_handler(msg, process_comp_deadline, file_id)

def process_comp_deadline(message, file_id):
    try:
        deadline = datetime.datetime.strptime(message.text, "%Y-%m-%d %H:%M")
    except:
        return bot.send_message(message.chat.id, "Formati noto'g'ri. YYYY-MM-DD HH:MM tarzda yozing:")
    
    msg = bot.send_message(message.chat.id, "G'oliblar sonini kiriting:")
    bot.register_next_step_handler(msg, process_comp_winners_count, file_id, deadline)

def process_comp_winners_count(message, file_id, deadline):
    try:
        winners = int(message.text)
    except:
        return bot.send_message(message.chat.id, "Iltimos, butun son kiriting:")
    
    competitions = load_json("competitions.json")
    comp_id = str(len(competitions) + 1)
    competitions[comp_id] = {
        "file_id": file_id,
        "deadline": deadline.isoformat(),
        "winners": winners,
        "participants": []
    }
    save_json("competitions.json", competitions)
    
    bot.send_message(message.chat.id, f"Konkurs №{comp_id} yaratildi. Endi e'lon qilinadi.")
    post_competition(comp_id)

def post_competition(comp_id):
    competitions = load_json("competitions.json")
    comp = competitions[comp_id]
    
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("✅ Qatnashish", callback_data=f"join_{comp_id}"))
    
    caption = f"📢 *Konkurs #{comp_id}!*\n\nVaqti: {comp['deadline']}\n\nIshtirok etish uchun 'Qatnashish' tugmasini bosing!"
    bot.send_photo(CHANNEL_ID, comp["file_id"], caption, reply_markup=keyboard, parse_mode="Markdown")
    bot.send_photo(GROUP_ID, comp["file_id"], caption, reply_markup=keyboard, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda c: c.data.startswith("join_"))
def join_competition(call):
    comp_id = call.data.split("_")[1]
    competitions = load_json("competitions.json")
    comp = competitions[comp_id]
    uid = str(call.from_user.id)
    
    if uid in comp["participants"]:
        return bot.answer_callback_query(call.id, "Siz allaqachon qatnashgansiz.")
    
    if not check_subscription(call.from_user.id):
        bot.answer_callback_query(call.id, "❗ Obuna bo'ling", show_alert=True)
        send_subscription_prompt(call.from_user.id)
        return
    
    comp["participants"].append(uid)
    competitions[comp_id] = comp
    save_json("competitions.json", competitions)
    bot.answer_callback_query(call.id, "✅ Siz tanlov ishtirokchisiga aylandingiz!")

# --- START COMMAND ---
@bot.message_handler(commands=["start"])
def start(message):
    user_id = message.from_user.id
    ref_id = None
    
    if len(message.text.split()) > 1:
        ref_id = message.text.split()[1]
    
    add_user(user_id, ref_id)
    
    if not check_subscription(user_id):
        send_subscription_prompt(user_id)
    else:
        bot.send_message(user_id, "🎮 Botga xush kelibsiz!", reply_markup=main_menu(user_id))

if __name__ == "__main__":
    try:
        init_db()
        print("Database initialized")
        
        # Start health check server in a separate thread
        if FLASK_AVAILABLE:
            # Flask server
            app = Flask(__name__)
            @app.route('/')
            def health_check():
                return "PUBG UC Bot is running", 200
            
            flask_thread = threading.Thread(target=lambda: app.run(
                host='0.0.0.0',
                port=int(os.environ.get("PORT", 10000)),
                debug=False,
                use_reloader=False
            ))
        else:
            # Fallback HTTP server
            flask_thread = threading.Thread(target=run_server)
        
        flask_thread.daemon = True
        flask_thread.start()
        
        print("Starting bot polling...")
        bot.infinity_polling()
        
    except Exception as e:
        print(f"Bot crashed: {e}")
        # Optionally notify admin
        for admin in ADMIN_IDS:
            try:
                bot.send_message(admin, f"Bot crashed: {e}")
            except:
                pass

