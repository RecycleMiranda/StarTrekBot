import os
import logging
import asyncio
from .models import InternalEvent
from .config_manager import ConfigManager
from . import router, send_queue, rp_engine_gemini

logger = logging.getLogger(__name__)

def is_group_enabled(group_id: str | None) -> bool:
    """
    Checks if the given group_id is in the whitelist via ConfigManager.
    """
    if group_id is None:
        return True
    
    config = ConfigManager.get_instance()
    whitelist_raw = config.get("enabled_groups", "*")
    whitelist = [g.strip() for g in whitelist_raw.split(",") if g.strip()]
    
    if not whitelist or "*" in whitelist:
        return True
        
    return str(group_id) in whitelist

def handle_event(event: InternalEvent):
    """
    Dispatcher for internal events with group filtering.
    """
    if not is_group_enabled(event.group_id):
        logger.info(f"[Dispatcher] Group {event.group_id} not in whitelist. Dropping event.")
        return False

    logger.info(f"[Dispatcher] Handling Event: {event.model_dump_json(indent=2)}")
    
    # Skip empty messages
    if not event.text or not event.text.strip():
        logger.info("[Dispatcher] Empty message, skipping.")
        return False
    
    # Build session ID
    session_id = f"{event.platform}:{event.group_id or event.user_id}"
    
    # Route the message
    try:
        route_result = router.route_event(session_id, event.text, {"event": event.model_dump()})
        logger.info(f"[Dispatcher] Route result: {route_result}")
        
        # Check if we should respond (computer mode or high confidence)
        if route_result.get("route") == "computer" or route_result.get("confidence", 0) >= 0.7:
            # Generate AI reply asynchronously
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(
                    rp_engine_gemini.generate_computer_reply(
                        trigger_text=event.text,
                        context=[],  # Could add conversation history later
                        meta={"session_id": session_id, "user_id": event.user_id}
                    )
                )
            finally:
                loop.close()
            
            logger.info(f"[Dispatcher] AI result: {result}")
            
            if result and result.get("ok") and result.get("reply"):
                reply_text = result["reply"]
                logger.info(f"[Dispatcher] Sending reply: {reply_text[:100]}...")
                
                # Enqueue the response
                sq = send_queue.SendQueue.get_instance()
                sq.enqueue({
                    "group_id": event.group_id,
                    "user_id": event.user_id,
                    "message": reply_text
                })
                return True
            else:
                logger.info(f"[Dispatcher] AI returned no reply: {result.get('reason', 'unknown')}")
        else:
            logger.info(f"[Dispatcher] Route is chat/low confidence, not responding.")
    except Exception as e:
        logger.error(f"[Dispatcher] Error processing message: {e}", exc_info=True)
    
    return False

