"""
Telegram bot handlers for admin (owner) only.

Commands:
  /admin_report   — full team performance report
  /pipeline       — deal pipeline summary
  /agent <id>     — stats for a specific agent
  /agents         — list all agents
  /intelligence   — AI deal intelligence report
  /broadcast <msg>— send message to all agents
  /add_leads      — trigger manual lead cycle
"""
import logging
from telegram import Update
from telegram.ext import ContextTypes, Application

from database.db import (
    get_pipeline_summary, get_team_stats_today, get_agent_stats,
    get_agents, set_agent_status, get_leads,
)
from engines.intelligence import build_intelligence_report, get_stuck_deals
from engines.followup_engine import get_followups_due, build_followup_alert
from config import OWNER_CHAT_ID

logger = logging.getLogger(__name__)


def is_admin(user_id: int) -> bool:
    return str(user_id) == str(OWNER_CHAT_ID)


def admin_only(func):
    """Decorator: reject non-admin users."""
    async def wrapper(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not is_admin(update.effective_user.id):
            await update.message.reply_text("This command is for admin only.")
            return
        return await func(update, ctx)
    wrapper.__name__ = func.__name__
    return wrapper


@admin_only
async def cmd_admin_report(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    stats = get_team_stats_today()
    if not stats:
        await update.message.reply_text("No activity logged today.")
        return

    lines = ["<b>TEAM PERFORMANCE TODAY</b>", ""]
    total = {"contacted": 0, "responses": 0, "demos": 0, "won": 0, "lost": 0}

    for s in stats:
        name = s.get("name") or s.get("agent_id", "Unknown")
        conv = f"{(s['responses'] / max(s['contacted'], 1) * 100):.0f}%"
        lines.append(
            f"<b>{name}</b>\n"
            f"  Contacted: {s['contacted']}  Responses: {s['responses']}  "
            f"Demos: {s['demos']}  Won: {s['won']}  Lost: {s['lost']}\n"
            f"  Response rate: {conv}"
        )
        lines.append("")
        for k in total:
            total[k] += s.get(k, 0)

    total_conv = f"{(total['responses'] / max(total['contacted'], 1) * 100):.0f}%"
    lines += [
        "─" * 28,
        f"TOTAL: contacted={total['contacted']} responses={total['responses']} "
        f"demos={total['demos']} won={total['won']} lost={total['lost']}",
        f"Team response rate: {total_conv}",
    ]
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


@admin_only
async def cmd_pipeline(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    pipeline = get_pipeline_summary()
    total = sum(pipeline.values())

    lines = ["<b>DEAL PIPELINE</b>", ""]
    stage_labels = {
        "new": "New Leads", "contacted": "Contacted", "engaged": "Engaged",
        "interested": "Interested", "closing": "Closing", "won": "Won", "lost": "Lost",
    }
    for stage, count in pipeline.items():
        if count:
            pct = f"({count/max(total,1)*100:.0f}%)"
            bar = "█" * min(count, 15)
            lines.append(f"{stage_labels.get(stage, stage):<12} {bar} {count} {pct}")

    lines += ["", f"Total leads in system: <b>{total}</b>"]

    stuck = get_stuck_deals()
    if stuck:
        lines += ["", f"Stuck deals needing attention: <b>{len(stuck)}</b>"]
        for l in stuck[:3]:
            lines.append(f"  ! #{l['id']} {l['name']} — {l['stage']}")

    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


@admin_only
async def cmd_agents(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    agents = get_agents()
    if not agents:
        await update.message.reply_text("No agents registered yet.")
        return

    lines = [f"<b>AGENTS ({len(agents)})</b>", ""]
    for agent in agents:
        today_stats = get_agent_stats(agent_id=agent["chat_id"])
        today = next((s for s in today_stats if s["report_date"] == __import__("datetime").date.today().isoformat()), {})
        lines.append(
            f"<b>{agent['name']}</b> (ID: {agent['chat_id']})\n"
            f"  Status: {agent['status']}  |  Joined: {agent['joined_at']}\n"
            f"  Today: contacted={today.get('contacted',0)} demos={today.get('demos',0)} won={today.get('won',0)}"
        )
        lines.append("")

    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


@admin_only
async def cmd_agent(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Usage: /agent <chat_id or name>")
        return

    search = ctx.args[0]
    agents = get_agents()
    found = next(
        (a for a in agents if str(a["chat_id"]) == search or search.lower() in a["name"].lower()),
        None,
    )
    if not found:
        await update.message.reply_text(f"Agent '{search}' not found.")
        return

    stats = get_agent_stats(agent_id=found["chat_id"])
    leads = get_leads(agent_id=found["chat_id"], limit=5)
    active_leads = [l for l in leads if l["stage"] not in ("won", "lost")]

    lines = [f"<b>AGENT: {found['name']}</b>", ""]

    if stats:
        lines.append("<b>Performance History:</b>")
        for s in stats[:7]:
            lines.append(
                f"  {s['report_date']}: contacted={s['contacted']} responses={s['responses']} "
                f"demos={s['demos']} won={s['won']}"
            )
        lines.append("")

    if active_leads:
        lines.append("<b>Active Leads:</b>")
        for l in active_leads:
            lines.append(f"  #{l['id']} {l['name']} — {l['stage']}")

    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


@admin_only
async def cmd_intelligence(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    report = build_intelligence_report()
    await update.message.reply_text(report, parse_mode="HTML")


@admin_only
async def cmd_followup_all(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    due = get_followups_due()
    if not due:
        await update.message.reply_text("No follow-ups overdue across the team.")
        return
    await update.message.reply_text(build_followup_alert(due), parse_mode="HTML")


@admin_only
async def cmd_broadcast(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Usage: /broadcast <message>")
        return

    msg = " ".join(ctx.args)
    agents = get_agents()
    sent = 0
    failed = 0

    for agent in agents:
        if str(agent["chat_id"]) == str(OWNER_CHAT_ID):
            continue
        try:
            await ctx.bot.send_message(
                chat_id=agent["chat_id"],
                text=f"<b>Message from Admin:</b>\n\n{msg}",
                parse_mode="HTML",
            )
            sent += 1
        except Exception as e:
            logger.warning(f"Broadcast failed for {agent['chat_id']}: {e}")
            failed += 1

    await update.message.reply_text(
        f"Broadcast sent to {sent} agent(s). Failed: {failed}."
    )


@admin_only
async def cmd_add_leads(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Starting manual lead cycle... This may take a few minutes.")
    try:
        from main import run_daily_lead_cycle
        result = await run_daily_lead_cycle()
        count = len(result.get("all_leads", []))
        await update.message.reply_text(f"Lead cycle complete. {count} leads processed.")
    except Exception as e:
        logger.error(f"Manual lead cycle failed: {e}")
        await update.message.reply_text(f"Lead cycle failed: {e}")
