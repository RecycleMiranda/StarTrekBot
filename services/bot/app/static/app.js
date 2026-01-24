document.addEventListener('DOMContentLoaded', async () => {
    const statusMsg = document.getElementById('status-msg');
    const saveBtn = document.getElementById('save-btn');

    // 从 URL 获取 Token
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
                // New Fields
                document.getElementById('gemini_api_key').value = data.gemini_api_key || '';
                document.getElementById('gemini_rp_model').value = data.gemini_rp_model || 'gemini-2.0-flash-lite';
                document.getElementById('moderation_enabled').value = String(data.moderation_enabled);
                document.getElementById('moderation_provider').value = data.moderation_provider || 'local';
                document.getElementById('tencent_secret_id').value = data.tencent_secret_id || '';
                document.getElementById('tencent_secret_key').value = data.tencent_secret_key || '';

                toggleModFields();
                showStatus('主控系统连接成功', 'success');
            } else if (json.code === 401) {
                showStatus('身份认证失败，请检查 URL 中的 Token', 'error');
            } else {
                showStatus('配置加载失败：' + json.message, 'error');
            }
        } catch (e) {
            showStatus('网络异常：无法连接至主控中心', 'error');
        }
    }

    async function saveSettings() {
        const config = {
            enabled_groups: document.getElementById('enabled_groups').value,
            computer_prefix: document.getElementById('computer_prefix').value,
            sender_type: document.getElementById('sender_type').value,
            rp_style_strict: document.getElementById('rp_style_strict').value === 'true',
            qq_send_endpoint: document.getElementById('qq_send_endpoint').value,
            // New Fields
            gemini_api_key: document.getElementById('gemini_api_key').value,
            gemini_rp_model: document.getElementById('gemini_rp_model').value,
            moderation_enabled: document.getElementById('moderation_enabled').value === 'true',
            moderation_provider: document.getElementById('moderation_provider').value,
            tencent_secret_id: document.getElementById('tencent_secret_id').value,
            tencent_secret_key: document.getElementById('tencent_secret_key').value
        };

        try {
            saveBtn.disabled = true;
            showStatus('正在同步配置...', '');
            const resp = await fetch(`/api/settings?token=${token}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(config)
            });
            const json = await resp.json();
            if (json.code === 0) {
                showStatus('✅ 配置已成功存入持久化存储', 'success');
            } else {
                showStatus('❌ 存储失败：' + json.message, 'error');
            }
        } catch (e) {
            showStatus('❌ 网络异常：配置未能同步', 'error');
        } finally {
            saveBtn.disabled = false;
        }
    }

    function showStatus(msg, type) {
        statusMsg.textContent = msg;
        statusMsg.className = type;
        if (type === 'success' || type === 'error') {
            setTimeout(() => {
                if (statusMsg.textContent === msg) statusMsg.textContent = '';
            }, 5000);
        }
    }

    function toggleModFields() {
        const provider = document.getElementById('moderation_provider').value;
        const tencentFields = document.getElementById('tencent-auth-fields');
        const localInfo = document.getElementById('local-mod-info');

        if (provider === 'tencent') {
            tencentFields.style.display = 'grid';
            localInfo.style.display = 'none';
        } else {
            tencentFields.style.display = 'none';
            localInfo.style.display = 'block';
        }
    }

    document.getElementById('moderation_provider').addEventListener('change', toggleModFields);
    saveBtn.addEventListener('click', saveSettings);
    loadSettings();
});
