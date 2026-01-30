# 星舰状态报告系统与核心架构逻辑说明

本文档详细介绍了星舰（StarTrekBot）的状态生成机制、底层组件管理以及自动诊断系统（ADS）的运行逻辑。

## 1. 核心系统框架 (`ship_systems.py`)
`ShipSystems` 是全舰状态的单一事实来源（Single Source of Truth），负责管理所有硬件与子系统的实时状态。

### A. MSD 注册表与组件映射
- **注册表 (Registry)**: 使用 JSON 树状结构定义全舰子系统（如：曲速核心、护盾、相位炮）。
- **递归构建**: 系统启动时会递归扫描注册表，构建一个扁平化的 `component_map`，支持通过名称或别名（Alias）快速检索组件。

### B. 递归效率算法 (Recursive Efficiency)
系统采用 **级联瓶颈模型** 计算子系统的运行效率：
- **公式**: `系统效率 = 基础健康值 * min(所有依赖项的效率)`。
- **逻辑**: 如果曲速核心（Warp Core）输出下降，与之关联的护盾和武器输出会自动受到联动限制。

### C. 告警等级 (Alert Levels)
- **NORMAL (Condition Green)**: 系统处于常规巡航状态。
- **YELLOW ALERT**: 护盾自动上线，全舰进入警戒模式。
- **RED ALERT**: 武器站就绪，护盾增强，所有非必要能源分配至战术系统。

## 2. 状态摘要生成器 (`tools.py: get_status`)
这是一个高层的聚合工具，通过调用多个子系统获取全舰综述：
- **资源监控**: 使用 `psutil` 获取容器/系统的 CPU 和内存使用率。
- **MSD 快照**: 提取注册表中所有关键组件的 `state`（状态）和 `metrics`（指标）。
- **情报整合**: 动态调用 `LogAnalyzer` 获取最近的战术接触摘要。
- **自适应摘要**: 将上述数据压缩为一条易于阅读的系统简报。

## 3. 自动诊断程序 (ADS - `diagnostic_manager.py`)
ADS 是星舰的“免疫系统”，负责故障的自动监测和修复建议。

### A. 故障汇报逻辑 (Fault Reporting)
- 当 `dispatcher.py` 捕获到执行错误时，会触发 `report_fault`。
- 每一个故障都会被分配一个 `ERR-0x...` 格式的唯一十六进制 ID。

### B. AI 诊断循环
- **病理分析**: ADS 异步将错误堆栈、用户指令和组件背景发送给 Gemini 引擎。
- **修复方案**: 系统自动生成 `diff` 格式的建议修复代码，并将其记录在 `DIAGNOSTIC_REPORT.md` 中。

### C. 自动旁路 (Auto-Healing)
- 对于已知类型的软件故障（如：语法错误、属性错误），系统尝试通过 `RepairAgent` 自动应用代码旁路。
- 所有的旁路操作都会记录在 `BYPASS_REGISTRY.md` 中，并同步至 GitHub logs 分支。

---

> [!TIP]
> **交互指令**:
> - “报告系统状态” -> 触发 `get_status` 全局扫描。
> - “检查 [子系统] 状态” -> 触发 `get_subsystem_status` 并计算递归效率。
