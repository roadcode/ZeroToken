"""
稳定性增强使用示例

演示如何使用 ZeroToken 的稳定性模块提高浏览器自动化可靠性。
"""

import asyncio
from zerotoken import (
    BrowserController,
    SmartSelectorGenerator,
    SmartWait,
    WaitCondition,
    ErrorRecovery,
    RetryWrapper,
    WaitChain
)


async def example_smart_selector():
    """示例 1: 智能选择器生成"""
    print("\n" + "=" * 60)
    print("示例 1: 智能选择器生成")
    print("=" * 60)

    controller = BrowserController()
    await controller.start(headless=True)

    try:
        # 打开页面
        await controller.open("https://example.com")

        # 生成智能选择器
        selector_generator = SmartSelectorGenerator()

        # 获取元素
        element = await controller.page.wait_for_selector("h1")

        # 生成智能选择器
        smart_selector = await selector_generator.generate(element)

        print(f"\n元素信息:")
        print(f"  标签：{smart_selector.element_info.get('tag')}")
        print(f"  文本：{smart_selector.element_info.get('text')}")

        print(f"\n首选选择器:")
        print(f"  类型：{smart_selector.primary.type.value}")
        print(f"  值：{smart_selector.primary.value}")
        print(f"  稳定性评分：{smart_selector.primary.stability_score}")

        print(f"\n备选选择器:")
        for alt in smart_selector.all_selectors()[1:6]:
            print(f"  - [{alt.stability_score:.2f}] {alt.type.value}: {alt.value}")

    finally:
        await controller.stop()


async def example_wait_strategies():
    """示例 2: 智能等待策略"""
    print("\n" + "=" * 60)
    print("示例 2: 智能等待策略")
    print("=" * 60)

    controller = BrowserController()
    await controller.start(headless=True)

    try:
        await controller.open("https://example.com")

        # 创建智能等待对象
        smart_wait = SmartWait(controller.page)

        # 等待元素可见
        print("\n等待元素可见...")
        result = await smart_wait.wait_for(
            WaitCondition.VISIBLE,
            "h1",
            description="等待标题显示"
        )
        print(f"  结果：{'成功' if result.success else '失败'}")
        print(f"  耗时：{result.elapsed_ms:.0f}ms")

        # 等待网络空闲
        print("\n等待网络空闲...")
        result = await smart_wait.wait_for(
            WaitCondition.NETWORK_IDLE,
            timeout=5000
        )
        print(f"  结果：{'成功' if result.success else '超时 (可接受)'}")

        # 级联等待
        print("\n级联等待...")
        wait_chain = WaitChain(controller.page)
        result = await (
            wait_chain
            .wait_for_selector("h1")
            .wait_for_visible()
            .wait_for_network_idle()
            .execute()
        )
        print(f"  总体结果：{'成功' if result['success'] else '失败'}")
        print(f"  总耗时：{result['total_elapsed_ms']:.0f}ms")

    finally:
        await controller.stop()


async def example_error_recovery():
    """示例 3: 错误恢复"""
    print("\n" + "=" * 60)
    print("示例 3: 错误恢复机制")
    print("=" * 60)

    controller = BrowserController()
    await controller.start(headless=True)

    try:
        await controller.open("https://example.com")

        # 创建错误恢复对象
        recovery = ErrorRecovery(controller.page, controller)

        # 模拟一个错误
        print("\n模拟选择器未找到错误...")
        try:
            await controller.page.click("#nonexistent-element-xyz123")
        except Exception as e:
            print(f"  原始错误：{str(e)[:50]}...")

            # 尝试恢复
            result = await recovery.handle_error(
                e,
                selector="#nonexistent-element-xyz123",
                action="click"
            )

            print(f"  恢复结果:")
            print(f"    成功：{result.success}")
            print(f"    已恢复：{result.recovered}")
            print(f"    操作：{result.action_taken}")

        # 测试重试包装器
        print("\n重试包装器测试...")
        retry_wrapper = RetryWrapper(max_retries=3, base_delay=0.5)

        attempt_count = 0

        async def flaky_function():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 3:
                raise Exception(f"临时错误 {attempt_count}")
            return "成功"

        try:
            result = await retry_wrapper.execute(
                flaky_function,
                description="测试不稳定函数"
            )
            print(f"  最终结果：{result}")
            print(f"  尝试次数：{attempt_count}")
        except Exception as e:
            print(f"  重试失败：{e}")

    finally:
        await controller.stop()


async def example_stable_workflow():
    """示例 4: 稳定性增强的工作流程"""
    print("\n" + "=" * 60)
    print("示例 4: 稳定性增强的工作流程")
    print("=" * 60)

    controller = BrowserController()
    await controller.start(headless=True)

    try:
        # 配置稳定性选项
        controller.set_config(
            enable_stability=True,
            max_retries=3,
            retry_delay=1.0,
            timeout=30000
        )

        print("\n执行稳定性增强的操作流程...")

        # 打开页面（带自动重试）
        record = await controller.open("https://example.com")
        print(f"1. 打开页面：{'成功' if record.result.get('success') else '失败'}")

        # 等待并提取文本（带智能等待）
        record = await controller.get_text("h1")
        print(f"2. 提取文本：{'成功' if record.result.get('success') else '失败'}")
        if record.result.get('value'):
            print(f"   文本内容：{record.result.get('value')}")

        # 截图
        record = await controller.screenshot()
        print(f"3. 截图：{'成功' if record.result.get('success') else '失败'}")

        # 查看稳定性历史
        if controller._error_recovery:
            history = controller._error_recovery.get_recovery_history()
            print(f"\n错误恢复历史：{len(history)} 条记录")

        if controller._smart_wait:
            wait_history = controller._smart_wait.get_wait_history()
            print(f"等待历史：{len(wait_history)} 条记录")

    finally:
        await controller.stop()


async def main():
    """运行所有示例"""
    print("\n" + "=" * 60)
    print("ZeroToken 稳定性增强示例")
    print("=" * 60)

    # 运行示例
    await example_smart_selector()
    await example_wait_strategies()
    await example_error_recovery()
    await example_stable_workflow()

    print("\n" + "=" * 60)
    print("所有示例运行完成！")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
