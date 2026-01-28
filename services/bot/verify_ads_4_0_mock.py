import sys
import os
import logging
from pprint import pprint

# Setup paths
sys.path.append(os.path.join(os.path.dirname(__file__), "app"))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ADS_4_0_TEST")

def test_protocol_engine_logic():
    logger.info("--- Testing Protocol Engine Logic (Mocked) ---")
    try:
        from app.protocol_engine import get_protocol_engine, Protocol
        engine = get_protocol_engine()
        
        # 1. Manually Inject a Test Protocol (Bypassing YAML Loader)
        # Simulating GO-07
        p_mock = Protocol(
            id="GO_TEST_07",
            name="Talos IV Ban (Mock)",
            category="RESTRICTED",
            priority=900,
            raw_data={
                "trigger": {"type": "NAVIGATION_SET", "target": "TALOS"},
                "actions": {"on_trigger": ["BLOCK_NAVIGATION", "ALERT_SECURITY"]}
            }
        )
        engine.protocols["GO_TEST_07"] = p_mock
        logger.info("Injected Mock Protocol: GO_TEST_07")
        
        # 2. Test Trigger Matching (Should Block)
        logger.info("Testing Evaluation: NAVIGATION_SET -> TALOS")
        res = engine.evaluate_action("NAVIGATION_SET", {"target": "Talos IV"})
        pprint(res)
        
        assert res['allowed'] == False, "Engine failed to BLOCK restricted action"
        assert "GO_TEST_07" in str(res['violations']), "Engine did not cite correct violation"
        
        # 3. Test Pass-through (Should Allow)
        logger.info("Testing Evaluation: NAVIGATION_SET -> EARTH")
        res2 = engine.evaluate_action("NAVIGATION_SET", {"target": "Earth"})
        pprint(res2)
        assert res2['allowed'] == True, "Engine blocked valid action"

        logger.info("ADS 4.0 Logic Verified ✅")
        
    except Exception as e:
        logger.error(f"Test Failed: {e}")
        raise

if __name__ == "__main__":
    test_protocol_engine_logic()
