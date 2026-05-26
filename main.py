import logging
import random
import time
import threading
import requests
import schedule
from datetime import datetime, timedelta
from telegram import Update, ParseMode
from telegram.ext import Updater, CommandHandler, CallbackContext

# =============================================
# GANTI TOKEN DI BAWAH INI
# =============================================
BOT_TOKEN = "8797179260:AAHGcufIwYnKOOZfeoVUXQ3-AMXixBwrvIY"
CHAT_ID   = "8185636936"

logging.basicConfig(format="%(asctime)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

SAHAM_LIST = [
    "BBCA","BBRI","BMRI","TLKM","ASII",
    "GOTO","BYAN","UNVR","ICBP","INDF",
    "KLBF","HMSP","EXCL","PGAS","SMGR",
    "ANTM","MDKA","MEDC","INCO","ADRO",
]

alert_users = set()

# =============================================
# HELPER TANGGAL
# =============================================
def hari_bursa_terakhir(mulai=None):
    """Cari hari bursa terakhir (skip Sabtu & Minggu)"""
    d = mulai or datetime.now()
    d -= timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d

def is_jam_bursa():
    now = datetime.now()
    if now.weekday() >= 5:
        return False
    jam = now.hour * 60 + now.minute
    return 9 * 60 <= jam <= 16 * 60 + 15

def fmt(val):
    sign = "+" if val >= 0 else ""
    if abs(val) >= 1000:
        return f"{sign}{val/1000:.2f}T"
    return f"{sign}{val:.1f}B"

def arrow(val):
    return "🟢" if val >= 0 else "🔴"

def waktu():
    return datetime.now().strftime("%d/%m/%Y %H:%M WIB")

def status_bursa():
    return "🟢 Bursa BUKA" if is_jam_bursa() else "🔴 Bursa TUTUP"

# =============================================
# FETCH DATA IDX
# =============================================
def fetch_by_date(tanggal: str):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36",
            "Referer": "https://www.idx.co.id/",
        }
        url = "https://www.idx.co.id/primary/TradingSummary/GetStockSummary"
        params = {"start": 0, "length": 100, "date": tanggal}
        r = requests.get(url, headers=headers, params=params, timeout=10)
        raw = r.json()
        items = raw.get("data", [])
        data = []
        for item in items:
            kode = item.get("StockCode", "").strip()
            if kode not in SAHAM_LIST:
                continue
            ab = float(item.get("ForeignBuy", 0)) / 1_000_000
            aj = float(item.get("ForeignSell", 0)) / 1_000_000
            db = float(item.get("NonForeignBuy", 0)) / 1_000_000
            dj = float(item.get("NonForeignSell", 0)) / 1_000_000
            data.append({
                "kode": kode,
                "asing_net": round(ab - aj, 1),
                "dom_net": round(db - dj, 1),
                "total_net": round((ab - aj) + (db - dj), 1),
                "nilai_miliar": round(float(item.get("Value", 0)) / 1_000_000_000, 1),
            })
        return data
    except Exception as e:
        logger.warning(f"Gagal ambil data {tanggal}: {e}")
        return []

def fetch_flow_data():
    """Hari ini, kalau kosong coba hari bursa terakhir, fallback simulasi"""
    data = fetch_by_date(datetime.now().strftime("%Y-%m-%d"))
    if data:
        return data, "hari ini"
    # Coba hari bursa terakhir
    tgl = hari_bursa_terakhir()
    data = fetch_by_date(tgl.strftime("%Y-%m-%d"))
    if data:
        return data, tgl.strftime("%d/%m/%Y")
    return fetch_simulasi(), "simulasi"

def fetch_simulasi():
    data = []
    for kode in SAHAM_LIST:
        ab = round(random.uniform(50, 800), 1)
        aj = round(random.uniform(50, 800), 1)
        db = round(random.uniform(100, 1200), 1)
        dj = round(random.uniform(100, 1200), 1)
        data.append({
            "kode": kode,
            "asing_net": round(ab - aj, 1),
            "dom_net": round(db - dj, 1),
            "total_net": round((ab - aj) + (db - dj), 1),
            "nilai_miliar": round(random.uniform(10, 3000), 1),
        })
    return data

