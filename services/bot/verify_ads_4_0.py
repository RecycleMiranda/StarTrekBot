import sys
import os
import logging
from pprint import pprint

# Setup paths
sys.path.append(os.path.join(os.path.dirname(__file__), "app"))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ADS_4_0_TEST")

def test_protocol_engine():
    logger.info("--- Testing Protocol Engine Core ---")
    try:
        from app.protocol_engine import get_protocol_engine
        engine = get_protocol_engine()
        
        # 1. List loaded protocols
        logger.info(f"Loaded Protocols: {list(engine.protocols.keys())}")
        assert "GO_01" in engine.protocols
        assert "GO_07" in engine.protocols
        
        # 2. Test GO-07 (Talos IV Ban) - Should Block
        logger.info("Testing GO-07 Trigger (Navigation)...")
        res = engine.evaluate_action("NAVIGATION_SET", {"target": "Talos IV"})
        pprint(res)
        assert res['allowed'] == False
        assert "GO_07" in res['violations'][0]
        
        # 3. Test GO-24 (Bombardment) - Should Unlock/Warn (Implementation specific)
        logger.info("Testing GO-24 Trigger (Manual Command)...")
        res = engine.evaluate_action("MANUAL_COMMAND", {"keyword": "Execute General Order 24"})
        pprint(res)
        # Based on my YAML, actions include UNLOCK_WMD but no explicit BLOCK unless I added one.
        # Let's check what I wrote: "on_active": ["UNLOCK..."]
        # Wait, my logic checks for "BLOCK/LOCK/DENY" strings in actions to determine violation.
        # If GO-24 just says "UNLOCK", it might pass as 'allowed' but with warnings?
        # Re-reading engine logic: if any act string has "BLOCK", allowed=False.
        # GO_24 actions: UNLOCK_WMD... so it might be RETURN allowed=True but active.
        # Correction: The trigger logic in engine is simple string matching.
        
        # 4. Test Prime Directive (GO-01)
        logger.info("Testing GO-01 (Sensor Contact)...")
        res = engine.evaluate_action("SENSOR_CONTACT", {}) # Missing condition data, might skip?
        # My engine logic doesn't fully parse conditions yet, just triggers.
        # GO_01 trigger is SENSOR_CONTACT.
        # If I send SENSOR_CONTACT, it matches trigger. 
        # Actions: BLOCK_TRANSPORTER... -> Should be Blocking.
        res = engine.evaluate_action("SENSOR_CONTACT", {"condition": "Pre-Warp"}) 
        pprint(res)
        assert res['allowed'] == False
        
        logger.info("Unknown Action Type...")
        res = engine.evaluate_action("EAT_SANDWICH", {})
        assert res['allowed'] == True

        logger.info("ADS 4.0 Engine Test PASSED")
    except Exception as e:
        logger.error(f"Test Failed: {e}")
        raise

if __name__ == "__main__":
    test_protocol_engine()
