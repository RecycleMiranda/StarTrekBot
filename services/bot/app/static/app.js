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
            qq_send_endpoint: document.getElementById('qq_send_endpoint').value
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

    saveBtn.addEventListener('click', saveSettings);
    loadSettings();
});
