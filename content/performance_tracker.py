import logging
import requests
from typing import Dict, List
from config import (
    META_ACCESS_TOKEN, META_INSTAGRAM_ACCOUNT_ID, META_FACEBOOK_PAGE_ID,
    TIKTOK_ACCESS_TOKEN,
)

logger = logging.getLogger(__name__)

META_BASE   = "https://graph.facebook.com/v19.0"
TIKTOK_BASE = "https://open.tiktokapis.com/v2"

_EMPTY_METRICS = lambda: {
    "views": 0, "impressions": 0, "reach": 0,
    "likes": 0, "comments": 0, "shares": 0, "saves": 0,
}


def fetch_instagram_posts(limit: int = 10) -> List[Dict]:
    if not META_ACCESS_TOKEN or not META_INSTAGRAM_ACCOUNT_ID:
        logger.warning("Meta/Instagram credentials not set — skipping")
        return []
    try:
        r = requests.get(
            f"{META_BASE}/{META_INSTAGRAM_ACCOUNT_ID}/media",
            params={
                "fields": "id,caption,timestamp,media_type",
                "limit": limit,
                "access_token": META_ACCESS_TOKEN,
            },
            timeout=15,
        )
        r.raise_for_status()
        posts = []
        for media in r.json().get("data", []):
            metrics = _instagram_insights(media["id"])
            posts.append({
                "post_id":   media["id"],
                "platform":  "instagram",
                "caption":   media.get("caption", "")[:120],
                "timestamp": media.get("timestamp", ""),
                **metrics,
            })
        return posts
    except Exception as e:
        logger.error(f"Instagram fetch failed: {e}")
        return []


def _instagram_insights(media_id: str) -> Dict:
    metrics = _EMPTY_METRICS()
    try:
        r = requests.get(
            f"{META_BASE}/{media_id}/insights",
            params={
                "metric": "impressions,reach,likes,comments,shares,saved,video_views",
                "access_token": META_ACCESS_TOKEN,
            },
            timeout=15,
        )
        r.raise_for_status()
        for item in r.json().get("data", []):
            name  = item["name"]
            value = (item.get("values") or [{}])[0].get("value", 0) or item.get("value", 0)
            if name == "impressions":  metrics["impressions"] = value
            elif name == "reach":      metrics["reach"]       = value
            elif name == "likes":      metrics["likes"]       = value
            elif name == "comments":   metrics["comments"]    = value
            elif name == "shares":     metrics["shares"]      = value
            elif name == "saved":      metrics["saves"]       = value
            elif name == "video_views": metrics["views"]      = value
    except Exception as e:
        logger.error(f"Instagram insights failed ({media_id}): {e}")
    return metrics


def fetch_facebook_posts(limit: int = 10) -> List[Dict]:
    if not META_ACCESS_TOKEN or not META_FACEBOOK_PAGE_ID:
        logger.warning("Facebook credentials not set — skipping")
        return []
    try:
        r = requests.get(
            f"{META_BASE}/{META_FACEBOOK_PAGE_ID}/posts",
            params={
                "fields": "id,message,created_time,insights.metric(post_impressions,post_reach,post_activity_by_action_type)",
                "limit": limit,
                "access_token": META_ACCESS_TOKEN,
            },
            timeout=15,
        )
        r.raise_for_status()
        posts = []
        for post in r.json().get("data", []):
            metrics = _EMPTY_METRICS()
            for insight in post.get("insights", {}).get("data", []):
                name  = insight["name"]
                value = (insight.get("values") or [{}])[0].get("value", 0)
                if name == "post_impressions": metrics["impressions"] = value
                elif name == "post_reach":     metrics["reach"]       = value
                elif name == "post_activity_by_action_type":
                    if isinstance(value, dict):
                        metrics["likes"]    = value.get("like", 0)
                        metrics["comments"] = value.get("comment", 0)
                        metrics["shares"]   = value.get("share", 0)
            posts.append({
                "post_id":   post["id"],
                "platform":  "facebook",
                "caption":   post.get("message", "")[:120],
                "timestamp": post.get("created_time", ""),
                **metrics,
            })
        return posts
    except Exception as e:
        logger.error(f"Facebook fetch failed: {e}")
        return []


def fetch_tiktok_posts(limit: int = 10) -> List[Dict]:
    if not TIKTOK_ACCESS_TOKEN:
        logger.warning("TikTok credentials not set — skipping")
        return []
    try:
        r = requests.post(
            f"{TIKTOK_BASE}/video/list/",
            json={
                "max_count": limit,
                "fields": ["id", "title", "create_time", "view_count", "like_count", "comment_count", "share_count"],
            },
            headers={"Authorization": f"Bearer {TIKTOK_ACCESS_TOKEN}"},
            timeout=15,
        )
        r.raise_for_status()
        posts = []
        for video in r.json().get("data", {}).get("videos", []):
            vc = video.get("view_count", 0)
            posts.append({
                "post_id":   str(video.get("id", "")),
                "platform":  "tiktok",
                "caption":   video.get("title", "")[:120],
                "timestamp": str(video.get("create_time", "")),
                "views":       vc,
                "impressions": vc,
                "reach":       vc,
                "likes":     video.get("like_count", 0),
                "comments":  video.get("comment_count", 0),
                "shares":    video.get("share_count", 0),
                "saves":     0,
            })
        return posts
    except Exception as e:
        logger.error(f"TikTok fetch failed: {e}")
        return []


def fetch_all_platform_posts(limit: int = 10) -> List[Dict]:
    posts = (
        fetch_instagram_posts(limit)
        + fetch_facebook_posts(limit)
        + fetch_tiktok_posts(limit)
    )
    logger.info(f"Fetched {len(posts)} posts across all platforms")
    return posts
