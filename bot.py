import logging
import os
from datetime import datetime, timedelta
from functools import wraps

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes

from database import Database

DEFAULT_SUMMARY_TIME = "09:00"

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
AUTHORIZED_USER_ID = int(os.environ["AUTHORIZED_USER_ID"])
DAILY_SUMMARY_TIME = os.environ.get("DAILY_SUMMARY_TIME", DEFAULT_SUMMARY_TIME)

db = Database()
scheduler = AsyncIOScheduler()


# --- Auth decorator ---

def authorized(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != AUTHORIZED_USER_ID:
            await update.message.reply_text("Unauthorized.")
            return
        return await func(update, context)
    return wrapper


# --- Commands ---

@authorized
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 *Hey Anton!*\n\nTrack your goals and get appointment reminders.\n\nType /help to see all commands.",
        parse_mode="Markdown",
    )


@authorized
async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    summary_time = db.get_setting("summary_time", DAILY_SUMMARY_TIME)
    await update.message.reply_text(
        "📋 *Commands*\n\n"
        "*Goals (daily):*\n"
        "/addgoal short|long <text> — Add a goal\n"
        "/goals — List all goals\n"
        "/done <id> — Mark goal as done\n"
        "/delgoal <id> — Delete a goal\n\n"
        "*Vision (5/10/15y):*\n"
        "/addgoal 5y|10y|15y <text> — Add a vision goal\n"
        "/vision — Show 5/10/15y vision\n\n"
        "*Appointments:*\n"
        "/addappt DD/MM/YYYY HH:MM <title> — Add appointment\n"
        "/appts — List upcoming appointments\n"
        "/delappt <id> — Delete an appointment\n\n"
        "*Daily Summary:*\n"
        "/summary — Send summary now\n"
        f"/setsummary HH:MM — Change daily summary time (currently {summary_time})\n\n"
        "_You'll get a reminder 30 min before each appointment._",
        parse_mode="Markdown",
    )


GOAL_TYPES = ("short", "long", "5y", "10y", "15y")
GOAL_TYPE_LABELS = {
    "short": "short-term",
    "long": "long-term",
    "5y": "5-year vision (2030)",
    "10y": "10-year vision (2035)",
    "15y": "15-year vision (2040)",
}


@authorized
async def add_goal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 2 or args[0] not in GOAL_TYPES:
        await update.message.reply_text(
            "Usage: /addgoal <type> <text>\n"
            "Types: short, long, 5y, 10y, 15y"
        )
        return
    goal_type = args[0]
    text = " ".join(args[1:])
    goal_id = db.add_goal(goal_type, text)
    await update.message.reply_text(
        f"✅ Goal #{goal_id} added ({GOAL_TYPE_LABELS[goal_type]}):\n{text}"
    )


@authorized
async def list_goals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    goals = db.get_goals()
    daily_goals = [g for g in goals if g["type"] in ("short", "long")]
    if not daily_goals:
        await update.message.reply_text(
            "No daily goals yet. Add one with /addgoal short|long <text>\n"
            "For vision goals use /vision"
        )
        return

    short_goals = [g for g in daily_goals if g["type"] == "short" and not g["done"]]
    long_goals = [g for g in daily_goals if g["type"] == "long" and not g["done"]]
    done_goals = [g for g in daily_goals if g["done"]]

    lines = ["🎯 *Your Goals*\n"]
    if short_goals:
        lines.append("*Short-term:*")
        for g in short_goals:
            lines.append(f"  #{g['id']} {g['text']}")
        lines.append("")
    if long_goals:
        lines.append("*Long-term:*")
        for g in long_goals:
            lines.append(f"  #{g['id']} {g['text']}")
        lines.append("")
    if done_goals:
        lines.append("*Completed:*")
        for g in done_goals[:5]:
            lines.append(f"  ✓ #{g['id']} {g['text']}")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


@authorized
async def list_vision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    goals = db.get_goals()
    vision_goals = [g for g in goals if g["type"] in ("5y", "10y", "15y") and not g["done"]]
    if not vision_goals:
        await update.message.reply_text(
            "No vision goals yet. Add one with /addgoal 5y|10y|15y <text>"
        )
        return

    sections = [
        ("5y", "🏁 *5-Year Vision — 2030*"),
        ("10y", "🚀 *10-Year Vision — 2035*"),
        ("15y", "🌟 *15-Year Vision — 2040*"),
    ]
    lines = ["🔭 *Your Vision*\n"]
    for type_key, header in sections:
        bucket = [g for g in vision_goals if g["type"] == type_key]
        if bucket:
            lines.append(header)
            for g in bucket:
                lines.append(f"  #{g['id']} {g['text']}")
            lines.append("")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


