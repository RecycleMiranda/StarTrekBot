import asyncio
import os
import sys
from services.bot.app.repair_agent import get_repair_agent

async def test_subspace_bypass():
    print("--- 🔬 启动子空间旁路热修复验证 ---")
    ra = get_repair_agent()
    
    # 模拟一个逻辑组件故障数据
    module = "tools.py"
    fault = "ValueError: math domain error in tactical sonar calculation"
    
    print(f"正在尝试为 {module} 生成外科手术式补丁...")
    
    # 我们直接调用核心 Autopilot 引擎
    res = await ra.async_autopilot_repair(module, fault)
    
    if res.get("ok"):
        print(f"✅ 成功！旁路补丁已应用至 {module}。")
        print(f"ADS 消息: {res.get('message')}")
        
        # 验证文件内容是否包含标签
        from services.bot.app import repair_tools
        read_res = repair_tools.read_module(module, force=True)
        content = read_res.get("content", "")
        
        if "<<< SUBSPACE BYPASS START >>>" in content:
            print("🔍 验证通过：源码中已发现 SUBSPACE BYPASS 标识。")
            # 打印补丁片段
            import re
            match = re.search(r"# <<< SUBSPACE BYPASS START >>>.*?# <<< SUBSPACE BYPASS END >>>", content, re.DOTALL)
            if match:
                print("\n生成的补丁预览:")
                print("-" * 20)
                print(match.group(0))
                print("-" * 20)
        else:
            print("❌ 错误：补丁应用成功但未发现标识标签。")
    else:
        print(f"❌ 失败：热修复程序未能成功执行。原因: {res.get('message')}")

if __name__ == "__main__":
    # 确保设置了 PYTHONPATH 以导入 local modules
    sys.path.append(os.path.join(os.getcwd()))
    asyncio.run(test_subspace_bypass())
