  
import sys
import os
import time
from unittest.mock import MagicMock, patch

# Mock PIL and httpx before importing tools
sys.modules['PIL'] = MagicMock()
sys.modules['PIL.Image'] = MagicMock()
sys.modules['httpx'] = MagicMock()

# Add the app directory to sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

from app import tools

def test_avatar_cache():
    user_id = "12345"
    
    # Mock httpx.Client.get
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = b"fake_image_data"
    
    mock_client = MagicMock()
    mock_client.get.return_value = mock_response
    mock_client.__enter__.return_value = mock_client
    
    with patch('httpx.Client', return_value=mock_client):
        with patch('PIL.Image.open', return_value=MagicMock()) as mock_image_open:
            print("--- First Call (Should fetch fresh) ---")
            tools.get_personnel_file(f"[CQ:at,qq={user_id}]", user_id)
            assert mock_client.get.call_count == 1
            
            print("--- Second Call (Should use cache) ---")
            tools.get_personnel_file(f"[CQ:at,qq={user_id}]", user_id)
            # Call count should STILL be 1
            assert mock_client.get.call_count == 1
            print("SUCCESS: Cache worked as expected.")

if __name__ == "__main__":
    try:
        test_avatar_cache()
    except Exception as e:
        print(f"FAILED: {e}")
        sys.exit(1)
