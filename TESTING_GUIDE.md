# Starfleet Tactical & Logistics: Testing Guide

This guide provides instructions for verifying the newly deployed systems.

## 1. 战术系统验证 (Tactical OODA Loop)

战术系统随 Bot 启动。您可以通过检查日志来验证后台循环是否正常。

### 检查运行状态
查看 `services/bot/app/tactical/SENSOR_LOGS.md`，这是传感器主日志。
```bash
tail -f services/bot/app/tactical/SENSOR_LOGS.md
```
**预期现象**: 
- 每隔 10 秒左右，如果检测到联系人，会有 `ACQUISITION` 或 `TACTICAL_LOCK` 记录。
- 如果没有联系人，说明目前由于安全策略没有生成模拟流量（我们在 `main.py` 中默认关闭了模拟流量生成以防干扰）。

### 触发模拟战斗 (Manual Simulation)
如果您想立刻看到 AI 开火，可以运行以下命令手动注入一个敌对目标：
```bash
# 运行这个临时脚本来模拟发现并交战
python3 -c "from services.bot.app.tactical import SensorManager, TacticalCore; sm=SensorManager(); sm._generate_traffic(); tc=TacticalCore(sm); tc.scan_for_threats(); tc.execute_engagement()"
```

---

## 2. 物流同步验证 (Git Logistics Hub)

### 手动同步日志
您可以手动触发一次将本地日志同步到 GitHub `logs` 分支的操作：
```bash
python3 git_sync.py
```
**验证步骤**:
1. 运行命令后，检查输出是否包含 `Switching track to 'logs'...`。
2. 登录 GitHub 仓库，切换到 `logs` 分支。
3. 检查是否存在 `logs/SENSOR_LOGS.md` 和 `logs/ARSENAL_LEDGER.log`。

### 测试开机全量拉取 (Full Pull)
模拟您刚在另一台机器上提交了日志，现在要在本地拉取：
```bash
python3 git_sync.py pull
```
**预期现象**:
- 系统会执行 `MASTER PULL PROTOCOL`。
- 本地 `main` 和 `logs` 分支都会被更新。

---

## 3. 生产集成验证 (Integration)

检查 Bot 的启动日志以确认“启动拉取”已生效：
1. 重启您的 Docker 容器（或直接运行 `python3 -m services.bot.app.main`）。
2. 在开头几行寻找：
   `INFO:__main__:Initializing Starfleet Logistics Boot Sync...`
   以及
   `INFO:__main__:Logistics Sync Success: Local data tracks updated.`

> [!TIP]
> **实时监控**: 建议开启两个终端，一个监控 `SENSOR_LOGS.md`，另一个执行 `git_sync.py`。

---

## 4. 情报分析验证 (Log Intelligence & Analysis)

情报分析系统允许您分段读取日志并进行智能筛选。

### 导出战术摘要 (AI Summary)
让分析引擎为您总结最近的战术态势：
```bash
python3 -c "from services.bot.app.tactical.log_analyzer import LogAnalyzer; import os; ana=LogAnalyzer(os.getcwd()+'/services/bot/app'); print(ana.generate_summary('tactical'))"
```

### 智能事件筛选 (Smart Filtering)
只查看特定的“锁定 (LOCK)”事件或“命中 (BDA)”事件：
```bash
# 筛选所有 TACTICAL_LOCK 事件
python3 -c "from services.bot.app.tactical.log_analyzer import LogAnalyzer; import os; ana=LogAnalyzer(os.getcwd()+'/services/bot/app'); print('\n'.join(ana.filter_logs('tactical', event_type='TACTICAL_LOCK')))"
```

### 分段读取测试 (Pagination)
模拟 AI 按需读取日志（例如只读取前 5 条）：
```bash
python3 -c "from services.bot.app.tactical.log_analyzer import LogAnalyzer; import os; ana=LogAnalyzer(os.getcwd()+'/services/bot/app'); print(ana.read_segmented('tactical', page=0, page_size=5))"
```

> [!NOTE]
> **AI 协同模式**:
> 在我们对话时，您可以直接对我说：“帮我分析一下最近的战术日志”，我将自动在后台运行这些程序并为您汇报。

---

## 5. 核心进化验证 (Conversational Evolution Testing)

以下是验证 ADS Phase 8-10 核心功能的对话指令列表。请直接在 QQ 群或私聊中发送以下指令。

### A. 部门化报告测试 (ADS 8.1 - Scoped Reporting)
**测试目的**: 验证系统是否能根据指令范围自动节流数据流。
- **指令 1**: `报一下状态` (全局状态，应包含 MSD 摘要)
- **指令 2**: `报告战术系统状态` (应仅包含护盾、武器等战术相关指标)
- **指令 3**: `医疗部报告` (应仅包含人员生命体征监控)
- **预期现象**: Bot 返回的报告长度应根据部门（Scope）明显变化，且不再包含无关部门的冗余数据。

### B. 语义快线命中测试 (ADS 9.1 - Semantic Fast-Path)
**测试目的**: 验证系统是否跳过 AI 规划，实现“条件反射”级响应。
- **指令 1**: `扫描一下` (命中语义缓存)
- **指令 2**: `运行全舰诊断` (命中语义缓存)
- **预期现象**: 
  - 响应速度应明显快于普通对话。
  - 检查后端日志，应出现 `[Dispatcher] FAST-PATH HIT: SENSOR_SCAN_QUICK` 等字样。

### C. SOP 脱水学习测试 (ADS 9.2 - Dehydration Engine)
**测试目的**: 验证 Bot 是否能从复杂指令中提取并提议新规程。
- **指令**: `把护盾升到 50% 之后再扫描一下目标` (这是一个组合指令)
- **预期现象**: 
  - 执行指令后，打开 **LCARS Web Hub** 的“规程学习 (SOP)”面板。
  - **观察**: 是否出现了一条新的 DRAFT 规程（例如：Shields 50% -> Scan）。
  - **操作**: 在 Web 端点击 `APPROVE`，然后再次发送 `把护盾升到 50% 之后再扫描一下目标`，验证其是否已进入 Fast-Path。

### D. 实时故障墙测试 (ADS 10.1 - Real-time LCARS)
**测试目的**: 验证网页端与指令的深度联动。
- **操作**: 
  1. 同时打开 **LCARS Web Hub** 的“全舰状态”面板。
  2. 在聊天中发送：`设置曲速核心效率为 20%` (模拟故障)。
  3. **观察**: 网页端是否立即将警报级别切为 **RED ALERT**，且“实时故障流”中是否出现了对应条目。
