import os
import logging
import asyncio
from datetime import datetime, timedelta
from collections import defaultdict, deque
from dotenv import load_dotenv
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    Defaults,
    filters,
)
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from get_remaining_meals import get_remaining_meals, OTPRetrievalError

# Load environment variables from .env file
load_dotenv()

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Suppress httpx INFO logs (only show warnings and errors)
logging.getLogger("httpx").setLevel(logging.WARNING)

# In-memory spam detection and ban storage
# Configuration
SPAM_THRESHOLD = 4  # Number of messages allowed
SPAM_TIME_WINDOW = 300  # Time window in seconds
BAN_DURATION = 1800  # Ban duration in seconds (30 minutes)

# Storage
user_message_times = defaultdict(deque)  # user_id -> deque of timestamps
banned_users = {}  # user_id -> ban_expiry_time

# Track active tasks per user (to prevent duplicate requests from same user)
active_user_tasks = {}  # user_id -> task


def is_user_banned(user_id: int) -> tuple[bool, int]:
    """Check if a user is banned and return ban status with remaining time."""
    if user_id in banned_users:
        ban_expiry = banned_users[user_id]
        if datetime.now() < ban_expiry:
            remaining_seconds = int((ban_expiry - datetime.now()).total_seconds())
            return True, remaining_seconds
        else:
            # Ban expired, remove from banned list
            del banned_users[user_id]
            # Clean up message history
            if user_id in user_message_times:
                user_message_times[user_id].clear()
    return False, 0


def check_spam(user_id: int) -> bool:
    """Check if user is spamming and ban if threshold exceeded."""
    now = datetime.now()

    # Get user's message timestamps
    message_times = user_message_times[user_id]

    # Remove old timestamps outside the time window
    cutoff_time = now - timedelta(seconds=SPAM_TIME_WINDOW)
    while message_times and message_times[0] < cutoff_time:
        message_times.popleft()

    # Add current message timestamp
    message_times.append(now)

    # Check if spam threshold exceeded
    if len(message_times) > SPAM_THRESHOLD:
        # Ban the user
        banned_users[user_id] = now + timedelta(seconds=BAN_DURATION)
        logger.warning(
            f"User {user_id} banned for spamming. Messages: {len(message_times)} in {SPAM_TIME_WINDOW}s"
        )
        return True

    return False


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send instructions when the user starts the bot."""
    user_id = update.effective_user.id

    # Check if user is banned
    is_banned, remaining_time = is_user_banned(user_id)
    if is_banned:
        minutes = remaining_time // 60
        seconds = remaining_time % 60
        await update.message.reply_text(
            f"🚫 <b>Temporarily Banned</b>\n\n"
            f"You've been temporarily banned for spamming.\n"
            f"⏱️ Time remaining: {minutes}m {seconds}s\n\n"
            f"Please wait before using the bot again."
        )
        return

    example_text = "12345678\nSRSPass123\nname.surname@ug.bilkent.edu.tr\nemailPass456"

    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton(text="Example Message", callback_data="copy_example")]]
    )

    await update.message.reply_text(
        "<b>Bilkent Meals Bot</b> 🍽️\n"
        "\nCheck your remaining SRS meals quickly and safely 🤤\n\n"
        "🛡️ <b>Your privacy matters:</b> <i>No data is stored. Your message is deleted right after processing.</i>\n\n"
        "⚠️ <b>Disclaimer:</b> <i>While this bot doesn't save your credentials, you are responsible for your own account security. I'm not liable for any data loss or unauthorized access.</i>\n\n"
        "📥 <b>Send one message with 4 lines:</b>\n"
        f"<pre>{example_text}</pre>\n"
        '\n🔍 <b>Transparency:</b> Source code available on <a href="https://github.com/shahumeen/Bilkent_SRS_meals_bot">GitHub</a>',
        reply_markup=keyboard,
        disable_web_page_preview=True,
    )

    # Store example in context for callback handler
    context.chat_data["example_text"] = example_text


async def copy_example_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Send the example credentials as plain text to ease copying."""
    query = update.callback_query
    await query.answer("Example ready to copy")
    example_text = context.chat_data.get(
        "example_text",
        "12345678\nSRSPass123\nname.surname@ug.bilkent.edu.tr\nemailPass456",
    )
    # Send as plain text (no HTML) to make copying straightforward
    await query.message.reply_text(example_text, parse_mode=None)


