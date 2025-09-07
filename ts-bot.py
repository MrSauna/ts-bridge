import logging
import os
import requests

from telegram import ForceReply, Update
from telegram.ext import Application, ApplicationHandlerStop, CommandHandler, ContextTypes, MessageHandler, TypeHandler, filters


# Enable logging
logging.basicConfig(

    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO

)

# set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


def get_user_list(url: str, apikey: str) -> list[str]:

    """Get the user list from the TeamSpeak server."""

    r = requests.get(url+"/1/clientlist?-voice%20-away", headers={"X-API-Key": apikey})
    body = r.json()["body"]
    users = [user for user in body if user["client_type"] == '0']
    away_nicknames = {user["client_nickname"] for user in users if user["client_away"] == '1' or user["client_output_muted"] == '1'}


    all_nicknames = {user["client_nickname"] for user in users}
    active_nicknames = all_nicknames - away_nicknames

    return sorted(active_nicknames, key=str.lower), sorted(away_nicknames, key=str.lower)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:

    """Send a message when the command /help is issued."""

    await update.message.reply_text("Help!")


async def whoami_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:

    """Send a message when the command /whoami is issued."""

    user = update.effective_user
    group = update.effective_chat

    await update.message.reply_html(

        rf"Your user ID is {user.id} and this group ID is {group.id}",

    )


def format_user_list(active: list[str], away: list[str]) -> str:

    """Format the user list from active and away users."""

    temp = f"{len(active)}\\+_{len(away)}_: "
    temp += ", ".join(active)

    for user in away:
        temp += f", _{user}_"
    
    return temp 


async def ts_get_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:

    """Get the user list from the TeamSpeak server."""

    ts_url = context.bot_data["ts_url"]
    ts_apikey = context.bot_data["ts_apikey"]
    active, away = get_user_list(ts_url, ts_apikey)

    await update.message.reply_text(format_user_list(active, away), parse_mode="MarkdownV2")


async def ts_get_users_live(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:

    """Get the user list from the TeamSpeak server. Live version."""

    # check fo existing live message
    if "live_msg" in context.bot_data:
        live_msg = context.bot_data["live_msg"]
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            reply_to_message_id=live_msg.message_id,
            text="Live message already exists. Please wait for it to update."
        )
        return

    # no existing live message, create one
    # Send the message and store the Message object for later editing
    active, away = get_user_list(context.bot_data["ts_url"], context.bot_data["ts_apikey"])
    sent_message = await context.bot.send_message(chat_id=update.effective_chat.id, text=format_user_list(active, away), parse_mode="MarkdownV2")
    context.bot_data["live_msg"] = sent_message  # Store the Message object


async def check_perms(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:

    """Check permissions."""

    group = update.effective_chat
    allowed_groups = context.bot_data["allowed_groups"]

    if group.id not in allowed_groups:

        logger.error(f"Unauthorized access to group {group.id} ({group.title})")
        raise ApplicationHandlerStop


async def update_live_message(context: ContextTypes.DEFAULT_TYPE):

    """Update the live message with the current user list."""

    live_msg = context.bot_data.get("live_msg")
    if not live_msg:
        logger.warning("No live message to update.")
        return

    active, away = get_user_list(context.bot_data["ts_url"], context.bot_data["ts_apikey"])
    text = format_user_list(active, away)
    if text != live_msg.text_markdown_v2:
        context.bot_data["live_msg"] = await live_msg.edit_text(format_user_list(active, away), parse_mode="MarkdownV2")


def main() -> None:

    """Start the bot."""

    # Create the Application and pass it your bot's token.

    token = os.getenv("BOT_TOKEN")
    application = Application.builder().token(token).build()
    job_queue = application.job_queue
    job_queue.run_repeating(update_live_message, interval=60, first=10)
    application.bot_data["allowed_groups"] = list(map(int, os.getenv("ALLOWED_GROUPS", "").split(",")))
    application.bot_data["ts_apikey"] = os.getenv("TS_APIKEY")
    application.bot_data["ts_url"] = os.getenv("TS_URL")

    # enforce permission for all
    check_perms_handler = TypeHandler(Update, check_perms)
    application.add_handler(check_perms_handler, -1)

    # normal handlers
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("whoami", whoami_command))
    application.add_handler(CommandHandler("ts", ts_get_users))
    application.add_handler(CommandHandler("tslive", ts_get_users_live))

    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":

    main()
