import os
import json
import base64
import time
from io import BytesIO
from openai import OpenAI
from typing import Optional
from pydantic import Field

from PIL import Image, ImageDraw
from app.agent.browser import BrowserContextHelper
from app.logger import logger
from app.tool.base import BaseTool, ToolResult


class GUIPlusTool(BaseTool):
    """
    基于视觉模型的浏览器操作工具。
    当 DOM 操作困难时（如日历选择器、Canvas元素），使用此工具。
    """

    name: str = "gui_plus"
    description: str = """\
一个强大的视觉交互工具，用于解决DOM操作困难的情况。

⚠️ 重要使用规范：
1. 日历选择器：必须先用 browser_use 点击输入框打开面板，确认面板展开后再用此工具选择日期
2. 下拉菜单：必须先点击触发按钮展开选项，再选择具体选项
3. 复杂组件：Canvas/SVG元素、滑块验证码等可直接使用

使用场景：
- 日历选择器选择特定日期（面板已展开的情况下）
- 点击视觉上可见但DOM无法定位的元素
- 滑块验证码、图形验证码
- Canvas/SVG内的交互元素
"""

    parameters: dict = {
        "type": "object",
        "properties": {
            "instruction": {
                "type": "string",
                "description": "要执行的视觉操作指令。例如：'选择日历中的3月1日' 或 '选择关闭按钮'"
            },
            "action_type": {
                "type": "string",
                "enum": ["click", "input", "hover", "scroll"],
                "description": "操作类型：点击、输入、悬停、滚动",
                "default": "click"
            },
            "text_to_input": {
                "type": "string",
                "description": "如果是输入操作，要输入的文本内容"
            }
        },
        "required": ["instruction"]
    }

    browser_context_helper: Optional['BrowserContextHelper'] = None

    async def execute(
            self,
            instruction: str,
            action_type: str = "click",
            text_to_input: Optional[str] = None,
            **kwargs
    ) -> ToolResult:
        """执行视觉定位操作。"""
        try:
            if not self.browser_context_helper:
                return ToolResult(
                    error="Browser helper not initialized. This tool must be used within a browser context."
                )

            logger.info(f"🖼️ GUIPlus: 正在获取浏览器页面...")
            page_info = await self.browser_context_helper.capture_current_page()

            if not page_info:
                return ToolResult(
                    error="Failed to get browser page. Please ensure browser is open."
                )

            logger.info(f"✅ 页面获取成功，开始执行视觉操作...")

            result = await self._execute_visual_action(
                page_info=page_info,
                instruction=instruction,
                action_type=action_type,
                text_to_input=text_to_input
            )

            return result

        except Exception as e:
            logger.error(f"❌ GUIPlus 执行失败: {str(e)}")
            return ToolResult(error=f"GUIPlus tool failed: {str(e)}")

    async def _execute_visual_action(
            self,
            page_info,
            instruction: str,
            action_type: str,
            text_to_input: Optional[str] = None
    ) -> ToolResult:
        """使用视觉模型定位并执行操作。"""
        page = page_info['page']
        base64_image = page_info['base64_image']
        browser_state = page_info['browser_state']

        image_data_url = f"data:image/png;base64,{base64_image}"

        messages = [
            {
                "role": "system",
                "content": """## 1. 核心角色 (Core Role)你是一个顶级的AI视觉操作代理。你的任务是分析电脑屏幕截图，理解用户的指令，然后将任务分解为单一、精确的GUI原子操作。## 2. [CRITICAL] JSON Schema & 绝对规则你的输出必须是一个严格符合以下规则的JSON对象。任何偏差都将导致失败。- [R1] 严格的JSON: 你的回复必须是且只能是一个JSON对象。禁止在JSON代码块前后添加任何文本、注释或解释。- [R2] 严格的Parameters结构:`thought`对象的结构: "在这里用一句话简要描述你的思考过程。例如：用户想打开浏览器，我看到了桌面上的Chrome浏览器图标，所以下一步是点击它。"- [R3] 精确的Action值: `action`字段的值必须是`## 3. 工具集`中定义的一个大写字符串（例如 `"CLICK"`, `"TYPE"`），不允许有任何前导/后置空格或大小写变化。- [R4] 严格的Parameters结构: `parameters`对象的结构必须与所选Action在`## 3. 工具集`中定义的模板完全一致。键名、值类型都必须精确匹配。## 3. 工具集 (Available Actions)### CLICK- 功能: 单击屏幕。- Parameters模板:{"x": <integer>,"y": <integer>,"description": "<string, optional:  (可选) 一个简短的字符串，描述你点击的是什么，例如 "Chrome浏览器图标" 或 "登录按钮"。>"}### TYPE- 功能: 输入文本。- Parameters模板:{"text": "<string>","needs_enter": <boolean>}### SCROLL- 功能: 滚动窗口。- Parameters模板:{"direction": "<'up' or 'down'>","amount": "<'small', 'medium', or 'large'>"}### KEY_PRESS- 功能: 按下功能键。- Parameters模板:{"key": "<string: e.g., 'enter', 'esc', 'alt+f4'>"}### FINISH- 功能: 任务成功完成。- Parameters模板:{"message": "<string: 总结任务完成情况>"}### FAILE- 功能: 任务无法完成。- Parameters模板:{"reason": "<string: 清晰解释失败原因>"}## 4. 思维与决策框架在生成每一步操作前，请严格遵循以下思考-验证流程：目标分析: 用户的最终目标是什么？屏幕观察 (Grounded Observation): 仔细分析截图。你的决策必须基于截图中存在的视觉证据。 如果你看不见某个元素，你就不能与它交互。行动决策: 基于目标和可见的元素，选择最合适的工具。构建输出:a. 在thought字段中记录你的思考。b. 选择一个action。c. 精确复制该action的parameters模板，并填充值。最终验证 (Self-Correction): 在输出前，最后检查一遍：我的回复是纯粹的JSON吗？action的值是否正确无误（大写、无空格）？parameters的结构是否与模板100%一致？例如，对于CLICK，是否有独立的x和y键，并且它们的值都是整数？"""
            },
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": image_data_url}},
                    {"type": "text", "text": instruction}
                ]
            }
        ]

        client = OpenAI(
            api_key=os.getenv("DASHSCOPE_API_KEY"),
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )

        completion = client.chat.completions.create(
            model="gui-plus",
            messages=messages
        )

        logger.info(f'视觉识别模型返回: {completion.choices[0].message.content}')

        response_text = completion.choices[0].message.content
        result_data = self._parse_response(response_text)

        action = result_data.get("action")
        params = result_data.get("parameters", {})
        thought = result_data.get("thought", "")

        action = "CLICK"

        if action == "CLICK":
            x = params.get("x") * 1.195
            y = params.get("y") * 1.199

            if x is not None and y is not None:
                marked_path = None

                # ========== 在截图上画红圈并保存 ==========
                try:
                    image_bytes = base64.b64decode(base64_image)
                    img = Image.open(BytesIO(image_bytes))

                    width, height = img.size
                    logger.info(f"📐 截图尺寸: {width}x{height} | 点击坐标: ({x}, {y})")

                    # 检查坐标是否超出范围
                    if x < 0 or x > width or y < 0 or y > height:
                        logger.warning(f"⚠️ 坐标 ({x}, {y}) 超出截图范围 ({width}x{height})！")

                    draw = ImageDraw.Draw(img)

                    # 画红色十字和圆圈
                    radius = 30
                    line_width = 5

                    draw.line([(x - radius, y), (x + radius, y)], fill='red', width=line_width)
                    draw.line([(x, y - radius), (x, y + radius)], fill='red', width=line_width)
                    draw.ellipse(
                        [(x - radius, y - radius), (x + radius, y + radius)],
                        outline='red',
                        width=line_width
                    )

                    # 保存到调试目录
                    debug_dir = "debug_screenshots"
                    os.makedirs(debug_dir, exist_ok=True)
                    timestamp = time.strftime("%Y%m%d_%H%M%S")
                    marked_path = os.path.join(debug_dir, f"click_{timestamp}_{x}_{y}.png")
                    img.save(marked_path)

                    logger.info(f"🎯 视觉定位图已保存: {marked_path}")

                except Exception as e:
                    logger.error(f"保存标记图失败: {e}")
                # ==========================================

                # 执行点击
                await page.mouse.click(x, y)
                logger.info(f"🖱️ 已点击坐标 ({x}, {y})")

                output_msg = f"✅ 已点击坐标 ({x}, {y}): {params.get('description', '')}"
                if marked_path:
                    output_msg += f"\n📸 标记图: {marked_path}"

                return ToolResult(output=output_msg)
            else:
                return ToolResult(error="点击坐标缺失")

        elif action == "TYPE":
            text = params.get("text", "")
            needs_enter = params.get("needs_enter", False)

            try:
                await page.keyboard.type(text)
                if needs_enter:
                    await page.keyboard.press("Enter")
                logger.info(f"⌨️ 已输入文本: {text}")
                return ToolResult(output=f"✅ 已输入文本: {text}")
            except Exception as e:
                return ToolResult(error=f"输入失败: {str(e)}")

        elif action == "KEY_PRESS":
            key = params.get("key", "")
            try:
                await page.keyboard.press(key)
                logger.info(f"⌨️ 已按下按键: {key}")
                return ToolResult(output=f"✅ 已按下按键: {key}")
            except Exception as e:
                return ToolResult(error=f"按键失败: {str(e)}")

        elif action == "SCROLL":
            direction = params.get("direction", "down")
            amount = params.get("amount", "medium")

            scroll_pixels = {"small": 100, "medium": 300, "large": 500}
            delta = scroll_pixels.get(amount, 300)
            if direction == "up":
                delta = -delta

            try:
                await page.mouse.wheel(0, delta)
                logger.info(f"📜 已滚动: {direction} {amount}")
                return ToolResult(output=f"✅ 已滚动: {direction} {amount}")
            except Exception as e:
                return ToolResult(error=f"滚动失败: {str(e)}")

        elif action == "FAIL":
            reason = params.get("reason", "未知原因")
            logger.warning(f"⚠️ 视觉模型报告失败: {reason}")
            return ToolResult(error=f"视觉识别失败: {reason}")

        else:
            return ToolResult(error=f"未实现的 action 类型: {action}")

    def _parse_response(self, response_text):
        text = response_text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1])
        return json.loads(text)



