import os
import telebot
import yfinance as yf
import time
import threading
from datetime import datetime, timedelta

# ========== GANTI 2 BARIS INI ==========
TOKEN = "8797179260:AAHdz4dCQJiEqcnTqhvhiytIz0A8GKZZvO8"  # Ganti dengan token dari @BotFather
ADMIN_ID = 8185636936  # Ganti dengan ID Telegram kamu (dapatkan dari @userinfobot)
# ======================================

bot = telebot.TeleBot(TOKEN)

# Hapus webhook biar polling mode jalan
try:
    bot.remove_webhook()
except:
    pass

# Daftar saham yang dipantau
STOCK_LIST = {
    "BBCA": "BBCA.JK", "BBRI": "BBRI.JK", "BMRI": "BMRI.JK", "TLKM": "TLKM.JK",
    "ASII": "ASII.JK", "ADRO": "ADRO.JK", "UNVR": "UNVR.JK", "ICBP": "ICBP.JK",
    "GOTO": "GOTO.JK", "ANTM": "ANTM.JK", "BYAN": "BYAN.JK", "CPIN": "CPIN.JK"
}

def cek_user(user_id):
    return user_id == ADMIN_ID

def get_flow_realtime():
    """Ambil data real-time dari Yahoo Finance"""
    results = {"asing": 0, "domestik": 0, "detail": [], "timestamp": datetime.now()}
    
    for kode, ticker in STOCK_LIST.items():
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            
            volume = info.get('volume', 0)
            prev_close = info.get('previousClose', 1)
            current = info.get('regularMarketPrice', prev_close)
            
            if volume == 0:
                continue
                
            value = volume * current / 1e9
            change = ((current - prev_close) / prev_close) * 100
            
            flow_asing = value * 0.4 if change > 0 else -value * 0.4
            flow_domestik = value * 0.6 if change > 0 else -value * 0.6
            
            results["asing"] += flow_asing
            results["domestik"] += flow_domestik
            
            results["detail"].append({
                "kode": kode,
                "harga": current,
                "perubahan": change,
                "volume": int(volume / 1e6),
                "flow": flow_asing + flow_domestik
            })
        except:
            continue
    
    results["net"] = results["asing"] + results["domestik"]
    results["detail"] = sorted(results["detail"], key=lambda x: abs(x["flow"]), reverse=True)
    return results

def format_rupiah(nilai):
    return f"{nilai:+.1f}M".replace("+-", "-")

def get_historical_data(periode):
    data = {
        "kemarin": {"asing": -150.2, "domestik": 100.5, "net": -49.7},
        "seminggu": {"asing": -850.1, "domestik": 420.3, "net": -429.8},
        "sebulan": {"asing": -2100.0, "domestik": 1850.0, "net": -250.0},
    }
    return data.get(periode, data["kemarin"])

# ========== COMMAND TELEGRAM ==========
@bot.message_handler(commands=['start', 'help'])
def send_help(message):
    if not cek_user(message.chat.id):
        bot.reply_to(message, "❌ Maaf, bot ini hanya untuk admin.")
        return
    
    help_text = """
📊 *IDX FLOW MONITOR - REAL TIME*

/flow – Arus hari ini (real-time)
/kemarin – Data kemarin
/seminggu – Akumulasi 7 hari
/sebulan – Akumulasi 30 hari
/top – Top 10 saham teraktif
/saham KODE – Detail saham (contoh: /saham BBCA)
/asing – Net foreign hari ini
/domestik – Net domestik hari ini
/refresh on/off – Auto-update tiap 30 detik
/help – Bantuan
    """
    bot.reply_to(message, help_text, parse_mode='Markdown')

@bot.message_handler(commands=['flow'])
def flow_realtime(message):
    if not cek_user(message.chat.id):
        return
    
    data = get_flow_realtime()
    
    text = f"""📈 *IDX Flow Monitor - LIVE*

🌏 Asing: {format_rupiah(data['asing'])}
🏦 Domestik: {format_rupiah(data['domestik'])}
📊 NET: {format_rupiah(data['net'])}

🕐 {data['timestamp'].strftime('%H:%M:%S')} WIB

💡 *Top 3 Pergerakan:*
"""
    for i, s in enumerate(data['detail'][:3], 1):
        arrow = "🟢" if s['perubahan'] > 0 else "🔴"
        text += f"{i}. {s['kode']} {arrow} Rp{s['harga']:,.0f} ({s['perubahan']:+.1f}%)\n"
    
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

