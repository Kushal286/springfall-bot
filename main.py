import logging
import pandas as pd
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, filters,
    ContextTypes, ConversationHandler
)
import os
from datetime import datetime
from flask import Flask
from threading import Thread
import warnings

# Suppress Flask dev server warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

# Logging setup
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# States for conversation
GRADE10, GRADE11, GRADE12, IELTS, SAT, MAJOR = range(6)

# Load the CSV data
DATA_PATH = 'average_rank_common_universities.csv'
df = pd.read_csv(DATA_PATH)

# Session data
sessions = {}

# Common Majors for buttons
common_majors = [
    "Computer Science", "Engineering", "Business", "Finance", "Psychology", "Biology",
    "Nursing", "Education", "Marketing", "Economics", "Sociology", "Political Science",
    "Environmental Science", "Mathematics", "Chemistry", "Physics", "Public Health",
    "Accounting", "Hospitality", "Architecture"
]
major_buttons = [[m] for m in common_majors[:10]] + [["Other"]]

# Flask Web Server for UptimeRobot
app_web = Flask('')

@app_web.route('/')
def home():
    return "I'm alive!"

def run_web():
    import logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    app_web.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run_web)
    t.start()

# Start command handler
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    sessions[user_id] = {}
    await update.message.reply_text(
        "🎓 Welcome to the *UNIVERSITY FINDER* — a tool built to assist students with finding suitable U.S. universities based on academic profile.\n\nLet’s get started with a few quick questions to help guide your future!\n\nPlease enter your *Grade 10 GPA* (out of 4.0):",
        parse_mode='Markdown'
    )
    return GRADE10

async def grade10(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    sessions[update.effective_user.id]['grade_10'] = update.message.text.strip()
    await update.message.reply_text("✅ Now enter your *Grade 11 GPA*:", parse_mode='Markdown')
    return GRADE11

async def grade11(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    sessions[update.effective_user.id]['grade_11'] = update.message.text.strip()
    await update.message.reply_text("✅ Now enter your *Grade 12 GPA*:", parse_mode='Markdown')
    return GRADE12

async def grade12(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    sessions[update.effective_user.id]['grade_12'] = update.message.text.strip()
    await update.message.reply_text("✅ Enter your *IELTS score* (5.0 to 9.0):", parse_mode='Markdown')
    return IELTS

async def ielts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        score = float(update.message.text.strip())
        if not (5.0 <= score <= 9.0): raise ValueError
        sessions[update.effective_user.id]['ielts'] = score
        await update.message.reply_text("✅ SAT is optional. Enter your SAT score or type 'NA':")
        return SAT
    except ValueError:
        await update.message.reply_text("❗ Please enter a valid IELTS score between 5.0 and 9.0.")
        return IELTS

async def sat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    sessions[update.effective_user.id]['sat'] = update.message.text.strip()
    await update.message.reply_text("✅ Select your intended *major* or choose 'Other' to type manually:",
                                    reply_markup=ReplyKeyboardMarkup(major_buttons, one_time_keyboard=True))
    return MAJOR

async def major(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    sessions[user_id]['major'] = update.message.text.strip()

    try:
        user = sessions[user_id]
        g12 = float(user['grade_12'])
        major = user['major']

        filtered = df[
            df['Common Majors'].str.contains(major, case=False, na=False) &
            (
                df['GPA Requirement'].astype(str).str.contains("N/A") |
                (pd.to_numeric(df['GPA Requirement'], errors='coerce') <= g12)
            )
        ]

        if filtered.empty:
            await update.message.reply_text("❗ No matching universities found. Try another major.")
        else:
            reply = "🎓 *Suggested Universities:*\n\n"
            for _, row in filtered.head(5).iterrows():
                reply += f"🏫 *{row['University Name']}*\n"
                reply += f"📍 Location: {row['City']}, {row['State']}\n"
                reply += f"📘 Major: {row['Common Majors']}\n"
                reply += f"📊 GPA: {row['GPA Requirement']} | 🧠 SAT: {row['SAT Requirement']}\n"
                reply += f"🗣️ English: {row['English Proficiency']} | 🏛️ Type: {row['Type']}\n"
                reply += f"──────────────\n"
            reply += "\nMaintained by KUSHAL — empowering students 💙"
            await update.message.reply_text(reply, parse_mode='Markdown')

    except Exception as e:
        logger.error(f"Error: {e}")
        await update.message.reply_text("⚠️ Something went wrong. Please try again later.")

    sessions.pop(user_id, None)
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    sessions.pop(update.effective_user.id, None)
    await update.message.reply_text("❌ Cancelled. Type /start to begin again.")
    return ConversationHandler.END

# Run the bot in its own thread

def run_bot():
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    telegram_app = ApplicationBuilder().token(TOKEN).build()

    handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            GRADE10: [MessageHandler(filters.TEXT & ~filters.COMMAND, grade10)],
            GRADE11: [MessageHandler(filters.TEXT & ~filters.COMMAND, grade11)],
            GRADE12: [MessageHandler(filters.TEXT & ~filters.COMMAND, grade12)],
            IELTS: [MessageHandler(filters.TEXT & ~filters.COMMAND, ielts)],
            SAT: [MessageHandler(filters.TEXT & ~filters.COMMAND, sat)],
            MAJOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, major)],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    telegram_app.add_handler(handler)
    telegram_app.run_polling()

if __name__ == '__main__':
    keep_alive()  # Flask ping for UptimeRobot
    Thread(target=run_bot).start()  # Run Telegram bot in a background thread