async def process_user_request(
    user_id: int,
    bilkent_id: str,
    stars_password: str,
    email: str,
    email_password: str,
    status_message,
) -> None:
    """Process a single user's meal request in the background."""
    
    # Check if user is banned
    is_banned, remaining_time = is_user_banned(user_id)
    if is_banned:
        minutes = remaining_time // 60
        seconds = remaining_time % 60
        await status_message.edit_text(
            f"🚫 <b>Temporarily Banned</b>\n\n"
            f"You've been temporarily banned for spamming.\n"
            f"⏱️ Time remaining: {minutes}m {seconds}s\n\n"
            f"Please wait before using the bot again."
        )
        # Remove task from active tasks when banned
        if user_id in active_user_tasks:
            del active_user_tasks[user_id]
        return

    # Check for spam
    if check_spam(user_id):
        minutes = BAN_DURATION // 60
        await status_message.edit_text(
            f"🚫 <b>Spam Detected!</b>\n\n"
            f"You've sent too many messages too quickly.\n"
            f"⏱️ Banned for: {minutes} minutes\n\n"
            f"Please wait before using the bot again."
        )
        # Remove task from active tasks when banned for spam
        if user_id in active_user_tasks:
            del active_user_tasks[user_id]
        return

    # Create callback function for status updates
    async def update_status(message: str):
        try:
            await status_message.edit_text(message)
        except Exception as e:
            logger.warning(f"Could not update status message: {e}")

    try:
        # Directly await get_remaining_meals since we're already in async context
        remaining_meals = await get_remaining_meals(
            bilkent_id=bilkent_id,
            stars_password=stars_password,
            email=email,
            email_password=email_password,
            status_callback=update_status,
        )

        if remaining_meals is not None:
            await status_message.edit_text(
                f"🍽️ <b>Meals Remaining:</b> {remaining_meals}\n😊 Afiyet olsun!"
            )
        else:
            await status_message.edit_text(
                "❌ Couldn't retrieve meals this time.\n\n"
                "🔎 Possible reasons:\n"
                "• ❗ Incorrect credentials\n"
                "• 🌐 Network hiccups\n"
                "• 🛠️ SRS service might be down\n\n"
                "🛡️ Your message was deleted for privacy—feel free to try again."
            )
    except OTPRetrievalError:
        # Show the exact user-specified message without exposing internal errors
        try:
            await status_message.edit_text("Failed to retrieve OTP from email")
        except:
            pass
    except Exception as e:
        logger.error(f"Error fetching meals for user {user_id}: {e}")
        try:
            await status_message.edit_text(f"❌ <b>Error</b>\n<code>{str(e)}</code>")
        except:
            pass
    finally:
        # Remove task from active tasks when done
        if user_id in active_user_tasks:
            del active_user_tasks[user_id]
            logger.info(f"Completed request for user {user_id}")


async def handle_credentials(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Parse credentials and fetch remaining meals concurrently."""
    user_id = update.effective_user.id

    # Check if user already has an active request
    if user_id in active_user_tasks:
        try:
            await update.message.delete()
        except Exception as e:
            logger.warning(f"Could not delete credentials message: {e}")

        await update.message.reply_text(
            "⏳ <b>Request in Progress</b>\n\n"
            "You already have a request being processed.\n"
            "Please wait for it to complete before sending another."
        )
        return

    # Check if user is banned
    is_banned, remaining_time = is_user_banned(user_id)
    if is_banned:
        minutes = remaining_time // 60
        seconds = remaining_time % 60
        # Delete the message containing credentials for security
        try:
            await update.message.delete()
        except Exception as e:
            logger.warning(f"Could not delete credentials message: {e}")

        await update.message.reply_text(
            f"🚫 <b>Temporarily Banned</b>\n\n"
            f"You've been temporarily banned for spamming.\n"
            f"⏱️ Time remaining: {minutes}m {seconds}s\n\n"
            f"Please wait before using the bot again."
        )
        return

    message_text = update.message.text.strip()

    # Delete the message containing credentials for security
    try:
        await update.message.delete()
    except Exception as e:
        logger.warning(f"Could not delete credentials message: {e}")

    # Parse the message (expecting 4 lines)
    lines = [line.strip() for line in message_text.split("\n") if line.strip()]

    if len(lines) != 4:
        await update.message.reply_text(
            "❌ <b>Invalid Format</b>\n\n"
            "Please send <b>4 lines</b> in <b>one</b> message:\n"
            "• SRS ID\n"
            "• SRS Password\n"
            "• Email (for OTP/2FA)\n"
            "• Email Password\n\n"
            "Send /start to see the example."
        )
        return

    bilkent_id, stars_password, email, email_password = lines

    # Notify user that process is starting
    status_message = await update.message.reply_text(
        "✅ Credentials received\n⏳ Checking your remaining meals securely..."
    )

    # Create and track the background task for this user
    task = asyncio.create_task(
        process_user_request(
            user_id=user_id,
            bilkent_id=bilkent_id,
            stars_password=stars_password,
            email=email,
            email_password=email_password,
            status_message=status_message,
        )
    )

    active_user_tasks[user_id] = task
    logger.info(
        f"Started concurrent request for user {user_id}. Active tasks: {len(active_user_tasks)}"
    )


def main() -> None:
    """Run the bot."""
    # Get bot token from environment variable
    token = os.getenv("TELEGRAM_BOT_TOKEN")

    if not token:
        raise ValueError(
            "TELEGRAM_BOT_TOKEN environment variable not set!\n"
            "Please set it using: export TELEGRAM_BOT_TOKEN='your_token_here'"
        )

    # Create application
    # Create application with HTML as default parse mode for nicer formatting
    application = (
        Application.builder()
        .token(token)
        .defaults(Defaults(parse_mode=ParseMode.HTML))
        .build()
    )

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(
        CallbackQueryHandler(copy_example_callback, pattern="^copy_example$")
    )
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_credentials)
    )

    # Start the bot
    logger.info("Bot started with concurrent request handling! Press Ctrl+C to stop.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)
    logger.info("Bot stopped.")


if __name__ == "__main__":
    main()
