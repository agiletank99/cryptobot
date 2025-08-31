import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import analysis
import risk_management

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CAPITALE_INIZIALE_DEMO, RISK_PER_TRADE_PERCENT, RR_RATIO = 10000.0, 1.5, 2.0
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
bot_state = {"is_running": False, "mode": "DEMO", "balance": CAPITALE_INIZIALE_DEMO, "open_positions": []}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    bot_state["is_running"] = True; chat_id = update.effective_chat.id
    for job in context.job_queue.get_jobs_by_name(str(chat_id)): job.schedule_removal()
    context.job_queue.run_repeating(market_analysis_job, interval=3600, first=10, name=str(chat_id), chat_id=chat_id)
    await update.message.reply_text('✅ Bot BTC/USD AVVIATO. Analisi oraria attivata.')

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    bot_state["is_running"] = False; chat_id = update.effective_chat.id
    for job in context.job_queue.get_jobs_by_name(str(chat_id)): job.schedule_removal()
    await update.message.reply_text('🛑 Bot BTC/USD FERMATO.')

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    pos_text = "Nessuna."
    if bot_state["open_positions"]:
        p = bot_state["open_positions"][0]
        pos_text = f"**{p['direction']}** @ ${p['entry_price']}"
    status_msg = (f"*STATO SISTEMA BTC/USD*\n-------------------\n" # <<< MODIFICA QUI
                  f"*- Stato:* {'🟢 ATTIVO' if bot_state['is_running'] else '🔴 FERMO'}\n"
                  f"*- Modalità:* {bot_state['mode']}\n"
                  f"*- Bilancio:* ${bot_state['balance']:,.2f}\n"
                  f"*- Posizione Aperta:* {pos_text}")
    await update.message.reply_text(status_msg, parse_mode='Markdown')
    
# ... (le funzioni demo_mode, real_mode, balance, positions rimangono identiche) ...
async def demo_mode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    bot_state["mode"] = "DEMO"; await update.message.reply_text('🎮 Modalità **DEMO** attivata.', parse_mode='Markdown')
async def real_mode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    bot_state["mode"] = "REALE"; await update.message.reply_text('⚠️ Modalità **REALE** attivata.', parse_mode='Markdown')
async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(f"💰 Bilancio attuale: **${bot_state['balance']:,.2f}**", parse_mode='Markdown')
async def positions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not bot_state["open_positions"]: await update.message.reply_text("Nessuna posizione aperta."); return
    p = bot_state["open_positions"][0]
    pos_details = (f"🔍 *POSIZIONE APERTA BTC/USD*\n-------------------\n" # <<< MODIFICA QUI
                   f"*- Direzione:* {p['direction']}\n*- Entrata:* ${p['entry_price']:.2f}\n"
                   f"*- Stop Loss:* ${p['stop_loss']:.2f}\n*- Take Profit:* ${p['take_profit']:.2f}")
    await update.message.reply_text(pos_details, parse_mode='Markdown')

async def market_analysis_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    if not bot_state["is_running"]: return
    chat_id = context.job.chat_id
    status, data_or_error_msg = analysis.get_market_data()
    
    if status == "ERRORE":
        await context.bot.send_message(chat_id, f"⚠️ Errore Dati BTC: {data_or_error_msg}"); return # <<< MODIFICA QUI
        
    data = data_or_error_msg
    decisione, mot_tech, mot_fond, price, atr, _ = analysis.analyze_from_data(data)
    
    if bot_state["open_positions"]:
        await context.bot.send_message(chat_id, "ℹ️ Posizione BTC già aperta. Monitoraggio..."); return # <<< MODIFICA QUI
        
    if decisione in ["APRI LONG", "APRI SHORT"]:
        direction = "LONG" if "LONG" in decisione else "SHORT"
        sl, tp = risk_management.calculate_sl_tp(price, direction, atr, RR_RATIO)
        position = {"direction": direction, "entry_price": price, "stop_loss": sl, "take_profit": tp}
        bot_state["open_positions"].append(position)
        signal_msg = (f"{'🟢' if direction == 'LONG' else '🔴'} *NUOVO SEGNALE: {direction} BTC/USD*\n" # <<< MODIFICA QUI
                      f"-------------------\n"
                      f"*- Entry:* ${price:,.2f}\n*- SL:* ${sl:,.2f}\n*- TP:* ${tp:,.2f}\n\n"
                      f"*Tecnica:* {mot_tech}\n*Fondamentale:* {mot_fond}")
        await context.bot.send_message(chat_id, text=signal_msg, parse_mode='Markdown')
    else:
        await context.bot.send_message(chat_id, f"✅ Analisi BTC OK. Decisione: MANTIENI. ({mot_tech})") # <<< MODIFICA QUI

def main() -> None:
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    commands = {"start": start, "stop": stop, "status": status, "demo": demo_mode, "real": real_mode, "balance": balance, "positions": positions}
    for name, func in commands.items():
        application.add_handler(CommandHandler(name, func))
    application.run_polling()

if __name__ == '__main__':
    main()
