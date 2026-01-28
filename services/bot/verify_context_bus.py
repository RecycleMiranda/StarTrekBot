from app.context_bus import get_odn_snapshot
from app.ship_systems import get_ship_systems

def test_context_bus():
    print("Testing Context Bus with new MSD Lookups...")
    try:
        # Provide a user_profile to satisfy clearance check logic if any
        snapshot = get_odn_snapshot(session_id="verify_session", user_profile={"clearance": 10})
        print("Success! Snapshot Generated:")
        print(f"Proprioception: {snapshot['proprioception']}")
        print(f"Warp Core: {snapshot['ship_status']['power']['warp_core_output']}")
        print(f"Hull: {snapshot['ship_status']['hull']['integrity']}")
    except Exception as e:
        print(f"FAILED: {e}")
        raise e

if __name__ == "__main__":
    test_context_bus()