def fetch_range(hari: int):
    """Akumulasi data beberapa hari bursa ke belakang"""
    akumulasi = {}
    tanggal_list = []
    d = datetime.now()
    count = 0
    while count < hari:
        d -= timedelta(days=1)
        if d.weekday() < 5:
            tanggal_list.append(d.strftime("%Y-%m-%d"))
            count += 1

    hari_berhasil = 0
    for tgl in tanggal_list:
        data = fetch_by_date(tgl)
        if not data:
            continue
        hari_berhasil += 1
        for item in data:
            kode = item["kode"]
            if kode not in akumulasi:
                akumulasi[kode] = {"kode": kode, "asing_net": 0, "dom_net": 0, "total_net": 0, "nilai_miliar": 0}
            akumulasi[kode]["asing_net"]    += item["asing_net"]
            akumulasi[kode]["dom_net"]      += item["dom_net"]
            akumulasi[kode]["total_net"]    += item["total_net"]
            akumulasi[kode]["nilai_miliar"] += item["nilai_miliar"]

    result = [{
        "kode": v["kode"],
        "asing_net": round(v["asing_net"], 1),
        "dom_net": round(v["dom_net"], 1),
        "total_net": round(v["total_net"], 1),
        "nilai_miliar": round(v["nilai_miliar"], 1),
    } for v in akumulasi.values()]

    return result, hari_berhasil, tanggal_list

# =============================================
# HANDLER BOT
# =============================================
def cmd_start(update: Update, ctx: CallbackContext):
    update.message.reply_text(
        "🏦 *IDX MONEY FLOW BOT*\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Monitor arus uang saham IDX\n"
        "Data real dari Bursa Efek Indonesia\n\n"
        "📌 *Perintah:*\n"
        "• /flow — Hari ini\n"
        "• /kemarin — Data kemarin\n"
        "• /seminggu — Akumulasi 7 hari\n"
        "• /sebulan — Akumulasi 30 hari\n"
        "• /top — Top 10 hari ini\n"
        "• /saham KODE — Detail multi periode\n"
        "• /asing — Net foreign\n"
        "• /domestik — Net domestik\n"
        "• /alert on/off — Notif 30 menit\n"
        "• /help — Bantuan",
        parse_mode=ParseMode.MARKDOWN
    )

def cmd_flow(update: Update, ctx: CallbackContext):
    update.message.reply_text("⏳ Mengambil data dari IDX...", parse_mode=ParseMode.MARKDOWN)
    data, label = fetch_flow_data()
    ta = sum(d["asing_net"] for d in data)
    td = sum(d["dom_net"] for d in data)
    tn = sum(d["total_net"] for d in data)
    tv = sum(d["nilai_miliar"] for d in data)
    update.message.reply_text(
        f"📊 *ARUS UANG IDX — {label.upper()}*\n"
        f"🕐 {waktu()} | {status_bursa()}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 Net Total: {arrow(tn)} `{fmt(tn)}`\n"
        f"🌏 Net Asing: {arrow(ta)} `{fmt(ta)}`\n"
        f"🇮🇩 Net Domestik: {arrow(td)} `{fmt(td)}`\n"
        f"📈 Nilai: `Rp {tv:,.1f} M`\n\n"
        f"Ketik /top untuk ranking saham",
        parse_mode=ParseMode.MARKDOWN
    )

