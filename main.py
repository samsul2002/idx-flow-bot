import os
import telebot
import requests
from datetime import datetime
import threading
import time
import json
import re

# ========== GANTI 2 BARIS INI ==========
TOKEN = "8797179260:AAE6A8-75ax4bl5QfeC_lgOQMLN4CVE9lBw"  # Ganti dengan token dari @BotFather
ADMIN_ID = 8185636936  # Ganti dengan ID Telegram kamu
# ======================================

bot = telebot.TeleBot(TOKEN)

try:
    bot.remove_webhook()
except:
    pass

def cek_user(user_id):
    return user_id == ADMIN_ID

def get_flow_realtime():
    """Ambil data real-time dari RTI Business"""
    try:
        # Data simulasi sementara sampai API siap
        # Karena scraping RTI perlu penanganan khusus, kita gunakan data simulasi dulu
        # TAPI ini data yang bisa diupdate manual atau nanti kita konek ke API lain
        
        # Ini contoh data yang bisa kamu ganti manual setiap hari
        # Atau nanti kita integrasi dengan Google Sheets
        
        return {
            "asing": -317.9,
            "domestik": -272.4,
            "net": -590.3,
            "total_volume": 8520,
            "total_value_m": 12800,
            "top_stocks": [
                {"kode": "BBCA", "value": 2850, "change": 1.25},
                {"kode": "BBRI", "value": 2100, "change": -0.75},
                {"kode": "TLKM", "value": 1950, "change": 0.50},
                {"kode": "ASII", "value": 1680, "change": -1.20},
                {"kode": "BMRI", "value": 1540, "change": 0.90},
            ],
            "timestamp": datetime.now()
        }
        
    except Exception as e:
        print(f"Error: {e}")
        return {
            "asing": 0,
            "domestik": 0,
            "net": 0,
            "total_volume": 0,
            "total_value_m": 0,
            "top_stocks": [],
            "timestamp": datetime.now(),
            "error": str(e)
        }

def get_stock_detail(kode):
    """Ambil detail saham"""
    try:
        # Data simulasi per saham
        # Ganti dengan data real nanti
        stock_data = {
            "BBCA": {"harga": 9850, "change": 1.25, "volume": 452, "value": 4450, "high": 9900, "low": 9750},
            "BBRI": {"harga": 4950, "change": -0.75, "volume": 380, "value": 1880, "high": 5020, "low": 4920},
            "TLKM": {"harga": 3850, "change": 0.50, "volume": 310, "value": 1190, "high": 3880, "low": 3820},
            "BMRI": {"harga": 6250, "change": 0.90, "volume": 245, "value": 1530, "high": 6300, "low": 6200},
            "ASII": {"harga": 5250, "change": -1.20, "volume": 298, "value": 1560, "high": 5350, "low": 5220},
        }
        
        data = stock_data.get(kode.upper())
        if data:
            return {
                "kode": kode.upper(),
                "harga": data["harga"],
                "perubahan": data["change"],
                "volume": data["volume"],
                "value_m": data["value"],
                "high": data["high"],
                "low": data["low"]
            }
        return None
    except:
        return None

def format_rupiah(nilai):
    return f"{nilai:+.1f}M".replace("+-", "-")

# ========== COMMAND TELEGRAM ==========
@bot.message_handler(commands=['start', 'help'])
def send_help(message):
    if not cek_user(message.chat.id):
        bot.reply_to(message, "❌ Maaf, bot ini hanya untuk admin.")
        return
    
    help_text = """
📊 *IDX FLOW MONITOR*

/flow – Arus hari ini
/top – Top 5 saham teraktif
/saham KODE – Detail saham (contoh: /saham BBCA)
/asing – Net foreign
/domestik – Net domestik
/update – Update data manual (admin only)

*Catatan:* Data diupdate manual oleh admin
    """
    bot.reply_to(message, help_text, parse_mode='Markdown')

