"""
Telegram bot handlers for sales agents.

Commands:
  /start        — register as agent
  /lead         — get next unclaimed lead
  /claim <id>   — claim a specific lead
  /my_leads     — list your active leads
  /switch <id>  — show a different lead
  /call <id>    — log a call attempt
  /sent <id>    — log message sent
  /demo <id>    — mark demo booked
  /close <id> won|lost [note] — close a lead
  /done <id>    — move to next stage
  /hook <id>    — get AI opening message
  /reply <id> <message> — get AI reply suggestion
"""
import logging
from telegram import Update
from telegram.ext import ContextTypes

from database.db import (
    upsert_agent, get_unclaimed_leads, claim_lead, get_lead,
    get_leads, update_lead_stage, log_conversation,
    bump_stat, get_conversation_history,
)
from engines.conversation_engine import generate_opening_message, suggest_reply, handle_objection
from engines.followup_engine import get_agent_followups, build_followup_alert
from engines.intelligence import get_micro_training, score_lead_priority

logger = logging.getLogger(__name__)

STAGES = ["new", "contacted", "engaged", "interested", "closing", "won", "lost"]


def _next_stage(current: str) -> str:
    try:
        idx = STAGES.index(current)
        if idx < STAGES.index("closing"):
            return STAGES[idx + 1]
    except ValueError:
        pass
    return current


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    upsert_agent(str(user.id), user.full_name)
    await update.message.reply_text(
        f"Welcome to NEXORA CRM, {user.first_name}!\n\n"
        "Commands:\n"
        "/lead — get next lead\n"
        "/my_leads — your active leads\n"
        "/claim <id> — claim a lead\n"
        "/done <id> — advance stage\n"
        "/demo <id> — mark demo booked\n"
        "/close <id> won|lost — close a deal\n"
        "/hook <id> — get opening message\n"
        "/reply <id> <msg> — get reply suggestion\n"
        "/followups — your follow-up alerts",
        parse_mode="HTML",
    )