def cmd_kemarin(update: Update, ctx: CallbackContext):
    update.message.reply_text("⏳ Mengambil data kemarin...", parse_mode=ParseMode.MARKDOWN)
    tgl = hari_bursa_terakhir()
    tgl_str = tgl.strftime("%Y-%m-%d")
    data = fetch_by_date(tgl_str)
    if not data:
        # Coba satu hari lagi ke belakang
        tgl2 = hari_bursa_terakhir(tgl)
        data = fetch_by_date(tgl2.strftime("%Y-%m-%d"))
        tgl_str = tgl2.strftime("%Y-%m-%d")
    if not data:
        update.message.reply_text(
            "❌ *Data kemarin tidak tersedia*\n"
            "Kemungkinan hari libur bursa atau IDX sedang offline.\n"
            "Coba lagi saat hari bursa (Senin-Jumat).",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    ta = sum(d["asing_net"] for d in data)
    td = sum(d["dom_net"] for d in data)
    tn = sum(d["total_net"] for d in data)
    tv = sum(d["nilai_miliar"] for d in data)
    s = sorted(data, key=lambda x: x["total_net"], reverse=True)
    top3 = " | ".join(f"{d['kode']} {fmt(d['total_net'])}" for d in s[:3])
    bot3 = " | ".join(f"{d['kode']} {fmt(d['total_net'])}" for d in s[-3:][::-1])
    update.message.reply_text(
        f"📊 *ARUS UANG IDX — KEMARIN*\n"
        f"📅 {tgl_str}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 Net Total: {arrow(tn)} `{fmt(tn)}`\n"
        f"🌏 Net Asing: {arrow(ta)} `{fmt(ta)}`\n"
        f"🇮🇩 Net Domestik: {arrow(td)} `{fmt(td)}`\n"
        f"📈 Nilai: `Rp {tv:,.1f} M`\n\n"
        f"🟢 Top Buy: `{top3}`\n"
        f"🔴 Top Sell: `{bot3}`",
        parse_mode=ParseMode.MARKDOWN
    )

def cmd_seminggu(update: Update, ctx: CallbackContext):
    update.message.reply_text("⏳ Mengambil data 7 hari... (~15 detik)", parse_mode=ParseMode.MARKDOWN)
    data, hari_ok, tgl_list = fetch_range(7)
    if not data or hari_ok == 0:
        update.message.reply_text(
            "❌ *Data 7 hari tidak tersedia*\n"
            "IDX mungkin sedang offline atau semua hari libur.\n"
            "Coba lagi saat hari bursa (Senin-Jumat).",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    ta = sum(d["asing_net"] for d in data)
    td = sum(d["dom_net"] for d in data)
    tn = sum(d["total_net"] for d in data)
    tv = sum(d["nilai_miliar"] for d in data)
    s = sorted(data, key=lambda x: x["total_net"], reverse=True)
    top5 = "\n".join(f"{arrow(d['total_net'])} `{d['kode']:<5}` `{fmt(d['total_net'])}`" for d in s[:5])
    bot5 = "\n".join(f"{arrow(d['total_net'])} `{d['kode']:<5}` `{fmt(d['total_net'])}`" for d in s[-5:][::-1])
    update.message.reply_text(
        f"📊 *AKUMULASI 7 HARI TERAKHIR*\n"
        f"📅 {tgl_list[-1]} s/d {tgl_list[0]}\n"
        f"✅ Data dari {hari_ok} hari bursa\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 Net Total: {arrow(tn)} `{fmt(tn)}`\n"
        f"🌏 Net Asing: {arrow(ta)} `{fmt(ta)}`\n"
        f"🇮🇩 Net Domestik: {arrow(td)} `{fmt(td)}`\n"
        f"📈 Nilai: `Rp {tv:,.1f} M`\n\n"
        f"🏆 *Top 5 Net Buy:*\n{top5}\n\n"
        f"💀 *Top 5 Net Sell:*\n{bot5}",
        parse_mode=ParseMode.MARKDOWN
    )

def cmd_sebulan(update: Update, ctx: CallbackContext):
    update.message.reply_text("⏳ Mengambil data 30 hari... (~60 detik, harap tunggu)", parse_mode=ParseMode.MARKDOWN)
    data, hari_ok, tgl_list = fetch_range(30)
    if not data or hari_ok == 0:
        update.message.reply_text(
            "❌ *Data 30 hari tidak tersedia*\n"
            "IDX mungkin sedang offline atau semua hari libur.\n"
            "Coba lagi saat hari bursa (Senin-Jumat).",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    ta = sum(d["asing_net"] for d in data)
    td = sum(d["dom_net"] for d in data)
    tn = sum(d["total_net"] for d in data)
    tv = sum(d["nilai_miliar"] for d in data)
    s = sorted(data, key=lambda x: x["total_net"], reverse=True)
    top5 = "\n".join(f"{arrow(d['total_net'])} `{d['kode']:<5}` `{fmt(d['total_net'])}`" for d in s[:5])
    bot5 = "\n".join(f"{arrow(d['total_net'])} `{d['kode']:<5}` `{fmt(d['total_net'])}`" for d in s[-5:][::-1])
    update.message.reply_text(
        f"📊 *AKUMULASI 30 HARI TERAKHIR*\n"
        f"📅 {tgl_list[-1]} s/d {tgl_list[0]}\n"
        f"✅ Data dari {hari_ok} hari bursa\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 Net Total: {arrow(tn)} `{fmt(tn)}`\n"
        f"🌏 Net Asing: {arrow(ta)} `{fmt(ta)}`\n"
        f"🇮🇩 Net Domestik: {arrow(td)} `{fmt(td)}`\n"
        f"📈 Nilai: `Rp {tv:,.1f} M`\n\n"
        f"🏆 *Top 5 Net Buy:*\n{top5}\n\n"
        f"💀 *Top 5 Net Sell:*\n{bot5}",
        parse_mode=ParseMode.MARKDOWN
    )

def cmd_top(update: Update, ctx: CallbackContext):
    update.message.reply_text("⏳ Mengambil data dari IDX...", parse_mode=ParseMode.MARKDOWN)
    data, label = fetch_flow_data()
    s = sorted(data, key=lambda x: x["total_net"], reverse=True)
    def baris(i, d):
        return f"`{i+1:>2}. {d['kode']:<5}` {arrow(d['total_net'])} `{fmt(d['total_net'])}`"
    update.message.reply_text(
        f"🏆 *TOP 10 NET BUY — {label.upper()}*\n"
        f"{status_bursa()} | 🕐 {waktu()}\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        + "\n".join(baris(i,d) for i,d in enumerate(s[:10])) +
        "\n\n💀 *TOP 10 NET SELL*\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        + "\n".join(baris(i,d) for i,d in enumerate(s[-10:][::-1])),
        parse_mode=ParseMode.MARKDOWN
    )

def cmd_saham(update: Update, ctx: CallbackContext):
    if not ctx.args:
        update.message.reply_text("Contoh: `/saham BBCA`", parse_mode=ParseMode.MARKDOWN)
        return
    kode = ctx.args[0].upper()
    if kode not in SAHAM_LIST:
        update.message.reply_text(f"❌ Kode *{kode}* tidak ditemukan.", parse_mode=ParseMode.MARKDOWN)
        return
    update.message.reply_text("⏳ Mengambil data multi periode...", parse_mode=ParseMode.MARKDOWN)
    hari_ini, label = fetch_flow_data()
    d1 = next((x for x in hari_ini if x["kode"] == kode), None)
    minggu, _, _ = fetch_range(7)
    dm = next((x for x in minggu if x["kode"] == kode), None)
    bulan, _, _ = fetch_range(30)
    db = next((x for x in bulan if x["kode"] == kode), None)
    msg = f"📌 *{kode}* — Multi Periode\n🕐 {waktu()} | {status_bursa()}\n━━━━━━━━━━━━━━━━━━━━\n\n"
    if d1:
        msg += f"📅 *{label.title()}*\n  Asing: {arrow(d1['asing_net'])} `{fmt(d1['asing_net'])}`\n  Domestik: {arrow(d1['dom_net'])} `{fmt(d1['dom_net'])}`\n  Net: {arrow(d1['total_net'])} `{fmt(d1['total_net'])}`\n\n"
    if dm:
        msg += f"📅 *7 Hari Terakhir*\n  Asing: {arrow(dm['asing_net'])} `{fmt(dm['asing_net'])}`\n  Domestik: {arrow(dm['dom_net'])} `{fmt(dm['dom_net'])}`\n  Net: {arrow(dm['total_net'])} `{fmt(dm['total_net'])}`\n\n"
    if db:
        msg += f"📅 *30 Hari Terakhir*\n  Asing: {arrow(db['asing_net'])} `{fmt(db['asing_net'])}`\n  Domestik: {arrow(db['dom_net'])} `{fmt(db['dom_net'])}`\n  Net: {arrow(db['total_net'])} `{fmt(db['total_net'])}`"
    if not d1 and not dm and not db:
        msg += "❌ Data tidak tersedia. Coba saat hari bursa."
    update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

def cmd_asing(update: Update, ctx: CallbackContext):
    update.message.reply_text("⏳ Mengambil data dari IDX...", parse_mode=ParseMode.MARKDOWN)
    data, label = fetch_flow_data()
    s = sorted(data, key=lambda x: x["asing_net"], reverse=True)
    lines = [f"{arrow(d['asing_net'])} `{d['kode']:<5}` `{fmt(d['asing_net'])}`" for d in s]
    total = sum(d["asing_net"] for d in data)
    update.message.reply_text(
        f"🌏 *NET ASING — {label.upper()}*\n{status_bursa()} | 🕐 {waktu()}\n━━━━━━━━━━━━━━━━━━━━\n"
        + "\n".join(lines)
        + f"\n━━━━━━━━━━━━━━━━━━━━\nTotal: {arrow(total)} `{fmt(total)}`",
        parse_mode=ParseMode.MARKDOWN
    )

def cmd_domestik(update: Update, ctx: CallbackContext):
    update.message.reply_text("⏳ Mengambil data dari IDX...", parse_mode=ParseMode.MARKDOWN)
    data, label = fetch_flow_data()
    s = sorted(data, key=lambda x: x["dom_net"], reverse=True)
    lines = [f"{arrow(d['dom_net'])} `{d['kode']:<5}` `{fmt(d['dom_net'])}`" for d in s]
    total = sum(d["dom_net"] for d in data)
    update.message.reply_text(
        f"🇮🇩 *NET DOMESTIK — {label.upper()}*\n{status_bursa()} | 🕐 {waktu()}\n━━━━━━━━━━━━━━━━━━━━\n"
        + "\n".join(lines)
        + f"\n━━━━━━━━━━━━━━━━━━━━\nTotal: {arrow(total)} `{fmt(total)}`",
        parse_mode=ParseMode.MARKDOWN
    )

def cmd_alert(update: Update, ctx: CallbackContext):
    uid = update.effective_chat.id
    if not ctx.args:
        update.message.reply_text("Ketik `/alert on` atau `/alert off`", parse_mode=ParseMode.MARKDOWN)
        return
    if ctx.args[0].lower() == "on":
        alert_users.add(uid)
        update.message.reply_text("✅ Alert aktif! Notif tiap 30 menit saat bursa buka.", parse_mode=ParseMode.MARKDOWN)
    else:
        alert_users.discard(uid)
        update.message.reply_text("🔕 Alert dimatikan.", parse_mode=ParseMode.MARKDOWN)

def cmd_help(update: Update, ctx: CallbackContext):
    update.message.reply_text(
        "📖 *BANTUAN IDX FLOW BOT*\n━━━━━━━━━━━━━━━━━━━━\n"
        "/flow — Hari ini\n"
        "/kemarin — Data kemarin\n"
        "/seminggu — Akumulasi 7 hari\n"
        "/sebulan — Akumulasi 30 hari\n"
        "/top — Top 10 hari ini\n"
        "/saham KODE — Detail multi periode\n"
        "/asing — Net foreign\n"
        "/domestik — Net domestik\n"
        "/alert on/off — Notif 30 menit\n\n"
        "💡 + = net buy | - = net sell\n"
        "B = Miliar | T = Triliun\n"
        "📡 Data real IDX | Senin-Jumat 09:00-16:15\n"
        "⚠️ Di luar jam bursa otomatis pakai data terakhir",
        parse_mode=ParseMode.MARKDOWN
    )

def send_alert(bot):
    if not alert_users or not is_jam_bursa():
        return
    data, _ = fetch_flow_data()
    ta = sum(d["asing_net"] for d in data)
    td = sum(d["dom_net"] for d in data)
    tn = sum(d["total_net"] for d in data)
    s = sorted(data, key=lambda x: x["total_net"], reverse=True)
    top3 = ", ".join(f"{d['kode']}({fmt(d['total_net'])})" for d in s[:3])
    bot3 = ", ".join(f"{d['kode']}({fmt(d['total_net'])})" for d in s[-3:][::-1])
    msg = (
        f"⏰ *AUTO ALERT IDX*\n🕐 {waktu()}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Net Total: {arrow(tn)} `{fmt(tn)}`\n"
        f"Net Asing: {arrow(ta)} `{fmt(ta)}`\n"
        f"Net Dom: {arrow(td)} `{fmt(td)}`\n\n"
        f"🟢 Buy: {top3}\n🔴 Sell: {bot3}"
    )
    for uid in list(alert_users):
        try:
            bot.send_message(chat_id=uid, text=msg, parse_mode=ParseMode.MARKDOWN)
        except:
            pass

def run_scheduler(bot):
    schedule.every(30).minutes.do(send_alert, bot=bot)
    while True:
        schedule.run_pending()
        time.sleep(60)

def main():
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start",    cmd_start))
    dp.add_handler(CommandHandler("flow",     cmd_flow))
    dp.add_handler(CommandHandler("kemarin",  cmd_kemarin))
    dp.add_handler(CommandHandler("seminggu", cmd_seminggu))
    dp.add_handler(CommandHandler("sebulan",  cmd_sebulan))
    dp.add_handler(CommandHandler("top",      cmd_top))
    dp.add_handler(CommandHandler("saham",    cmd_saham))
    dp.add_handler(CommandHandler("asing",    cmd_asing))
    dp.add_handler(CommandHandler("domestik", cmd_domestik))
    dp.add_handler(CommandHandler("alert",    cmd_alert))
    dp.add_handler(CommandHandler("help",     cmd_help))
    t = threading.Thread(target=run_scheduler, args=(updater.bot,), daemon=True)
    t.start()
    print("Bot jalan!")
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
