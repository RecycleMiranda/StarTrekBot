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
        msd: "MASTER SYSTEMS DISPLAY - 实时诊断",
        sops: "SOP LEARNING DOCK - 规程核准终端",
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
            if (target === 'msd') fetchMSDData();
            if (target === 'sops') fetchSOPData();
            if (target === 'bridge') fetchFaults();
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
                document.getElementById('sender_type').value = data.sender_type || 'mock';
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
            sender_type: document.getElementById('sender_type').value,
            napcat_port: parseInt(document.getElementById('napcat_port').value),
            napcat_token: document.getElementById('napcat_token').value
        };

        try {
            saveBtn.disabled = true;
            console.log("Saving config:", config);
            const resp = await fetch(`/api/settings?token=${token}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(config)
            });
            const json = await resp.json();
            if (json.code === 0) {
                showStatus(`✅ 配置已同步 (模式: ${config.sender_type})`, 'success');
                alert(`设置保存成功！当前发送模式：${config.sender_type}\n注意：切换模式后必须在服务器重启机器人。`);
                updateStatusCards(config);
            } else {
                showStatus(`❌ 存储失败: ${json.message}`, 'error');
                alert("存储失败: " + json.message);
            }
        } catch (e) {
            console.error("Save error:", e);
            showStatus('❌ 存储异常：检查网络连接', 'error');
            alert("存储异常: " + e.message);
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

    async function fetchMSDData() {
        const container = document.getElementById('msd-container');
        try {
            const resp = await fetch(`/api/v1/lcars/msd?token=${token}`);
            const json = await resp.json();
            if (json.code === 0 && json.data) {
                container.innerHTML = Object.entries(json.data).map(([catId, cat]) => `
                    <div style="margin-bottom: 20px;">
                        <h3 style="color:var(--lcars-gold); font-size: 0.8rem; border-bottom: 1px solid rgba(255,153,0,0.3);">${cat.display_name_en} (${cat.display_name_cn})</h3>
                        ${Object.entries(cat.components || {}).map(([compId, comp]) => `
                            <div class="msd-node">
                                <span>${comp.name}</span>
                                <span class="status-indicator ${comp.state === 'OFFLINE' ? 'status-offline' : (comp.state === 'HAZARD' ? 'status-hazard' : 'status-online')}">
                                    ${comp.state}
                                </span>
                            </div>
                        `).join('')}
                    </div>
                `).join('');
            }
        } catch (e) {
            console.error('MSD Sync Failure', e);
        }
    }

    async function fetchSOPData() {
        const list = document.getElementById('sop-list');
        try {
            const resp = await fetch(`/api/v1/lcars/sop?token=${token}`);
            const json = await resp.json();
            if (json.code === 0 && json.data) {
                const sops = Object.entries(json.data);
                if (sops.length === 0) {
                    list.innerHTML = '<p style="opacity:0.5;">没有待核准的 DRAFT 规程。</p>';
                    return;
                }
                list.innerHTML = sops.map(([query, sop]) => `
                    <div class="glass-panel sop-card">
                        <div style="font-size: 0.7rem; color: var(--lcars-teal);">NEURAL INFERENCE | ID: ${sop.intent_id}</div>
                        <div style="font-weight: bold; margin: 10px 0;">指令: "${query}"</div>
                        <div style="font-family: monospace; font-size: 0.8rem; background:rgba(0,0,0,0.3); padding: 10px;">
                            ${sop.tool_chain.map(step => `&gt; Execute ${step.tool}(${JSON.stringify(step.args)})`).join('<br>')}
                        </div>
                        <div class="action-bar">
                            <button class="st-btn btn-approve" onclick="window.approveSOP('${query}')">核准进入协议 (APPROVE)</button>
                            <button class="st-btn btn-reject">忽略 (IGNORE)</button>
                        </div>
                    </div>
                `).join('');
            }
        } catch (e) {
            console.error('SOP Retrieval Failure', e);
        }
    }

    window.approveSOP = async (query) => {
        try {
            const resp = await fetch(`/api/v1/lcars/sop/approve?token=${token}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query })
            });
            const json = await resp.json();
            if (json.code === 0) {
                alert("规程已成功核准并在子空间缓存生效。");
                fetchSOPData();
            }
        } catch (e) {
            alert("Approve failed: " + e.message);
        }
    };

    async function fetchFaults() {
        const faultsList = document.getElementById('faults-list');
        const alertLevel = document.getElementById('alert-level');
        const alertCard = document.getElementById('alert-card');
        try {
            const resp = await fetch(`/api/v1/lcars/faults?token=${token}`);
            const json = await resp.json();
            if (json.code === 0 && json.data) {
                const faults = Object.entries(json.data);
                if (faults.length === 0) {
                    faultsList.innerHTML = '<span style="color:var(--lcars-success);">[ NOMINAL ] 未检测到活跃故障。</span>';
                    alertLevel.textContent = "GREEN ALERT";
                    alertCard.style.borderLeftColor = "var(--lcars-teal)";
                } else {
                    faultsList.innerHTML = faults.map(([id, f]) => `
                        <div style="margin-bottom: 5px; color: var(--lcars-red);">
                            [!] ${f.subsystem || 'SYS'}: ${f.error_msg} (${f.timestamp})
                        </div>
                    `).join('');
                    alertLevel.textContent = "RED ALERT";
                    alertCard.style.borderLeftColor = "var(--lcars-red)";
                }
            }
        } catch (e) {
            console.error('Fault Scan Failure', e);
        }
    }

    // Auto-refresh loop
    setInterval(() => {
        const activePanel = document.querySelector('.panel.active');
        if (!activePanel) return;

        const id = activePanel.id;
        if (id === 'sentinel') fetchSentinelData();
        if (id === 'msd') fetchMSDData();
        if (id === 'sops') fetchSOPData();
        if (id === 'bridge') fetchFaults();
    }, 4000);

    function showStatus(msg, type) {
        statusMsg.textContent = msg;
        statusMsg.className = type;
    }

    refreshQrBtn.addEventListener('click', fetchQR);
    saveBtn.addEventListener('click', saveSettings);
    loadSettings();
});
