"""
Full lead processing pipeline.

Steps:
  1. Normalize
  2. Deduplicate
  3. Score
  4. Filter (score >= MIN_LEAD_SCORE)
  5. Detect intent
  6. Filter (intent HIGH or MEDIUM)
  7. Detect opportunity
  8. Classify niche
  9. Attach micro-strategy
 10. Generate hook
 11. Select top 5
"""
import logging
from typing import List, Dict, Set

from processing.normalizer        import normalize
from processing.scorer            import score_lead
from processing.intent_detector   import detect_intent
from processing.opportunity_detector import detect_opportunity
from processing.niche_classifier  import classify_niche
from processing.hook_generator    import generate_hook
from config import MIN_LEAD_SCORE, TOP_N_LEADS, NICHE_STRATEGY

logger = logging.getLogger(__name__)


def run_pipeline(raw_leads: List[Dict], known_ids: Set[str]) -> Dict:
    """
    Process raw leads through the full pipeline.

    Returns:
      {
        "all_leads":  [qualified lead dicts],
        "top_leads":  [top N lead dicts],
        "stats": { total_raw, after_dedup, after_score, after_intent, top_n }
      }
    """
    stats = {"total_raw": len(raw_leads)}

    # Step 1 — Normalize
    leads = [normalize(r) for r in raw_leads]

    # Step 2 — Deduplicate
    seen: Set[str] = set(known_ids)
    unique = []
    for lead in leads:
        if lead["lead_id"] not in seen:
            seen.add(lead["lead_id"])
            unique.append(lead)
    stats["after_dedup"] = len(unique)
    logger.info(f"After dedup: {len(unique)} / {len(leads)}")

    # Step 3 & 4 — Score + filter
    scored = []
    for lead in unique:
        score, breakdown = score_lead(lead)
        lead["score"]           = score
        lead["score_breakdown"] = breakdown
        if score >= MIN_LEAD_SCORE:
            scored.append(lead)
    stats["after_score"] = len(scored)
    logger.info(f"After score filter (≥{MIN_LEAD_SCORE}): {len(scored)}")

    # Step 5 & 6 — Intent + filter
    qualified = []
    for lead in scored:
        intent = detect_intent(lead)
        lead["intent"] = intent
        if intent in ("HIGH", "MEDIUM"):
            qualified.append(lead)
    stats["after_intent"] = len(qualified)
    logger.info(f"After intent filter (HIGH/MEDIUM): {len(qualified)}")

    # Steps 7–10 — Enrich
    for lead in qualified:
        lead["opportunity"] = detect_opportunity(lead)
        lead["niche"]       = classify_niche(lead)
        lead["strategy"]    = NICHE_STRATEGY.get(lead["niche"], "")
        lead["hook"]        = generate_hook(lead)

    # Step 11 — Top 5 by score (then intent priority)
    intent_rank = {"HIGH": 0, "MEDIUM": 1}
    top = sorted(
        qualified,
        key=lambda l: (-l["score"], intent_rank.get(l["intent"], 2))
    )[:TOP_N_LEADS]

    stats["top_n"] = len(top)
    logger.info(f"Top {TOP_N_LEADS} selected: {len(top)}")

    return {"all_leads": qualified, "top_leads": top, "stats": stats}
