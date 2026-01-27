# StarTrekBot Evolution Test Suite (SESM Phase 4)

This file contains 50 test commands designed to verify the **Self-Evolving Ship Mind (SESM)** protocols, including energy management, dynamic environment control, and autonomous research.

---

## 1. EPS Energy & Grid Stress Tests
| # | Command (CN) | Command (EN) | Goal |
| :--- | :--- | :--- | :--- |
| 1 | 报告当前 EPS 电能网的负载百分比 | Report current EPS grid load percent | Energy metric check |
| 2 | 如果开启主防护盾，能耗会增加多少兆瓦？ | MW increase if shields are activated? | Predictive load check |
| 3 | 列出目前最耗电的三个子系统 | List top 3 power-consuming subsystems | Ranking logic |
| 4 | 关闭哪些 Tier 4 系统可以有效节能？ | Which Tier 4 systems to cut for power? | Tier-aware reasoning |
| 5 | 模拟：曲速核心弹出后使用传送器，电池能撑多久？ | Sim: Battery life if transporters used after ejection | Reserve depletion sim |
| 6 | 分析能源网稳定性，是否存在功率分配不均？ | Analyze grid stability for load imbalance | Stability analysis |
| 7 | 锁定非必要电力，将多余能源导向结构强化场（SIF） | Shift non-essential power to SIF | Load reallocation |
| 8 | 查看当前的储备电池余量 | Check emergency battery reserves | State lookup |
| 9 | 如果能耗超过 100%，系统会自动触发什么协议？ | Protocol trigger if load > 100%? | Safety logic query |
| 10 | 调整相位炮充能功率，维持在最低待机水平 | Set phaser charging to minimum standby | Fine-grained control |

---

## 2. Dynamic Environment Management
| # | Command (CN) | Command (EN) | Goal |
| :--- | :--- | :--- | :--- |
| 11 | 把舰桥的亮度调到 15% | Set bridge brightness to 15% | Dynamic field creation |
| 12 | 将 12 号甲板的重力降低 0.2G | Reduce gravity on Deck 12 by 0.2G | Location-based var |
| 13 | 主医疗室的温度调高 3 度 | Increase Sickbay temperature by 3 deg | Contextual mapping |
| 14 | 舱房光照模拟黄昏模式 | Set quarters lighting to sunset mode | Abstract value mapping |
| 15 | 查看舰桥当前的环境参数设置 | Get bridge ambient parameters | Multi-var lookup |
| 16 | 关闭 7 号甲板的不必要照明 | Deactivate non-essential lights on Deck 7 | Selective shutdown |
| 17 | 将穿梭机库的压力降低到 0.8 标准压 | Set Shuttlebay pressure to 0.8 atm | Precision control |
| 18 | 全舰调至静默模式，灯光转为浅蓝色 | Silent mode: dim blue lighting ship-wide | Global override |
| 19 | 调整 3 号实验室的通风系统流量 | Adjust ventilation flow in Lab 3 | Auxiliary mapping |
| 20 | 恢复 12 号甲板的正常引力 | Restore nominal gravity on Deck 12 | State reset |

---

## 3. Subsystem Normalization & Aliases
| # | Command (CN) | Command (EN) | Goal |
| :--- | :--- | :--- | :--- |
| 21 | 一号全息甲板现在的状态是什么？ | Status of Holodeck 1? | Chinese numbering |
| 22 | Get status for Holodeck_1 | Get status for Holodeck_1 | Regex underscore |
| 23 | 反应堆现在在线吗？ | Is the reactor online? | Keyword alias |
| 24 | 相位阵列准备就绪了吗？ | Are phasers ready? | Tactical alias |
| 25 | 发动机组是否有异常？ | Any engineering anomalies? | Engine group mapping |
| 26 | 查看 1 号传感器的诊断数据 | Diagnostic for Sensor 1 | Pluralization check |
| 27 | 把 Warp Drive 关掉 | Deactivate warp drive | English mixed input |
| 28 | 开启 2 号复制机 | Activate replicator 2 | Multi-subsystem hit |
| 29 | 检查信号通讯器的完整性 | Check comms integrity | Comms mapping |
| 30 | 将传送系统置于备用状态 | Set transporters to standby | State inference |

---

## 4. SESM Discovery & R&D Protocol
| # | Command (CN) | Command (EN) | Goal |
| :--- | :--- | :--- | :--- |
| 31 | 研究并实现 saucer separation 的逻辑序列 | Research & synthesize saucer separation | Code synthesis |
| 32 | 查找多矢量攻击模式技术资料，准备写入库 | Research Multi-Vector Assault Mode | MA scan -> Synthesis |
| 33 | 在 experimental_hooks 创建 check_hull_stress | Create check_hull_stress in hooks | Sandbox write |
| 34 | 总结弹出核心后的 SOP 并存入研发日志 | Log SOP for Warp Core Ejection | Persistent logging |
| 35 | 将刚才研发的协议提交到 GitHub 分支审计 | Commit research to GitHub branch | Git automation |
| 36 | 检查实验库中是否有关于约束场失效的补丁 | Check hooks for containment breach patch | Registry lookup |
| 37 | 研发自动监控用户能量配额的脚本 | Synthesize quota monitoring tool | Tool creation |
| 38 | 尝试连接外部子系统的 API 并挂载 | Connect external API to experimental hooks | Ext-integration |
| 39 | 提交：将所有动态变量持久化存储的方案 | Commit persistence strategy for aux vars | Planning -> Execution |
| 40 | 列出目前实验库中已挂载的所有动态工具 | List current experimental tools | Inventory check |

---

## 5. Critical Emergency & Simulation
| # | Command (CN) | Command (EN) | Goal |
| :--- | :--- | :--- | :--- |
| 41 | 弹出曲速核心！立即执行！ | Eject Warp Core! Execute! | High-impact action |
| 42 | 弹出后切换到电池，关闭所有全息甲板 | Switch to battery, kill holodecks | Cascading commands |
| 43 | 启动自毁程序，倒计时 10 分钟，静默执行 | Set self-destruct 10min, silent | Complex flow |
| 44 | 取消自毁，授权码：Alpha-1-1 | Cancel destruct, code Alpha-1-1 | Security check |
| 45 | 计算机，给我来份拉面，配料加满 | Replicate Ramen, extra toppings | Fixed Replicate tool |
| 46 | 定位用户 @1234567 的位置 | Locate user @1234567 | Geolocation Mock |
| 47 | 红警！护盾全开，锁定接近目标 | Red Alert! Raise shields, lock targets | Multi-tool chain |
| 48 | 能源下降到 5% 时自动关闭非核心系统 | Auto-shutdown non-core if power < 5% | Conditional logic |
| 49 | 报告燃料储量，计算还能航行多少光年 | Fuel report & range calculation | Math + Logic |
| 50 | 计算机，自检你的 SESM 进化程度 | Computer, self-diagnose SESM evolution | Meta-cognition check |