@authorized
async def mark_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /done <id>")
        return
    try:
        goal_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Please provide a valid goal ID.")
        return
    if db.mark_goal_done(goal_id):
        await update.message.reply_text(f"✅ Goal #{goal_id} marked as done!")
    else:
        await update.message.reply_text(f"Goal #{goal_id} not found or already done.")


@authorized
async def delete_goal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /delgoal <id>")
        return
    try:
        goal_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Please provide a valid goal ID.")
        return
    if db.delete_goal(goal_id):
        await update.message.reply_text(f"🗑️ Goal #{goal_id} deleted.")
    else:
        await update.message.reply_text(f"Goal #{goal_id} not found.")


@authorized
async def add_appointment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 3:
        await update.message.reply_text(
            "Usage: /addappt DD/MM/YYYY HH:MM <title>\nExample: /addappt 15/04/2025 14:30 Doctor appointment"
        )
        return
    try:
        dt = datetime.strptime(f"{args[0]} {args[1]}", "%d/%m/%Y %H:%M")
    except ValueError:
        await update.message.reply_text(
            "Invalid date/time. Use: DD/MM/YYYY HH:MM\nExample: 15/04/2025 14:30"
        )
        return

    if dt <= datetime.now():
        await update.message.reply_text("That date is in the past. Please use a future date/time.")
        return

    title = " ".join(args[2:])
    appt_id = db.add_appointment(dt, title)

    # Schedule 30-min reminder
    reminder_time = dt - timedelta(minutes=30)
    if reminder_time > datetime.now():
        scheduler.add_job(
            send_reminder,
            "date",
            run_date=reminder_time,
            args=[context.bot, AUTHORIZED_USER_ID, title, dt],
            id=f"appt_{appt_id}",
            replace_existing=True,
        )
        reminder_note = f"\n⏰ Reminder set for {reminder_time.strftime('%d/%m/%Y at %H:%M')}"
    else:
        reminder_note = "\n⚠️ Less than 30 min away — no reminder will be sent."

    await update.message.reply_text(
        f"📅 Appointment #{appt_id} added:\n*{title}*\n{dt.strftime('%d/%m/%Y at %H:%M')}{reminder_note}",
        parse_mode="Markdown",
    )


@authorized
async def list_appointments(update: Update, context: ContextTypes.DEFAULT_TYPE):
    appts = db.get_upcoming_appointments()
    if not appts:
        await update.message.reply_text(
            "No upcoming appointments. Add one with /addappt DD/MM/YYYY HH:MM <title>"
        )
        return

    lines = ["📅 *Upcoming Appointments*\n"]
    for a in appts:
        dt = datetime.fromisoformat(a["datetime"])
        lines.append(f"*#{a['id']}* {a['title']}")
        lines.append(f"   {dt.strftime('%d/%m/%Y at %H:%M')}\n")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


@authorized
async def delete_appointment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /delappt <id>")
        return
    try:
        appt_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Please provide a valid appointment ID.")
        return

    if db.delete_appointment(appt_id):
        job_id = f"appt_{appt_id}"
        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)
        await update.message.reply_text(f"🗑️ Appointment #{appt_id} deleted.")
    else:
        await update.message.reply_text(f"Appointment #{appt_id} not found.")


@authorized
async def set_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        current = db.get_setting("summary_time", DAILY_SUMMARY_TIME)
        await update.message.reply_text(
            f"Daily summary is currently sent at *{current}*.\n"
            "Use /setsummary HH:MM to change it.",
            parse_mode="Markdown",
        )
        return
    time_str = context.args[0]
    try:
        hour, minute = [int(x) for x in time_str.split(":")]
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError
    except (ValueError, AttributeError):
        await update.message.reply_text("Invalid time. Use HH:MM format, e.g. 08:30")
        return

    db.set_setting("summary_time", f"{hour:02d}:{minute:02d}")
    _schedule_daily_summary(context.bot, hour, minute)
    await update.message.reply_text(
        f"✅ Daily summary will now be sent at *{hour:02d}:{minute:02d}* every day.",
        parse_mode="Markdown",
    )


@authorized
async def trigger_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_daily_summary(context.bot)


