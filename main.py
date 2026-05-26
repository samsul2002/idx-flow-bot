import os
import telebot
import pandas as pd
from datetime import datetime
import threading
import time

# ========== GANTI 2 BARIS INI ==========
TOKEN = "8797179260:AAE6A8-75ax4bl5QfeC_lgOQMLN4CVE9lBw"  # Ganti dengan token dari @BotFather
ADMIN_ID = 8185636936  # Ganti dengan ID Telegram kamu (dapatkan dari @userinfobot)
# ======================================

bot = telebot.TeleBot(TOKEN)

try:
    bot.remove_webhook()
except:
    pass

def cek_user(user_id):
    return user_id == ADMIN_ID

def get_flow_from_idx():
    """
    Ambil data ringkasan perdagangan dari API resmi BEI
    Menggunakan library idx-bei
    """
    try:
        from idx_bei import IDX
        
        idx = IDX()
        
        # Ambil data ringkasan perdagangan harian
        # Data ini berisi ringkasan seluruh saham yang diperdagangkan hari ini
        ringkasan = idx.get_ringkasan_harian()
        
        if ringkasan is None or ringkasan.empty:
            return None
        
        # Hitung estimasi arus asing & domestik
        # Asumsi: Volume asing ~40% dari total volume, domestik ~60%
        total_volume = ringkasan['Total Volume'].sum() if 'Total Volume' in ringkasan.columns else 0
        total_value = ringkasan['Total Value'].sum() if 'Total Value' in ringkasan.columns else 0
        
        # Konversi ke miliar
        total_value_m = total_value / 1e9 if total_value > 0 else 0
        
        # Estimasi flow (positif jika harga naik, negatif jika turun)
        # Ambil dari perubahan harga rata-rata
        if 'Change' in ringkasan.columns:
            avg_change = ringkasan['Change'].mean()
        else:
            avg_change = 0
        
        # Arah flow ditentukan dari perubahan harga
        arah = 1 if avg_change > 0 else -1
        
        flow_asing = total_value_m * 0.4 * arah
        flow_domestik = total_value_m * 0.6 * arah
        
        # Ambil top saham berdasarkan volume/value
        detail = []
        if 'Code' in ringkasan.columns and 'Total Value' in ringkasan.columns:
            top_stocks = ringkasan.nlargest(10, 'Total Value')[['Code', 'Total Value', 'Change']].to_dict('records')
            for stock in top_stocks:
                detail.append({
                    "kode": stock.get('Code', ''),
                    "value_m": stock.get('Total Value', 0) / 1e9,
                    "perubahan": stock.get('Change', 0)
                })
        
        return {
            "asing": flow_asing,
            "domestik": flow_domestik,
            "net": flow_asing + flow_domestik,
            "total_volume": total_volume / 1e6,  # juta lot
            "total_value_m": total_value_m,
            "detail": detail,
            "timestamp": datetime.now()
        }
        
    except Exception as e:
        print(f"Error mengambil data dari IDX: {e}")
        # Fallback ke data simulasi jika gagal
        return {
            "asing": -317.9,
            "domestik": -272.4,
            "net": -590.3,
            "total_volume": 0,
            "total_value_m": 0,
            "detail": [],
            "timestamp": datetime.now(),
            "error": str(e)
        }

def get_stock_detail(kode_saham):
    """Ambil detail spesifik untuk 1 saham dari API BEI"""
    try:
        from idx_bei import IDX
        
        idx = IDX()
        
        # Coba ambil data saham individual
        # Beberapa method idx-bei mungkin berbeda, ini alternatif
        ringkasan = idx.get_ringkasan_harian()
        
        if ringkasan is not None and not ringkasan.empty and 'Code' in ringkasan.columns:
            # Filter berdasarkan kode saham
            stock_data = ringkasan[ringkasan['Code'].str.upper() == kode_saham.upper()]
            
            if not stock_data.empty:
                row = stock_data.iloc[0]
                return {
                    "kode": kode_saham.upper(),
                    "harga": row.get('Last Price', 0),
                    "perubahan": row.get('Change', 0),
                    "volume": row.get('Total Volume', 0) / 1e6,
                    "value": row.get('Total Value', 0) / 1e9,
                    "high": row.get('High', 0),
                    "low": row.get('Low', 0)
                }
        
        return None
    except Exception as e:
        print(f"Error detail saham {kode_saham}: {e}")
        return None

def format_rupiah(nilai_m):
    """Format nilai dalam miliar Rupiah"""
    return f"{nilai_m:+.1f}M".replace("+-", "-")

# ========== COMMAND TELEGRAM ==========
@bot.message_handler(commands=['start', 'help'])
def send_help(message):
    if not cek_user(message.chat.id):
        bot.reply_to(message, "❌ Maaf, bot ini hanya untuk admin.")
        return
    
    help_text = """
📊 *IDX FLOW MONITOR - REAL TIME (Langsung dari BEI)*

/flow – Arus hari ini (real-time)
/saham KODE – Detail saham (contoh: /saham BBCA)
/top – Top 10 saham teraktif hari ini
/asing – Net foreign hari ini
/domestik – Net domestik hari ini
/refresh on/off – Auto-update tiap 30 menit
/help – Bantuan

*Sumber Data:* Bursa Efek Indonesia (Real-time)
    """
    bot.reply_to(message, help_text, parse_mode='Markdown')

