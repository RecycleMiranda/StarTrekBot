document.addEventListener('DOMContentLoaded', async () => {
    const statusMsg = document.getElementById('status-msg');
    const saveBtn = document.getElementById('save-btn');
    const qrBox = document.getElementById('qr-box');
    const refreshQrBtn = document.getElementById('refresh-qr');

    // URL Params
    const urlParams = new URLSearchParams(window.location.search);
    const token = urlParams.get('token') || '';

    // Panel Logic
    const menuBtns = document.querySelectorAll('.menu-btn[data-panel]');
    const panels = document.querySelectorAll('.panel');
    const panelTitle = document.getElementById('panel-title');

    const titles = {
        bridge: "STARSHIP BRIDGE - 实时状态",
        navigation: "STARSHIP NAVIGATION - QQ 身份验证",
        engineering: "ENGINEERING BAY - 核心配置",
        sentinel: "S.E.S.M. SENTINEL - 自主逻辑流控中心",
        records: "SUBSPACE RECORDS - 通讯日志"
    };

    menuBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const target = btn.getAttribute('data-panel');
            menuBtns.forEach(b => b.classList.remove('active'));
            panels.forEach(p => p.classList.remove('active'));
            btn.classList.add('active');
            document.getElementById(target).classList.add('active');
            panelTitle.textContent = titles[target] || "星舰控制中心";

            if (target === 'navigation') fetchQR();
            if (target === 'sentinel') fetchSentinelData();
        });
    });

    async function loadSettings() {
        try {
            const resp = await fetch(`/api/settings?token=${token}`);
            const json = await resp.json();
            if (json.code === 0) {
                const data = json.data;
                document.getElementById('enabled_groups').value = data.enabled_groups || '';
                document.getElementById('gemini_api_key').value = data.gemini_api_key || '';
                document.getElementById('moderation_enabled').value = String(data.moderation_enabled);
                document.getElementById('moderation_provider').value = data.moderation_provider || 'local';
                document.getElementById('napcat_port').value = data.napcat_port || '';
                document.getElementById('napcat_token').value = data.napcat_token || '';

                updateStatusCards(data);
                showStatus('主控系统连接成功', 'success');
            }
        } catch (e) {
            showStatus('网络异常：无法连接至主控中心', 'error');
        }
    }

    function updateStatusCards(config) {
        document.getElementById('gemini-status').textContent = config.gemini_api_key ? "✅ 在线" : "❌ 未配置";
        document.getElementById('mod-status').textContent = config.moderation_enabled ? `✅ ${config.moderation_provider}` : "⚪ 已禁用";
    }

    async function fetchQR() {
        qrBox.innerHTML = '<p style="color: #333">正在向 NapCat 请求二维码...</p>';
        try {
            const resp = await fetch(`/api/napcat/qr?token=${token}`);
            const json = await resp.json();
            if (json.code === 0 && json.data && json.data.qrCode) {
                // If it's a data URL
                qrBox.innerHTML = `<img src="${json.data.qrCode}" alt="Login QR">`;
            } else if (json.data && json.data.url) {
                // If it's a raw URL, we might need a QR generator or just show the link
                qrBox.innerHTML = `<p>扫描此链接登录: <br><small>${json.data.url}</small></p>`;
            } else {
                let msg = json.message || 'NapCat 未响应';
                if (json.raw_response) {
                    msg += `<br><details><summary>原始响应截图 (前500字)</summary><pre style="text-align:left; font-size:0.7rem; color:#666; background:#f4f4f4; padding:5px;">${json.raw_response}</pre></details>`;
                }
                qrBox.innerHTML = `<p style="color: red">${msg}</p>`;
            }
        } catch (e) {
            qrBox.innerHTML = `<p style="color: red">异常: 无法连接至代理接口</p>`;
        }
    }

    async function saveSettings() {
        const config = {
            enabled_groups: document.getElementById('enabled_groups').value,
            gemini_api_key: document.getElementById('gemini_api_key').value,
            moderation_enabled: document.getElementById('moderation_enabled').value === 'true',
            moderation_provider: document.getElementById('moderation_provider').value,
            napcat_port: parseInt(document.getElementById('napcat_port').value),
            napcat_token: document.getElementById('napcat_token').value
        };

        try {
            saveBtn.disabled = true;
            const resp = await fetch(`/api/settings?token=${token}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(config)
            });
            const json = await resp.json();
            if (json.code === 0) {
                showStatus('✅ 配置已同步', 'success');
                updateStatusCards(config);
            }
        } catch (e) {
            showStatus('❌ 存储失败', 'error');
        } finally {
            saveBtn.disabled = false;
        }
    }

    async function fetchSentinelData() {
        const sentinelList = document.getElementById('sentinel-list');
        try {
            const resp = await fetch(`/api/sentinel/status?token=${token}`);
            const json = await resp.json();
            if (json.code === 0 && json.data) {
                const triggers = json.data.triggers || [];
                if (triggers.length === 0) {
                    sentinelList.innerHTML = `
                        <div class="status-card" style="grid-column: 1/-1; border-color: #666; opacity: 0.6;">
                            <p>主控核心当前无活跃的自主逻辑监控项 (S.E.S.M. Idle)</p>
                        </div>
                    `;
                    return;
                }

                sentinelList.innerHTML = triggers.map(t => `
                    <div class="sentinel-card">
                        <div class="sentinel-id">${t.id}</div>
                        <div class="sentinel-desc">${t.desc}</div>
                        <div class="sentinel-logic">
                            <span class="logic-if">IF</span> ${t.condition || 'N/A'}<br>
                            <span class="logic-then">THEN</span> ${t.action || 'N/A'}
                        </div>
                        <div class="sentinel-stats">
                            <span>命中频率: <span class="hit-badge">${t.hits}</span></span>
                            <span>上次执行: ${t.last_run ? new Date(t.last_run * 1000).toLocaleTimeString() : '从未触发'}</span>
                        </div>
                    </div>
                `).join('');
            }
        } catch (e) {
            console.error('Failed to fetch sentinel data', e);
        }
    }

    // Auto-refresh for bridge and sentinel panels
    setInterval(() => {
        const activePanel = document.querySelector('.panel.active');
        if (activePanel && activePanel.id === 'sentinel') {
            fetchSentinelData();
        }
        if (activePanel && activePanel.id === 'bridge') {
            // In future, update real-time bridge status here
        }
    }, 5000);

    function showStatus(msg, type) {
        statusMsg.textContent = msg;
        statusMsg.className = type;
    }

    refreshQrBtn.addEventListener('click', fetchQR);
    saveBtn.addEventListener('click', saveSettings);
    loadSettings();
});
