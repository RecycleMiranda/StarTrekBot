def get_lexicon_prompt() -> str:
    """Returns the comprehensive LCARS/Cardassian technical lexicon extracted from TNG and DS9 manuals."""
    return """
TECHNICAL LEXICON (MANDATORY TRANSLATIONS):

[Ship & Station Structures]
- Main Skeletal Structure -> 主龙骨结构 / 主骨架结构
- Saucer Module -> 碟部 / 碟体
- Stardrive Section / Battle Section -> 轮机舰体 / 作战部
- Docking Tower -> 对接塔
- Docking Ring -> 对接环
- Airlock -> 气闸
- Security Gate -> 安保防护通道
- Tritanium -> 三钛
- Duranium -> 硬铀
- Toranium -> Toranium
- Kelindide -> Kelindide
- Rodinium -> Rodinium
- Gamma-welded -> 伽马焊接
- Structural Integrity Field (SIF) -> 结构完整性力场
- Inertial Damping Field (IDF) -> 惯性阻尼系统/场
- Ablative armor -> 烧蚀装甲
- Pressure door -> 承压门
- Anti-gravity conduit -> 反重力导管

[Propulsion Systems]
- Continuum Distortion Propulsion (CDP) -> 连续体扭曲推进 (曲速驱动正式名称)
- Warp Drive -> 曲速驱动 / 曲速引擎
- Matter/Antimatter Reaction Assembly (M/ARA) -> 物质/反物质反应装置 (曲速核心)
- Dilithium Crystal -> 二锂晶体
- Warp Field Coil -> 曲速场线圈
- Bussard Ramscoop -> 巴萨德冲压采集器
- Electro Plasma System (EPS) -> 等离子电力系统
- Impulse Propulsion System (IPS) -> 脉冲推进系统
- Artificial singularity drive -> 人工奇点驱动 (罗慕伦技术)
- Cochrane -> 科克伦 (子空间畸变单位)
- Verterion membrane -> verteron 膜
- Verteron condensation nodes -> verteron 凝聚节点

[Computer & Command Systems]
- LCARS -> 计算机数据库访问与读取系统
- Operations Center (Ops) -> 运作中心
- Main Bridge -> 主舰桥
- Computer Core -> 计算机核心
- Optical Data Network (ODN) -> 光学数据网络
- Isolinear Optical Chip -> 等线性光学芯片
- Isolinear rod -> 等线性数据棒 (卡达西存储介质)
- Quad -> 夸 (Kiloquad -> 千夸 / Gigaquad -> 吉夸)
- PADD -> 个人访问显示设备
- Communications Processing Group (CPG) -> CPG (协调处理器与外设组)
- Level 4 Isolinear Rod -> 4级数据棒 (核心级存储)

[Energy & Utilities]
- Fusion Reactor -> 聚变反应堆
- Fusion fuel pellet -> 聚变靶丸
- Industrial replicator -> 工业复制机
- Matter Stream -> 物质流
- Plasma power grid -> 等离子电网
- Subspace transceiver -> 子空间收发器
- Nutritional matrix -> 营养物矩阵

[Transporter Systems]
- Transporter -> 传送机 / 传送系统
- Annular Confinement Beam (ACB) -> 环形约束波束
- Pattern Buffer -> 模式缓冲器
- Phase Transition Coils -> 相转换线圈
- Heisenberg Compensator -> 海森堡补偿器
- Bio-filter -> 生物过滤器
- Emitter Array -> 发射极阵列

[Science & Sensors]
- Tricorder -> 三录仪
- TR-950 Type X Tricorder -> TR-950 X型三录仪
- Lateral Sensor Array -> 侧向传感器阵列
- Navigational Deflector -> 航行偏导仪
- Orb artifacts -> 神球 (贝久圣物)
- Subspace scanning speed -> 子空间扫描速度

[Tactical Systems]
- Phaser -> 相位炮 / 相位器
- Photon Torpedo -> 光子鱼雷
- Quantum Torpedo -> 量子鱼雷
- Spiral-wave disruptor -> 螺旋波裂解炮 (卡达西武器)
- Polaron weapon -> 极化子武器 (自治领武器)
- Defensive shield -> 防御护盾
- Shield generator -> 护盾发生器
- Self-replicating mine -> 自复制空雷

[Environmental & Crew Support]
- Life Support -> 生命保障
- Gravity Generator -> 重力发生器
- Gravity blanket -> 重力发生毯 (卡达西技术)
- Hypospray -> 无针喷雾注射器
- Bio-bed -> 生物床
- Holographic Environment Simulator -> 全息环境模拟器 (全息甲板)

[Auxiliary Spacecraft & Threat Forces]
- Shuttlecraft -> 穿梭机
- Danube-class Runabout -> 多瑙河级汽艇
- Galaxy-class -> 银河级
- Sovereign-class -> 元首级
- Defiant-class -> 挑战级
- Galor-Class Attack Cruiser -> 加洛级攻击巡洋舰
- Jem'Hadar Attack Ship -> 詹哈达攻击舰
- D'Deridex-Class Warbird -> 戴克森级战鸟
- Workbee -> 工蜂 (作业作业车)
"""
