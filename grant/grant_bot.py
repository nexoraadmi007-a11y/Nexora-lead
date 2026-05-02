"""
NEXORA Grant Bot — Telegram interface for grant application generation.

Conversation flow:
  /grant → ask grant name → ask link → ask questions → generate → send doc
"""
import logging
import asyncio
from io import BytesIO
from telegram import Update, Document
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)
from grant.grant_engine import generate_grant_application
from grant.doc_builder import build_word_document

logger = logging.getLogger(__name__)

# Conversation states
ASK_NAME, ASK_LINK, ASK_QUESTIONS, GENERATING = range(4)

# ── Helpers ──────────────────────────────────────────────────────────────────

def _escape(text: str) -> str:
    """Minimal HTML-safe escape for Telegram HTML mode."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


async def _send_chunks(context: ContextTypes.DEFAULT_TYPE, chat_id: int, text: str):
    """Send long text in 4000-char chunks."""
    while len(text) > 4000:
        cut = text.rfind("\n", 0, 4000) or 4000
        await context.bot.send_message(chat_id=chat_id, text=text[:cut])
        text = text[cut:].lstrip("\n")
    if text.strip():
        await context.bot.send_message(chat_id=chat_id, text=text.strip())


# ── Conversation handlers ─────────────────────────────────────────────────────

async def cmd_grant(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text(
        "📋 <b>NEXORA GRANT ENGINE</b>\n\n"
        "Let's build your grant application.\n\n"
        "Step 1 of 3 — What is the <b>grant name</b>?",
        parse_mode="HTML",
    )
    return ASK_NAME


async def received_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    name = update.message.text.strip()
    if not name:
        await update.message.reply_text("Please enter a valid grant name.")
        return ASK_NAME

    context.user_data["grant_name"] = name
    await update.message.reply_text(
        f"✅ Grant: <b>{_escape(name)}</b>\n\n"
        "Step 2 of 3 — Paste the <b>grant link</b> (or type <code>skip</code> to continue without it).",
        parse_mode="HTML",
    )
    return ASK_LINK


async def received_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    context.user_data["grant_link"] = "" if text.lower() == "skip" else text

    await update.message.reply_text(
        "Step 3 of 3 — Paste all your <b>grant questions</b>.\n\n"
        "One question per line, or numbered. Send when ready.",
        parse_mode="HTML",
    )
    return ASK_QUESTIONS


async def received_questions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    raw = update.message.text.strip()
    if not raw:
        await update.message.reply_text("No questions found. Please paste your questions.")
        return ASK_QUESTIONS

    # Parse: strip numbering like "1. ", "1) ", bullet "- "
    lines = [
        line.lstrip("0123456789.-) ").strip()
        for line in raw.split("\n")
        if line.strip()
    ]
    questions = [q for q in lines if len(q) > 4]

    if not questions:
        await update.message.reply_text(
            "Couldn't parse any questions. Please try again."
        )
        return ASK_QUESTIONS

    context.user_data["questions"] = questions

    await update.message.reply_text(
        f"✅ Got <b>{len(questions)} question(s)</b>.\n\n"
        "⏳ Generating your grant application... this takes 30–60 seconds.",
        parse_mode="HTML",
    )

    grant_name = context.user_data["grant_name"]
    grant_link = context.user_data.get("grant_link", "")

    try:
        draft = await asyncio.to_thread(
            generate_grant_application, grant_name, questions, grant_link
        )
    except Exception as e:
        logger.error("Grant generation failed: %s", e)
        await update.message.reply_text(
            "❌ Generation failed. Please try again with /grant."
        )
        return ConversationHandler.END

    # Build Word doc
    try:
        docx_buffer: BytesIO = await asyncio.to_thread(
            build_word_document, grant_name, draft
        )
        filename = f"NEXORA_Grant_{grant_name.replace(' ', '_')}.docx"
        await context.bot.send_document(
            chat_id=update.effective_chat.id,
            document=docx_buffer,
            filename=filename,
            caption=f"📄 <b>NEXORA Grant Application</b>\n{_escape(grant_name)}",
            parse_mode="HTML",
        )
    except Exception as e:
        logger.warning("Word doc build failed (%s) — sending text only.", e)

    # Send text preview
    preview_header = (
        "📩 <b>Your grant application draft is ready.</b>\n\n"
        f"Grant: <b>{_escape(grant_name)}</b>\n"
        f"Questions answered: <b>{len(questions)}</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    )
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=preview_header,
        parse_mode="HTML",
    )
    await _send_chunks(context, update.effective_chat.id, draft)

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=(
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "✅ <b>Done.</b> Download the .docx above for Word-ready formatting.\n\n"
            "Need to generate another? Send /grant"
        ),
        parse_mode="HTML",
    )

    return ConversationHandler.END


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text("Cancelled. Send /grant to start again.")
    return ConversationHandler.END


async def fallback_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Send /grant to generate a new grant application."
    )


# ── Bot builder ───────────────────────────────────────────────────────────────

def build_grant_application(token: str) -> Application:
    app = Application.builder().token(token).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("grant", cmd_grant)],
        states={
            ASK_NAME:      [MessageHandler(filters.TEXT & ~filters.COMMAND, received_name)],
            ASK_LINK:      [MessageHandler(filters.TEXT & ~filters.COMMAND, received_link)],
            ASK_QUESTIONS: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_questions)],
        },
        fallbacks=[CommandHandler("cancel", cmd_cancel)],
        allow_reentry=True,
    )

    app.add_handler(conv)
    app.add_handler(CommandHandler("start", cmd_grant))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, fallback_message))

    return app
