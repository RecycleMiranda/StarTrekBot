import os
import json
import logging
import asyncio
from typing import Optional, Dict

try:
    from tencentcloud.common import credential
    from tencentcloud.common.profile.client_profile import ClientProfile
    from tencentcloud.common.profile.http_profile import HttpProfile
    from tencentcloud.common.exception.tencent_cloud_sdk_exception import TencentCloudSDKException
    from tencentcloud.tms.v20201229 import tms_client, models
    TENCENT_SDK_AVAILABLE = True
except ImportError:
    TENCENT_SDK_AVAILABLE = False

# Config
MODERATION_ENABLED = os.getenv("MODERATION_ENABLED", "false").lower() == "true"
SECRET_ID = os.getenv("TENCENT_SECRET_ID")
SECRET_KEY = os.getenv("TENCENT_SECRET_KEY")
REGION = os.getenv("TENCENT_REGION", "ap-guangzhou")
BIZ_TYPE = os.getenv("TENCENT_TMS_BIZTYPE")
TIMEOUT = int(os.getenv("MODERATION_TIMEOUT_SECONDS", "3"))

logger = logging.getLogger(__name__)

# Risk Levels
RISK_NONE = 0
RISK_LOW = 1
RISK_MED = 2
RISK_HIGH = 3

async def moderate_text(text: str, stage: str = "input", meta: Optional[dict] = None) -> dict:
    """
    Moderates text using Tencent Cloud TMS.
    Returns a normalized moderation result.
    """
    if not MODERATION_ENABLED:
        return _result(True, "pass", RISK_NONE, "moderation_disabled", "disabled")

    if not TENCENT_SDK_AVAILABLE:
        logger.warning("tencentcloud-sdk-python-tms not installed but moderation enabled.")
        return _result(True, "pass", RISK_NONE, "sdk_missing", "error")

    if not SECRET_ID or not SECRET_KEY:
        logger.warning("Tencent Cloud credentials not configured.")
        return _result(True, "pass", RISK_NONE, "not_configured", "error")

    try:
        # Tencent SDK is synchronous, wrap in executor for async safety
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _call_tms_sync, text)
        return result
    except Exception as e:
        logger.error(f"Tencent TMS moderation failed: {e}")
        return _result(True, "pass", RISK_NONE, str(e), "error")

def _call_tms_sync(text: str) -> dict:
    """Synchronous call to Tencent TMS SDK"""
    try:
        cred = credential.Credential(SECRET_ID, SECRET_KEY)
        http_profile = HttpProfile()
        http_profile.reqTimeout = TIMEOUT
        
        client_profile = ClientProfile()
        client_profile.httpProfile = http_profile
        
        client = tms_client.TmsClient(cred, REGION, client_profile)
        
        req = models.TextModerationRequest()
        req.Content = text
        if BIZ_TYPE:
            req.BizType = BIZ_TYPE

        resp = client.TextModeration(req)
        
        # Suggestion: Pass, Review, Block
        suggestion = resp.Suggestion
        
        if suggestion == "Block":
            return _result(False, "block", RISK_HIGH, "tms_blocked", "tencent_tms", {"label": resp.Label})
        elif suggestion == "Review":
            # Conservative: treat Review as Block for now
            return _result(False, "block", RISK_MED, "tms_review_required", "tencent_tms", {"label": resp.Label})
        else:
            return _result(True, "pass", RISK_NONE, "tms_passed", "tencent_tms")

    except TencentCloudSDKException as err:
        logger.warning(f"Tencent Cloud SDK error: {err}")
        return _result(True, "pass", RISK_NONE, f"sdk_error: {err.code}", "error")

def _result(allow: bool, action: str, risk: int, reason: str, provider: str, raw: dict = None) -> dict:
    return {
        "allow": allow,
        "action": action,
        "risk_level": risk,
        "reason": reason,
        "provider": provider,
        "raw": raw
    }

def get_status() -> dict:
    return {
        "enabled": MODERATION_ENABLED,
        "sdk_available": TENCENT_SDK_AVAILABLE,
        "configured": bool(SECRET_ID and SECRET_KEY),
        "region": REGION,
        "provider": "tencent_tms" if MODERATION_ENABLED else "disabled"
    }