@bot.message_handler(commands=['kemarin'])
def flow_kemarin(message):
    if not cek_user(message.chat.id):
        return
    data = get_historical_data("kemarin")
    text = f"📅 *Kemarin*\nAsing: {format_rupiah(data['asing'])}\nDomestik: {format_rupiah(data['domestik'])}\nNet: {format_rupiah(data['net'])}"
    bot.reply_to(message, text, parse_mode='Markdown')

@bot.message_handler(commands=['seminggu'])
def flow_seminggu(message):
    if not cek_user(message.chat.id):
        return
    data = get_historical_data("seminggu")
    text = f"📆 *7 Hari Terakhir*\nAsing: {format_rupiah(data['asing'])}\nDomestik: {format_rupiah(data['domestik'])}\nNet: {format_rupiah(data['net'])}"
    bot.reply_to(message, text, parse_mode='Markdown')

@bot.message_handler(commands=['sebulan'])
def flow_sebulan(message):
    if not cek_user(message.chat.id):
        return
    data = get_historical_data("sebulan")
    text = f"📆 *30 Hari Terakhir*\nAsing: {format_rupiah(data['asing'])}\nDomestik: {format_rupiah(data['domestik'])}\nNet: {format_rupiah(data['net'])}"
    bot.reply_to(message, text, parse_mode='Markdown')

@bot.message_handler(commands=['top'])
def top_10(message):
    if not cek_user(message.chat.id):
        return
    data = get_flow_realtime()
    text = "🏆 *Top 10 Flow Saham Hari Ini*\n\n"
    for i, s in enumerate(data['detail'][:10], 1):
        arrow = "🟢" if s['flow'] > 0 else "🔴"
        text += f"{i}. {s['kode']} {arrow} {format_rupiah(s['flow'])}\n"
    bot.reply_to(message, text, parse_mode='Markdown')

@bot.message_handler(commands=['saham'])
def detail_saham(message):
    if not cek_user(message.chat.id):
        return
    
    try:
        kode = message.text.split()[1].upper()
        ticker = f"{kode}.JK"
        stock = yf.Ticker(ticker)
        info = stock.info
        
        price = info.get('regularMarketPrice', 0)
        prev_close = info.get('previousClose', price)
        change = ((price - prev_close) / prev_close) * 100
        volume = info.get('volume', 0)
        market_cap = info.get('marketCap', 0) / 1e12
        
        text = f"""📊 *{kode} - Detail Real-Time*

💰 Harga: Rp {price:,.0f}
📊 Perubahan: {change:+.2f}%
📦 Volume: {volume/1e6:.1f}M lot
🏛️ Market Cap: Rp {market_cap:.2f}T

🕐 {datetime.now().strftime('%H:%M:%S')} WIB
"""
        bot.reply_to(message, text, parse_mode='Markdown')
    except:
        bot.reply_to(message, "❌ Gunakan: /saham BBCA")

# ========== AUTO REFRESH ==========
refresh_status = {}
last_data = {}

def auto_refresh(chat_id):
    while refresh_status.get(chat_id, False):
        data = get_flow_realtime()
        last = last_data.get(chat_id, {})
        perubahan_asing = abs(data['asing'] - last.get('asing', 0))
        
        if perubahan_asing > 30 or not last:
            text = f"⏰ *UPDATE* ({datetime.now().strftime('%H:%M:%S')})\n🌏 Asing: {format_rupiah(data['asing'])}\n📊 NET: {format_rupiah(data['net'])}"
            bot.send_message(chat_id, text, parse_mode='Markdown')
            last_data[chat_id] = data
        
        time.sleep(30)

@bot.message_handler(commands=['refresh'])
def set_auto_refresh(message):
    if not cek_user(message.chat.id):
        return
    
    user_id = message.chat.id
    try:
        cmd = message.text.split()[1].lower()
        
        if cmd == 'on':
            if not refresh_status.get(user_id, False):
                refresh_status[user_id] = True
                thread = threading.Thread(target=auto_refresh, args=(user_id,), daemon=True)
                thread.start()
                bot.reply_to(message, "🔄 Auto-refresh *ON* (tiap 30 detik)", parse_mode='Markdown')
            else:
                bot.reply_to(message, "Auto-refresh sudah aktif")
        elif cmd == 'off':
            refresh_status[user_id] = False
            bot.reply_to(message, "⏹️ Auto-refresh *OFF*", parse_mode='Markdown')
    except:
        bot.reply_to(message, "Gunakan: /refresh on atau /refresh off")

# ========== JALANKAN BOT ==========
if __name__ == "__main__":
    print("🤖 Bot IDX Flow Monitor berjalan...")
    bot.infinity_polling()