# --- Daily summary ---

async def send_daily_summary(bot: Bot):
    now = datetime.now()
    week_end = now + timedelta(days=7)

    goals = db.get_goals()
    short_goals = [g for g in goals if g["type"] == "short" and not g["done"]]
    long_goals = [g for g in goals if g["type"] == "long" and not g["done"]]
    vision_5y = [g for g in goals if g["type"] == "5y" and not g["done"]]
    vision_10y = [g for g in goals if g["type"] == "10y" and not g["done"]]
    vision_15y = [g for g in goals if g["type"] == "15y" and not g["done"]]
    appts = db.get_appointments_in_range(now, week_end)

    lines = [f"☀️ *Good morning, Anton!* — {now.strftime('%A, %d %B %Y')}\n"]

    # Daily goals
    if short_goals or long_goals:
        lines.append("🎯 *Active Goals*")
        if short_goals:
            lines.append("_Short-term:_")
            for g in short_goals:
                lines.append(f"  • {g['text']}")
        if long_goals:
            lines.append("_Long-term:_")
            for g in long_goals:
                lines.append(f"  • {g['text']}")
    else:
        lines.append("🎯 No active goals — add some with /addgoal!")

    lines.append("")

    # Vision reminder
    if vision_5y or vision_10y or vision_15y:
        lines.append("🔭 *Your Vision*")
        for label, bucket in [("5y→2030", vision_5y), ("10y→2035", vision_10y), ("15y→2040", vision_15y)]:
            if bucket:
                lines.append(f"_({label})_")
                for g in bucket:
                    lines.append(f"  • {g['text']}")
        lines.append("")

    # Appointments
    if appts:
        lines.append("📅 *Upcoming (next 7 days)*")
        for a in appts:
            dt = datetime.fromisoformat(a["datetime"])
            lines.append(f"  • {dt.strftime('%d/%m %H:%M')} — {a['title']}")
    else:
        lines.append("📅 No upcoming appointments this week.")

    await bot.send_message(
        chat_id=AUTHORIZED_USER_ID,
        text="\n".join(lines),
        parse_mode="Markdown",
    )


def _schedule_daily_summary(bot: Bot, hour: int, minute: int):
    job_id = "daily_summary"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
    scheduler.add_job(
        send_daily_summary,
        "cron",
        hour=hour,
        minute=minute,
        args=[bot],
        id=job_id,
        replace_existing=True,
    )
    logger.info(f"Daily summary scheduled at {hour:02d}:{minute:02d}.")


# --- Reminder job ---

async def send_reminder(bot: Bot, user_id: int, title: str, dt: datetime):
    await bot.send_message(
        chat_id=user_id,
        text=f"⏰ *Reminder — in 30 minutes:*\n\n*{title}*\n🕐 {dt.strftime('%H:%M')}",
        parse_mode="Markdown",
    )


# --- Startup: reschedule pending appointments ---

async def post_init(application: Application):
    scheduler.start()
    appts = db.get_upcoming_appointments()
    rescheduled = 0
    for a in appts:
        dt = datetime.fromisoformat(a["datetime"])
        reminder_time = dt - timedelta(minutes=30)
        if reminder_time > datetime.now():
            scheduler.add_job(
                send_reminder,
                "date",
                run_date=reminder_time,
                args=[application.bot, AUTHORIZED_USER_ID, a["title"], dt],
                id=f"appt_{a['id']}",
                replace_existing=True,
            )
            rescheduled += 1
    logger.info(f"Rescheduled {rescheduled} upcoming reminder(s).")

    summary_time = db.get_setting("summary_time", DAILY_SUMMARY_TIME)
    hour, minute = [int(x) for x in summary_time.split(":")]
    _schedule_daily_summary(application.bot, hour, minute)


# --- Main ---

def main():
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("addgoal", add_goal))
    app.add_handler(CommandHandler("goals", list_goals))
    app.add_handler(CommandHandler("vision", list_vision))
    app.add_handler(CommandHandler("done", mark_done))
    app.add_handler(CommandHandler("delgoal", delete_goal))
    app.add_handler(CommandHandler("addappt", add_appointment))
    app.add_handler(CommandHandler("appts", list_appointments))
    app.add_handler(CommandHandler("delappt", delete_appointment))
    app.add_handler(CommandHandler("summary", trigger_summary))
    app.add_handler(CommandHandler("setsummary", set_summary))

    logger.info("Bot starting...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
