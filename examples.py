"""
ZeroToken 使用示例 - 演示 AI Agent 浏览器自动化流程

展示：
1. MCP 工具调用
2. 轨迹记录
3. 脚本生成
4. 混合执行（含 AI 节点）
"""

import asyncio
import json
from zerotoken import (
    BrowserController,
    TrajectoryRecorder,
    ScriptGenerator,
    HybridEngine,
    AINodeContext
)


async def example_basic_recording():
    """示例 1: 基础轨迹记录"""
    print("\n" + "=" * 60)
    print("示例 1: 基础轨迹记录")
    print("=" * 60)

    controller = BrowserController()
    recorder = TrajectoryRecorder()
    recorder.bind_controller(controller)

    try:
        # 初始化浏览器
        await controller.start(headless=True)
        print("浏览器已启动")

        # 开始轨迹记录
        recorder.start_trajectory("demo_login", "演示登录流程")
        print("轨迹记录已开始")

        # 执行一系列操作
        record = await controller.open("https://example.com")
        print(f"打开页面：{record.result}")

        record = await controller.get_text("h1")
        print(f"提取文本：{record.result}")

        record = await controller.screenshot()
        print(f"截图：{record.result.get('success')}")

        # 完成轨迹
        trajectory = recorder.complete_trajectory()
        print(f"轨迹完成，共 {len(trajectory.operations)} 步操作")

        # 保存轨迹
        filepath = recorder.save_trajectory()
        print(f"轨迹已保存到：{filepath}")

        # 导出 AI 提示
        ai_prompt = recorder.export_for_ai("demo_login")
        print(f"AI 提示已生成 ({len(ai_prompt)} 字符)")

    finally:
        await controller.stop()


async def example_script_generation():
    """示例 2: 从轨迹生成脚本"""
    print("\n" + "=" * 60)
    print("示例 2: 从轨迹生成脚本")
    print("=" * 60)

    generator = ScriptGenerator()

    # 列出可用轨迹
    recorder = TrajectoryRecorder()
    trajectories = recorder.list_trajectories()

    if trajectories:
        task_id = trajectories[0]["task_id"]
        print(f"使用轨迹：{task_id}")

        # 生成脚本（规则基础）
        script = generator.generate_script(task_id)
        print(f"生成的脚本：{json.dumps(script, indent=2, ensure_ascii=False)}")

        # 保存脚本
        filepath = generator.save_script(script, f"{task_id}_script")
        print(f"脚本已保存到：{filepath}")
    else:
        print("没有找到轨迹，请先运行示例 1")


async def example_hybrid_execution():
    """示例 3: 混合引擎执行"""
    print("\n" + "=" * 60)
    print("示例 3: 混合引擎执行（含 AI 节点）")
    print("=" * 60)

    # 创建示例脚本（包含 AI 节点）
    script = {
        "name": "ai_demo_script",
        "goal": "演示 AI 节点执行",
        "parameters": ["search_query"],
        "steps": [
            {
                "action": "open",
                "params": {"url": "https://example.com"}
            },
            {
                "action": "wait",
                "params": {"seconds": 1}
            },
            {
                "action": "extract_data",
                "ai_node": True,
                "ai_prompt": "分析页面内容，提取主要标题",
                "params": {
                    "schema": {
                        "fields": [
                            {"name": "title", "selector": "h1", "type": "text"}
                        ]
                    }
                }
            }
        ]
    }

    # 设置 AI 处理器
    async def dummy_ai_handler(ctx: AINodeContext) -> dict:
        """模拟 AI 处理器（实际使用时调用 LLM API）"""
        print(f"\n[AI 节点] 收到请求：{ctx.action}")
        print(f"页面状态：{ctx.page_state}")
        print(f"AI 提示：{ctx.ai_prompt}")

        # 模拟 AI 决策
        return {
            "action": "extract_data",
            "params": ctx.params,
            "confidence": 0.95,
            "reasoning": "Use the extract_data method as defined in the script"
        }

    # 执行引擎
    engine = HybridEngine()
    engine.set_ai_handler(dummy_ai_handler)
    engine.set_variables(search_query="test")

    result = await engine.execute(script)
    print(f"\n执行结果：{json.dumps(result, indent=2, ensure_ascii=False)}")


async def example_mcp_workflow():
    """示例 4: 模拟完整 MCP 工作流"""
    print("\n" + "=" * 60)
    print("示例 4: 模拟完整 MCP 工作流")
    print("=" * 60)

    controller = BrowserController()
    recorder = TrajectoryRecorder()
    recorder.bind_controller(controller)
    generator = ScriptGenerator()

    await controller.start(headless=True)

    try:
        # 步骤 1: 开始记录
        print("\n[步骤 1] 开始轨迹记录")
        recorder.start_trajectory("mcp_workflow", "MCP 工作流演示")

        # 步骤 2: 执行操作
        print("\n[步骤 2] 执行浏览器操作")
        await controller.open("https://example.com")
        print("  - 已打开页面")

        await controller.wait_for("selector", "h1")
        print("  - 已等待元素加载")

        record = await controller.get_text("h1")
        print(f"  - 已提取文本：{record.result.get('value', '')}")

        # 步骤 3: 完成记录
        print("\n[步骤 3] 完成轨迹记录")
        trajectory = recorder.complete_trajectory()
        recorder.save_trajectory()

        # 步骤 4: 生成脚本
        print("\n[步骤 4] 生成脚本")
        script = generator.generate_script("mcp_workflow")
        generator.save_script(script, "mcp_workflow_script")
        print(f"  - 脚本步骤数：{len(script['steps'])}")

        # 步骤 5: 回放脚本
        print("\n[步骤 5] 执行脚本回放")
        engine = HybridEngine()
        result = await engine.execute(script)
        print(f"  - 执行结果：{'成功' if result.get('success') else '失败'}")

    finally:
        await controller.stop()


async def main():
    """运行所有示例"""
    print("\n" + "=" * 60)
    print("ZeroToken 使用示例")
    print("=" * 60)

    # 运行示例
    await example_basic_recording()
    await example_script_generation()
    await example_hybrid_execution()
    await example_mcp_workflow()

    print("\n" + "=" * 60)
    print("所有示例运行完成！")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
