import json
from .models import InternalEvent

def handle_event(event: InternalEvent):
    """
    Dispatcher for internal events.
    Currently just prints the event to stdout.
    """
    print(f"[Dispatcher] Handling Event: {event.model_dump_json(indent=2)}")
    
    # Placeholder for plugin system or further logic
    # TODO: route event to handlers
    return True
