import logging
import os
from datetime import datetime, timedelta
from functools import wraps

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes

from database import Database

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
AUTHORIZED_USER_ID = int(os.environ["AUTHORIZED_USER_ID"])

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
    await update.message.reply_text(
        "📋 *Commands*\n\n"
        "*Life Goals \\(5/10/15y\\):*\n"
        "/lifegoals — View 5/10/15y life goals\n"
        "/addlife 5|10|15 \\<text\\> — Add a life goal\n"
        "/achievelife \\<id\\> — Mark life goal as achieved\n"
        "/dellife \\<id\\> — Delete a life goal\n\n"
        "*Goals:*\n"
        "/addgoal short|long \\<text\\> — Add a goal\n"
        "/goals — List all goals\n"
        "/setdue \\<id\\> DD/MM/YYYY — Set a deadline on a goal\n"
        "/done \\<id\\> — Mark goal as done\n"
        "/delgoal \\<id\\> — Delete a goal\n\n"
        "*Appointments:*\n"
        "/addappt DD/MM/YYYY HH:MM \\<title\\> — Add appointment\n"
        "/appts — List upcoming appointments\n"
        "/delappt \\<id\\> — Delete an appointment\n\n"
        "_You'll get a reminder 30 min before each appointment\\._",
        parse_mode="MarkdownV2",
    )


HORIZON_LABELS = {
    5: "5 Years — 2030 (you'll be 45)",
    10: "10 Years — 2035 (you'll be 50)",
    15: "15 Years — 2040 (you'll be 55)",
}


@authorized
async def list_life_goals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    goals = db.get_life_goals()
    if not goals:
        await update.message.reply_text("No life goals yet. Add one with /addlife 5|10|15 <text>")
        return

    lines = ["🌟 *Life Goals*\n"]
    for horizon in (5, 10, 15):
        horizon_goals = [g for g in goals if g["horizon"] == horizon]
        if not horizon_goals:
            continue
        lines.append(f"*{HORIZON_LABELS[horizon]}*")
        active = [g for g in horizon_goals if not g["achieved"]]
        done = [g for g in horizon_goals if g["achieved"]]
        for g in active:
            lines.append(f"  #{g['id']} {g['text']}")
        for g in done:
            lines.append(f"  ✓ #{g['id']} ~~{g['text']}~~")
        lines.append("")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


@authorized
async def add_life_goal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 2 or args[0] not in ("5", "10", "15"):
        await update.message.reply_text("Usage: /addlife 5|10|15 <text>")
        return
    horizon = int(args[0])
    text = " ".join(args[1:])
    goal_id = db.add_life_goal(horizon, text)
    await update.message.reply_text(
        f"🌟 Life goal #{goal_id} added ({horizon}y horizon):\n{text}"
    )


@authorized
async def achieve_life_goal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /achievelife <id>")
        return
    try:
        goal_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Please provide a valid goal ID.")
        return
    if db.mark_life_goal_achieved(goal_id):
        await update.message.reply_text(f"🏆 Life goal #{goal_id} marked as achieved!")
    else:
        await update.message.reply_text(f"Life goal #{goal_id} not found or already achieved.")


@authorized
async def delete_life_goal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /dellife <id>")
        return
    try:
        goal_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Please provide a valid goal ID.")
        return
    if db.delete_life_goal(goal_id):
        await update.message.reply_text(f"🗑️ Life goal #{goal_id} deleted.")
    else:
        await update.message.reply_text(f"Life goal #{goal_id} not found.")


@authorized
async def add_goal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 2 or args[0] not in ("short", "long"):
        await update.message.reply_text("Usage: /addgoal short|long <text>")
        return
    goal_type = args[0]
    text = " ".join(args[1:])
    goal_id = db.add_goal(goal_type, text)
    await update.message.reply_text(
        f"✅ Goal #{goal_id} added ({goal_type}-term):\n{text}"
    )


def _format_due(g: dict) -> str:
    if not g.get("due_date"):
        return ""
    due = datetime.strptime(g["due_date"], "%Y-%m-%d").date()
    today = datetime.now().date()
    delta = (due - today).days
    label = due.strftime("%-d %b")
    if delta < 0:
        return f" ⚠️ overdue ({label})"
    if delta == 0:
        return f" ⏰ due today"
    if delta <= 7:
        return f" ⏳ {delta}d left ({label})"
    return f" 📅 by {label}"


@authorized
async def list_goals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    goals = db.get_goals()
    if not goals:
        await update.message.reply_text("No goals yet. Add one with /addgoal short|long <text>")
        return

    short_goals = [g for g in goals if g["type"] == "short" and not g["done"]]
    long_goals = [g for g in goals if g["type"] == "long" and not g["done"]]
    done_goals = [g for g in goals if g["done"]]

    lines = ["🎯 *Your Goals*\n"]
    if short_goals:
        lines.append("*Short-term:*")
        for g in short_goals:
            lines.append(f"  #{g['id']} {g['text']}{_format_due(g)}")
        lines.append("")
    if long_goals:
        lines.append("*Long-term:*")
        for g in long_goals:
            lines.append(f"  #{g['id']} {g['text']}{_format_due(g)}")
        lines.append("")
    if done_goals:
        lines.append("*Completed:*")
        for g in done_goals[:5]:
            lines.append(f"  ✓ #{g['id']} {g['text']}")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


@authorized
async def set_due(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) != 2:
        await update.message.reply_text("Usage: /setdue <id> DD/MM/YYYY")
        return
    try:
        goal_id = int(args[0])
    except ValueError:
        await update.message.reply_text("Please provide a valid goal ID.")
        return
    try:
        due = datetime.strptime(args[1], "%d/%m/%Y").date()
    except ValueError:
        await update.message.reply_text("Invalid date. Use DD/MM/YYYY e.g. 30/06/2025")
        return
    if db.set_goal_due_date(goal_id, due.isoformat()):
        await update.message.reply_text(
            f"📅 Due date set for goal #{goal_id}: {due.strftime('%-d %b %Y')}"
        )
    else:
        await update.message.reply_text(f"Goal #{goal_id} not found.")


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


# --- Reminder job ---

async def send_reminder(bot: Bot, user_id: int, title: str, dt: datetime):
    await bot.send_message(
        chat_id=user_id,
        text=f"⏰ *Reminder — in 30 minutes:*\n\n*{title}*\n🕐 {dt.strftime('%H:%M')}",
        parse_mode="Markdown",
    )


# --- Startup: reschedule pending appointments ---

async def post_init(application: Application):
    db.seed_life_goals()
    db.seed_short_term_goals()
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
    app.add_handler(CommandHandler("lifegoals", list_life_goals))
    app.add_handler(CommandHandler("addlife", add_life_goal))
    app.add_handler(CommandHandler("achievelife", achieve_life_goal))
    app.add_handler(CommandHandler("dellife", delete_life_goal))
    app.add_handler(CommandHandler("addgoal", add_goal))
    app.add_handler(CommandHandler("goals", list_goals))
    app.add_handler(CommandHandler("setdue", set_due))
    app.add_handler(CommandHandler("done", mark_done))
    app.add_handler(CommandHandler("delgoal", delete_goal))
    app.add_handler(CommandHandler("addappt", add_appointment))
    app.add_handler(CommandHandler("appts", list_appointments))
    app.add_handler(CommandHandler("delappt", delete_appointment))

    logger.info("Bot starting...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
