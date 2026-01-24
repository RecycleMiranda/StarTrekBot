document.addEventListener('DOMContentLoaded', async () => {
    const statusMsg = document.getElementById('status-msg');
    const saveBtn = document.getElementById('save-btn');
    
    // Get token from URL
    const urlParams = new URLSearchParams(window.location.search);
    const token = urlParams.get('token') || '';

    async function loadSettings() {
        try {
            const resp = await fetch(`/api/settings?token=${token}`);
            const json = await resp.json();
            if (json.code === 0) {
                const data = json.data;
                document.getElementById('enabled_groups').value = data.enabled_groups || '';
                document.getElementById('computer_prefix').value = data.computer_prefix || '';
                document.getElementById('sender_type').value = data.sender_type || 'mock';
                document.getElementById('rp_style_strict').value = String(data.rp_style_strict);
                document.getElementById('qq_send_endpoint').value = data.qq_send_endpoint || '';
            } else {
                showStatus('Unauthorized or Error loading settings', 'error');
            }
        } catch (e) {
            showStatus('Network error loading settings', 'error');
        }
    }

    async function saveSettings() {
        const config = {
            enabled_groups: document.getElementById('enabled_groups').value,
            computer_prefix: document.getElementById('computer_prefix').value,
            sender_type: document.getElementById('sender_type').value,
            rp_style_strict: document.getElementById('rp_style_strict').value === 'true',
            qq_send_endpoint: document.getElementById('qq_send_endpoint').value
        };

        try {
            saveBtn.disabled = true;
            showStatus('Processing...', '');
            const resp = await fetch(`/api/settings?token=${token}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(config)
            });
            const json = await resp.json();
            if (json.code === 0) {
                showStatus('CONFIGURATION PERSISTED SUCCESSFULY', 'success');
            } else {
                showStatus('Save failed: ' + json.message, 'error');
            }
        } catch (e) {
            showStatus('Network error saving settings', 'error');
        } finally {
            saveBtn.disabled = false;
        }
    }

    function showStatus(msg, type) {
        statusMsg.textContent = msg;
        statusMsg.className = type;
        if (type) {
            setTimeout(() => { statusMsg.textContent = ''; }, 5000);
        }
    }

    saveBtn.addEventListener('click', saveSettings);
    loadSettings();
});