async def cmd_lead(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    upsert_agent(str(user.id), user.full_name)

    leads = get_unclaimed_leads(limit=1)
    if not leads:
        await update.message.reply_text("No unclaimed leads right now. Check back after the next daily brief.")
        return

    lead = leads[0]
    await update.message.reply_text(
        _format_lead_card(lead) + "\n\nType /claim " + str(lead["id"]) + " to take this lead.",
        parse_mode="HTML",
    )


async def cmd_claim(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    upsert_agent(str(user.id), user.full_name)

    if not ctx.args:
        await update.message.reply_text("Usage: /claim <lead_id>")
        return

    try:
        lead_id = int(ctx.args[0])
    except ValueError:
        await update.message.reply_text("Invalid lead ID.")
        return

    success = claim_lead(lead_id, str(user.id))
    if not success:
        await update.message.reply_text(
            "Could not claim this lead — it may already be taken or does not exist."
        )
        return

    lead = get_lead(lead_id)
    bump_stat(str(user.id), "contacted")
    tip = get_micro_training("contacted")

    await update.message.reply_text(
        f"Lead claimed!\n\n{_format_lead_card(lead)}\n\n"
        f"<b>Tip:</b> {tip}\n\n"
        f"Get opening message: /hook {lead_id}",
        parse_mode="HTML",
    )


async def cmd_my_leads(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    leads = get_leads(agent_id=str(user.id), limit=15)
    active = [l for l in leads if l["stage"] not in ("won", "lost")]

    if not active:
        await update.message.reply_text("You have no active leads. Use /lead to get one.")
        return

    lines = [f"<b>YOUR LEADS ({len(active)})</b>", ""]
    for lead in active:
        priority = score_lead_priority(lead)
        lines.append(
            f"<b>#{lead['id']}</b> {lead['name']} — {lead.get('niche','')}\n"
            f"  Stage: {lead['stage']}  |  Priority: {priority:.1f}/10\n"
            f"  Phone: {lead.get('phone') or 'N/A'}"
        )
        lines.append("")

    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


async def cmd_switch(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Usage: /switch <lead_id>")
        return
    try:
        lead_id = int(ctx.args[0])
    except ValueError:
        await update.message.reply_text("Invalid lead ID.")
        return

    lead = get_lead(lead_id)
    if not lead:
        await update.message.reply_text("Lead not found.")
        return

    history = get_conversation_history(lead_id, limit=5)
    history_text = ""
    if history:
        history_text = "\n\n<b>Recent Conversation:</b>\n"
        for msg in history:
            who = "You" if msg["direction"] == "out" else "Prospect"
            history_text += f"  {who}: {msg['message'][:80]}\n"

    tip = get_micro_training(lead.get("stage", "new"))
    await update.message.reply_text(
        _format_lead_card(lead) + history_text + f"\n<b>Tip:</b> {tip}",
        parse_mode="HTML",
    )


async def cmd_call(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not ctx.args:
        await update.message.reply_text("Usage: /call <lead_id>")
        return
    try:
        lead_id = int(ctx.args[0])
    except ValueError:
        await update.message.reply_text("Invalid lead ID.")
        return

    lead = get_lead(lead_id)
    if not lead:
        await update.message.reply_text("Lead not found.")
        return

    log_conversation(lead_id, str(user.id), "out", "[Call attempt logged]")
    update_lead_stage(lead_id, lead["stage"] or "contacted")
    bump_stat(str(user.id), "contacted")

    await update.message.reply_text(
        f"Call attempt logged for <b>{lead['name']}</b>.\n"
        "If they replied, use /reply to get a suggested response.\n"
        "If they answered: /done to advance stage.",
        parse_mode="HTML",
    )


async def cmd_sent(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = ctx.args
    if len(args) < 2:
        await update.message.reply_text("Usage: /sent <lead_id> <message text>")
        return

    try:
        lead_id = int(args[0])
    except ValueError:
        await update.message.reply_text("Invalid lead ID.")
        return

    message = " ".join(args[1:])
    lead = get_lead(lead_id)
    if not lead:
        await update.message.reply_text("Lead not found.")
        return

    log_conversation(lead_id, str(user.id), "out", message)
    update_lead_stage(lead_id, lead["stage"] or "contacted")
    bump_stat(str(user.id), "contacted")

    await update.message.reply_text(
        f"Message logged for <b>{lead['name']}</b>. Good luck!",
        parse_mode="HTML",
    )


async def cmd_demo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not ctx.args:
        await update.message.reply_text("Usage: /demo <lead_id>")
        return
    try:
        lead_id = int(ctx.args[0])
    except ValueError:
        await update.message.reply_text("Invalid lead ID.")
        return

    lead = get_lead(lead_id)
    if not lead:
        await update.message.reply_text("Lead not found.")
        return

    update_lead_stage(lead_id, "interested", notes="Demo booked")
    bump_stat(str(user.id), "demos")
    bump_stat(str(user.id), "responses")
    tip = get_micro_training("interested")

    await update.message.reply_text(
        f"Demo booked for <b>{lead['name']}</b>! Stage updated to: interested\n\n"
        f"<b>Tip:</b> {tip}",
        parse_mode="HTML",
    )


async def cmd_close(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if len(ctx.args) < 2:
        await update.message.reply_text("Usage: /close <lead_id> won|lost [optional note]")
        return

    try:
        lead_id = int(ctx.args[0])
    except ValueError:
        await update.message.reply_text("Invalid lead ID.")
        return

    outcome = ctx.args[1].lower()
    if outcome not in ("won", "lost"):
        await update.message.reply_text("Outcome must be 'won' or 'lost'.")
        return

    note = " ".join(ctx.args[2:]) if len(ctx.args) > 2 else ""
    lead = get_lead(lead_id)
    if not lead:
        await update.message.reply_text("Lead not found.")
        return

    update_lead_stage(lead_id, outcome, notes=note or None)
    bump_stat(str(user.id), outcome)

    msg = (
        f"Deal CLOSED — <b>{outcome.upper()}</b>\n"
        f"Business: {lead['name']}\n"
    )
    if note:
        msg += f"Note: {note}\n"
    if outcome == "won":
        msg += "\nOutstanding! Keep the momentum going."
    else:
        msg += "\nLogged as lost. Every 'no' gets you closer to the next 'yes'."

    await update.message.reply_text(msg, parse_mode="HTML")


async def cmd_done(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not ctx.args:
        await update.message.reply_text("Usage: /done <lead_id>")
        return
    try:
        lead_id = int(ctx.args[0])
    except ValueError:
        await update.message.reply_text("Invalid lead ID.")
        return

    lead = get_lead(lead_id)
    if not lead:
        await update.message.reply_text("Lead not found.")
        return

    current = lead.get("stage", "new")
    new_stage = _next_stage(current)
    if new_stage == current:
        await update.message.reply_text(
            f"Lead is at '{current}' — use /close {lead_id} won|lost to finish."
        )
        return

    update_lead_stage(lead_id, new_stage)
    bump_stat(str(user.id), "responses")
    tip = get_micro_training(new_stage)

    await update.message.reply_text(
        f"<b>{lead['name']}</b> moved: {current} → <b>{new_stage}</b>\n\n"
        f"<b>Next step:</b> {tip}",
        parse_mode="HTML",
    )


async def cmd_hook(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Usage: /hook <lead_id>")
        return
    try:
        lead_id = int(ctx.args[0])
    except ValueError:
        await update.message.reply_text("Invalid lead ID.")
        return

    lead = get_lead(lead_id)
    if not lead:
        await update.message.reply_text("Lead not found.")
        return

    await update.message.reply_text("Generating opening message...", parse_mode="HTML")
    message = generate_opening_message(lead)
    await update.message.reply_text(
        f"<b>Opening Message for {lead['name']}:</b>\n\n{message}",
        parse_mode="HTML",
    )


async def cmd_reply(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if len(ctx.args) < 2:
        await update.message.reply_text("Usage: /reply <lead_id> <prospect's message>")
        return
    try:
        lead_id = int(ctx.args[0])
    except ValueError:
        await update.message.reply_text("Invalid lead ID.")
        return

    lead = get_lead(lead_id)
    if not lead:
        await update.message.reply_text("Lead not found.")
        return

    prospect_msg = " ".join(ctx.args[1:])
    history = get_conversation_history(lead_id, limit=6)
    log_conversation(lead_id, str(update.effective_user.id), "in", prospect_msg)
    bump_stat(str(update.effective_user.id), "responses")

    await update.message.reply_text("Thinking...", parse_mode="HTML")
    suggestion = suggest_reply(lead, prospect_msg, history)

    await update.message.reply_text(
        f"<b>Suggested reply:</b>\n\n{suggestion}",
        parse_mode="HTML",
    )


async def cmd_followups(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    upsert_agent(str(user.id), user.full_name)
    leads = get_agent_followups(str(user.id))
    if not leads:
        await update.message.reply_text("No follow-ups due right now. Great work!")
        return
    await update.message.reply_text(build_followup_alert(leads), parse_mode="HTML")


def _format_lead_card(lead: dict) -> str:
    phone = lead.get("phone") or "No phone"
    return (
        f"<b>#{lead['id']}. {lead['name']}</b>\n"
        f"Type: {lead.get('niche','')}\n"
        f"Location: {lead.get('address') or lead.get('city','')}\n"
        f"Phone: {phone}\n"
        f"Score: {lead.get('score','')}/10  |  Intent: {lead.get('intent','')}\n"
        f"Stage: {lead.get('stage','new')}\n"
        f"Gap: {lead.get('opportunity','')}\n"
        f"Hook: <i>{(lead.get('hook') or '')[:120]}</i>"
    )