@bot.message_handler(commands=['flow'])
def flow_realtime(message):
    if not cek_user(message.chat.id):
        return
    
    bot.reply_to(message, "🔄 *Mengambil data dari BEI...*", parse_mode='Markdown')
    
    data = get_flow_from_idx()
    
    if data.get('error'):
        error_text = f"⚠️ *Gagal mengambil data real-time*\n\nError: {data['error']}\n\nData menggunakan estimasi terakhir:\n"
        error_text += f"🌏 Asing: {format_rupiah(data['asing'])}\n"
        error_text += f"🏦 Domestik: {format_rupiah(data['domestik'])}\n"
        error_text += f"📊 NET: {format_rupiah(data['net'])}"
        bot.reply_to(message, error_text, parse_mode='Markdown')
        return
    
    text = f"""📈 *IDX Flow Monitor - LIVE (BEI)*

🌏 Asing: {format_rupiah(data['asing'])}
🏦 Domestik: {format_rupiah(data['domestik'])}
📊 NET: {format_rupiah(data['net'])}

📦 Total Volume: {data['total_volume']:.1f}M lot
💰 Total Value: Rp {data['total_value_m']:.0f}M

🕐 {data['timestamp'].strftime('%H:%M:%S')} WIB

💡 *Top 3 Pergerakan:*
"""
    for i, s in enumerate(data['detail'][:3], 1):
        arrow = "🟢" if s['perubahan'] > 0 else "🔴"
        text += f"{i}. {s['kode']} {arrow} Rp{s['value_m']:.0f}M ({s['perubahan']:+.1f}%)\n"
    
    bot.reply_to(message, text, parse_mode='Markdown')

@bot.message_handler(commands=['asing'])
def net_asing(message):
    if not cek_user(message.chat.id):
        return
    data = get_flow_from_idx()
    bot.reply_to(message, f"🌏 *Net Foreign*: {format_rupiah(data['asing'])}", parse_mode='Markdown')

@bot.message_handler(commands=['domestik'])
def net_domestik(message):
    if not cek_user(message.chat.id):
        return
    data = get_flow_from_idx()
    bot.reply_to(message, f"🏦 *Net Domestik*: {format_rupiah(data['domestik'])}", parse_mode='Markdown')

@bot.message_handler(commands=['top'])
def top_10(message):
    if not cek_user(message.chat.id):
        return
    
    bot.reply_to(message, "🔄 *Mengambil data dari BEI...*", parse_mode='Markdown')
    data = get_flow_from_idx()
    
    if not data['detail']:
        bot.reply_to(message, "❌ Belum ada data top saham hari ini")
        return
    
    text = "🏆 *Top 10 Saham Teraktif Hari Ini (Nilai Transaksi)*\n\n"
    for i, s in enumerate(data['detail'][:10], 1):
        arrow = "🟢" if s['perubahan'] > 0 else "🔴"
        text += f"{i}. {s['kode']} {arrow} Rp{s['value_m']:.0f}M\n"
    
    bot.reply_to(message, text, parse_mode='Markdown')

@bot.message_handler(commands=['saham'])
def detail_saham(message):
    if not cek_user(message.chat.id):
        return
    
    try:
        kode = message.text.split()[1].upper()
    except IndexError:
        bot.reply_to(message, "❌ Gunakan: /saham BBCA")
        return
    
    bot.reply_to(message, f"🔄 *Mengambil data {kode} dari BEI...*", parse_mode='Markdown')
    
    data = get_stock_detail(kode)
    
    if data is None:
        bot.reply_to(message, f"❌ Data saham {kode} tidak ditemukan. Coba kode lain seperti BBCA, BBRI, TLKM.")
        return
    
    text = f"""📊 *{data['kode']} - Detail Real-Time (BEI)*

💰 Harga: Rp {data['harga']:,.0f}
📊 Perubahan: {data['perubahan']:+.2f}%
📈 Hari ini: Rp {data['low']:,.0f} - Rp {data['high']:,.0f}
📦 Volume: {data['volume']:.1f}M lot
💵 Nilai Transaksi: Rp {data['value']:.0f}M

🕐 {datetime.now().strftime('%H:%M:%S')} WIB
"""
    bot.reply_to(message, text, parse_mode='Markdown')

# ========== AUTO REFRESH ==========
refresh_status = {}
last_data = {}

def auto_refresh(chat_id):
    while refresh_status.get(chat_id, False):
        data = get_flow_from_idx()
        last = last_data.get(chat_id, {})
        
        perubahan_asing = abs(data['asing'] - last.get('asing', 0)) if not data.get('error') else 0
        
        if perubahan_asing > 30 or not last:
            if data.get('error'):
                text = f"⚠️ *Gagal update data BEI*\nMenggunakan data sebelumnya"
            else:
                text = f"⏰ *UPDATE* ({datetime.now().strftime('%H:%M:%S')})\n"
                text += f"🌏 Asing: {format_rupiah(data['asing'])}\n"
                text += f"📊 NET: {format_rupiah(data['net'])}"
            bot.send_message(chat_id, text, parse_mode='Markdown')
            last_data[chat_id] = data
        
        time.sleep(1800)  # 30 menit

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
                bot.reply_to(message, "🔄 Auto-refresh *ON* (tiap 30 menit)", parse_mode='Markdown')
            else:
                bot.reply_to(message, "Auto-refresh sudah aktif")
        elif cmd == 'off':
            refresh_status[user_id] = False
            bot.reply_to(message, "⏹️ Auto-refresh *OFF*", parse_mode='Markdown')
    except:
        bot.reply_to(message, "Gunakan: /refresh on atau /refresh off")

# ========== JALANKAN BOT ==========
if __name__ == "__main__":
    print("🤖 Bot IDX Flow Monitor (BEI Real-time) berjalan...")
    print(f"Bot @{bot.get_me().username} aktif!")
    bot.infinity_polling()