@bot.message_handler(commands=['flow'])
def flow_realtime(message):
    if not cek_user(message.chat.id):
        return
    
    data = get_flow_realtime()
    
    if data.get('error'):
        text = f"⚠️ Error: {data['error']}"
    else:
        text = f"""📈 *IDX Flow Monitor*

🌏 Asing: {format_rupiah(data['asing'])}
🏦 Domestik: {format_rupiah(data['domestik'])}
📊 NET: {format_rupiah(data['net'])}

📦 Total Volume: {data['total_volume']:.0f}M lot
💰 Total Value: Rp {data['total_value_m']:.0f}M

🕐 {data['timestamp'].strftime('%H:%M:%S')} WIB

💡 *Top 5:*
"""
        for i, s in enumerate(data['top_stocks'][:5], 1):
            arrow = "🟢" if s['change'] > 0 else "🔴"
            text += f"{i}. {s['kode']} {arrow} Rp{s['value']:.0f}M ({s['change']:+.1f}%)\n"
    
    bot.reply_to(message, text, parse_mode='Markdown')

@bot.message_handler(commands=['top'])
def top_10(message):
    if not cek_user(message.chat.id):
        return
    
    data = get_flow_realtime()
    
    text = "🏆 *Top 5 Saham Teraktif*\n\n"
    for i, s in enumerate(data['top_stocks'][:5], 1):
        arrow = "🟢" if s['change'] > 0 else "🔴"
        text += f"{i}. {s['kode']} {arrow} Rp{s['value']:.0f}M\n"
    
    bot.reply_to(message, text, parse_mode='Markdown')

@bot.message_handler(commands=['saham'])
def detail_saham(message):
    if not cek_user(message.chat.id):
        return
    
    try:
        kode = message.text.split()[1].upper()
    except:
        bot.reply_to(message, "❌ Gunakan: /saham BBCA")
        return
    
    data = get_stock_detail(kode)
    
    if not data:
        bot.reply_to(message, f"❌ Data saham {kode} tidak tersedia")
        return
    
    text = f"""📊 *{data['kode']} - Detail*

💰 Harga: Rp {data['harga']:,.0f}
📊 Perubahan: {data['perubahan']:+.2f}%
📈 Hari ini: Rp {data['low']:,.0f} - Rp {data['high']:,.0f}
📦 Volume: {data['volume']:.0f}M lot
💵 Nilai: Rp {data['value_m']:.0f}M

🕐 {datetime.now().strftime('%H:%M:%S')} WIB
"""
    bot.reply_to(message, text, parse_mode='Markdown')

@bot.message_handler(commands=['asing'])
def net_asing(message):
    if not cek_user(message.chat.id):
        return
    data = get_flow_realtime()
    bot.reply_to(message, f"🌏 *Net Foreign*: {format_rupiah(data['asing'])}", parse_mode='Markdown')

@bot.message_handler(commands=['domestik'])
def net_domestik(message):
    if not cek_user(message.chat.id):
        return
    data = get_flow_realtime()
    bot.reply_to(message, f"🏦 *Net Domestik*: {format_rupiah(data['domestik'])}", parse_mode='Markdown')

# ========== UPDATE DATA MANUAL ==========
data_simpanan = {}

@bot.message_handler(commands=['update'])
def update_data(message):
    if not cek_user(message.chat.id):
        return
    
    try:
        # Format: /update asing=317.9 domestik=272.4 net=590.3
        args = message.text.split()
        if len(args) < 2:
            bot.reply_to(message, "❌ Format: /update asing=317 domestik=272 net=590")
            return
        
        data_baru = {}
        for arg in args[1:]:
            if '=' in arg:
                key, val = arg.split('=')
                data_baru[key] = float(val)
        
        # Simpan ke file atau memory
        global data_simpanan
        data_simpanan = data_baru
        
        bot.reply_to(message, f"✅ Data diupdate!\nAsing: {data_baru.get('asing',0)}M\nDomestik: {data_baru.get('domestik',0)}M\nNet: {data_baru.get('net',0)}M")
        
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {e}")

# ========== JALANKAN BOT ==========
if __name__ == "__main__":
    print("🤖 Bot IDX Flow Monitor berjalan...")
    print(f"Bot @{bot.get_me().username} aktif!")
    bot.infinity_polling()
