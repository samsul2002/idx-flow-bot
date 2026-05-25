import os
import logging
import random
import time
import threading
import schedule
from datetime import datetime
from telegram import Update, ParseMode
from telegram.ext import Updater, CommandHandler, CallbackContext

# =============================================
# GANTI INI DENGAN TOKEN BARU DARI BOTFATHER
# =============================================
BOT_TOKEN = "8797179260:AAH9e7MpitzJaYSR5Qpw04lrUuK7glnm23A"
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

def fetch_flow_data():
    data = []
    for kode in SAHAM_LIST:
        ab = round(random.uniform(50, 800), 1)
        aj = round(random.uniform(50, 800), 1)
        db = round(random.uniform(100, 1200), 1)
        dj = round(random.uniform(100, 1200), 1)
        data.append({
            "kode": kode,
            "asing_beli": ab, "asing_jual": aj,
            "asing_net": round(ab - aj, 1),
            "dom_beli": db, "dom_jual": dj,
            "dom_net": round(db - dj, 1),
            "total_net": round((ab - aj) + (db - dj), 1),
            "volume": random.randint(5_000_000, 800_000_000),
            "nilai_miliar": round(random.uniform(10, 3000), 1),
        })
    return data

def fmt(val):
    sign = "+" if val >= 0 else ""
    if abs(val) >= 1000:
        return f"{sign}{val/1000:.2f}T"
    return f"{sign}{val:.1f}B"

def arrow(val):
    return "🟢" if val >= 0 else "🔴"

def waktu():
    return datetime.now().strftime("%d/%m/%Y %H:%M WIB")

def cmd_start(update: Update, ctx: CallbackContext):
    update.message.reply_text(
        "🏦 *IDX MONEY FLOW BOT*\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Monitor arus uang saham IDX\n\n"
        "📌 *Perintah:*\n"
        "• /flow — Ringkasan hari ini\n"
        "• /top — Top 10 net buy & sell\n"
        "• /saham KODE — Detail 1 saham\n"
        "• /asing — Net foreign semua saham\n"
        "• /domestik — Net domestik semua saham\n"
        "• /alert on/off — Notif otomatis 30 menit\n"
        "• /help — Bantuan",
        parse_mode=ParseMode.MARKDOWN
    )

def cmd_flow(update: Update, ctx: CallbackContext):
    data = fetch_flow_data()
    ta = sum(d["asing_net"] for d in data)
    td = sum(d["dom_net"] for d in data)
    tn = sum(d["total_net"] for d in data)
    tv = sum(d["nilai_miliar"] for d in data)
    update.message.reply_text(
        f"📊 *ARUS UANG IDX*\n"
        f"🕐 {waktu()}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 Net Total: {arrow(tn)} `{fmt(tn)}`\n"
        f"🌏 Net Asing: {arrow(ta)} `{fmt(ta)}`\n"
        f"🇮🇩 Net Domestik: {arrow(td)} `{fmt(td)}`\n"
        f"📈 Nilai Transaksi: `Rp {tv:,.1f} M`\n\n"
        f"Ketik /top untuk lihat ranking saham",
        parse_mode=ParseMode.MARKDOWN
    )

def cmd_top(update: Update, ctx: CallbackContext):
    data = fetch_flow_data()
    s = sorted(data, key=lambda x: x["total_net"], reverse=True)
    buy  = s[:10]
    sell = s[-10:][::-1]
    def baris(i, d):
        return f"`{i+1:>2}. {d['kode']:<5}` {arrow(d['total_net'])} `{fmt(d['total_net'])}`"
    update.message.reply_text(
        "🏆 *TOP 10 NET BUY*\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        + "\n".join(baris(i,d) for i,d in enumerate(buy)) +
        "\n\n💀 *TOP 10 NET SELL*\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        + "\n".join(baris(i,d) for i,d in enumerate(sell)) +
        f"\n\n🕐 {waktu()}",
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
    data = fetch_flow_data()
    d = next(x for x in data if x["kode"] == kode)
    update.message.reply_text(
        f"📌 *{kode}*\n"
        f"🕐 {waktu()}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🌏 *Asing*\n"
        f"  Beli: `{fmt(d['asing_beli'])}` | Jual: `{fmt(d['asing_jual'])}`\n"
        f"  Net: {arrow(d['asing_net'])} `{fmt(d['asing_net'])}`\n\n"
        f"🇮🇩 *Domestik*\n"
        f"  Beli: `{fmt(d['dom_beli'])}` | Jual: `{fmt(d['dom_jual'])}`\n"
        f"  Net: {arrow(d['dom_net'])} `{fmt(d['dom_net'])}`\n\n"
        f"💰 *Total Net:* {arrow(d['total_net'])} `{fmt(d['total_net'])}`\n"
        f"📊 Nilai: `Rp {d['nilai_miliar']:,.1f} M`",
        parse_mode=ParseMode.MARKDOWN
    )

def cmd_asing(update: Update, ctx: CallbackContext):
    data = fetch_flow_data()
    s = sorted(data, key=lambda x: x["asing_net"], reverse=True)
    lines = [f"{arrow(d['asing_net'])} `{d['kode']:<5}` `{fmt(d['asing_net'])}`" for d in s]
    total = sum(d["asing_net"] for d in data)
    update.message.reply_text(
        "🌏 *NET ASING*\n━━━━━━━━━━━━━━━━━━━━\n"
        + "\n".join(lines)
        + f"\n━━━━━━━━━━━━━━━━━━━━\nTotal: {arrow(total)} `{fmt(total)}`",
        parse_mode=ParseMode.MARKDOWN
    )

def cmd_domestik(update: Update, ctx: CallbackContext):
    data = fetch_flow_data()
    s = sorted(data, key=lambda x: x["dom_net"], reverse=True)
    lines = [f"{arrow(d['dom_net'])} `{d['kode']:<5}` `{fmt(d['dom_net'])}`" for d in s]
    total = sum(d["dom_net"] for d in data)
    update.message.reply_text(
        "🇮🇩 *NET DOMESTIK*\n━━━━━━━━━━━━━━━━━━━━\n"
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
        update.message.reply_text("✅ Alert aktif! Notif tiap 30 menit.", parse_mode=ParseMode.MARKDOWN)
    else:
        alert_users.discard(uid)
        update.message.reply_text("🔕 Alert dimatikan.", parse_mode=ParseMode.MARKDOWN)

def cmd_help(update: Update, ctx: CallbackContext):
    update.message.reply_text(
        "📖 *BANTUAN*\n━━━━━━━━━━━━━━━━━━━━\n"
        "/flow — Ringkasan arus hari ini\n"
        "/top — Top 10 buy & sell\n"
        "/saham KODE — Detail saham\n"
        "/asing — Net foreign\n"
        "/domestik — Net domestik\n"
        "/alert on — Notif 30 menit\n"
        "/alert off — Stop notif\n\n"
        "💡 + = net buy | - = net sell\n"
        "B = Miliar | T = Triliun",
        parse_mode=ParseMode.MARKDOWN
    )

def send_alert(bot):
    if not alert_users:
        return
    data = fetch_flow_data()
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
  
