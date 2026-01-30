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
