"""
WebSocket endpoint for AI agent social feed.
Streams real-time Gemini-generated posts and comments.
"""
import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from agents.gemini_social import gemini_social

logger = logging.getLogger(__name__)
router = APIRouter()

@router.websocket("/ws/social")
async def ws_social(websocket: WebSocket):
    await websocket.accept()
    q = gemini_social.subscribe()

    try:
        recent = gemini_social.get_recent_posts(30)
        await websocket.send_json({"type": "history", "posts": recent})
    except Exception:
        pass

    try:
        while True:
            try:
                item = await asyncio.wait_for(q.get(), timeout=30.0)
                await websocket.send_json(item)
            except asyncio.TimeoutError:
                await websocket.send_json({"type": "ping"})
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.debug(f"ws_social client disconnected: {e}")
    finally:
        gemini_social.unsubscribe(q)

@router.post("/api/social/start")
async def start_social():
    gemini_social.start()
    return {"status": "started", "running": gemini_social.is_running}

@router.post("/api/social/stop")
async def stop_social():
    gemini_social.stop()
    return {"status": "stopped", "running": False}

@router.get("/api/social/status")
async def social_status():
    return {
        "running": gemini_social.is_running,
        "post_count": len(gemini_social._posts),
    }

@router.post("/api/social/human-post")
async def human_post(body: dict):
    """Allow humans to post to the social feed."""
    from agents.gemini_social import SocialPost, _next_post_id, AGENT_PERSONAS
    import time, random

    content = body.get("content", "").strip()
    username = body.get("username", "You")
    if not content:
        return {"error": "Empty post"}

    post = SocialPost(
        id=_next_post_id(),
        agent_name=username,
        content=content,
        timestamp=time.time(),
        sentiment="neutral",
        token=None,
        likes=0,
        comments=[],
        is_ai=False,
    )
    gemini_social._posts.append(post)

    msg = {
        "type": "post",
        "post": {
            "id": post.id,
            "agent_name": post.agent_name,
            "content": post.content,
            "timestamp": post.timestamp,
            "sentiment": post.sentiment,
            "token": post.token,
            "likes": post.likes,
            "comments": post.comments,
            "is_ai": False,
            "avatar": username[:2].upper(),
            "color": "#64748b",
        }
    }
    await gemini_social._broadcast(msg)

    if gemini_social.is_running:
        asyncio.create_task(_delayed_agent_response(post))

    return {"status": "posted"}

async def _delayed_agent_response(human_post):
    """Have an agent respond to a human post after a delay."""
    await asyncio.sleep(5 + __import__('random').random() * 5)
    if gemini_social.is_running:
        await gemini_social._generate_comment_cycle()
