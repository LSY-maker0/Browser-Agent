# Browser Agent

<div align="center">
  <h3>通用浏览器自动化智能体 (基于 OpenManus 架构)</h3>
  <p>一个基于 OpenManus 架构的自主浏览器 Agent，专为解决传统 RPA 无法处理的动态网页交互与复杂推理任务而设计</p>
</div>

## 项目简介

Browser Agent 是一个通用浏览器自动化智能体，旨在解决传统 RPA 无法处理的动态网页交互与复杂推理任务（如跨平台比价、竞品分析）。

核心作用是实现一个自主规划的超级智能体，具备强大的网页操作能力和智能化决策能力。

## 📈 项目演示


### 🔧 技术栈
- **语言**: Python
- **框架**: LangGraph, Playwright
- **模型**: Qwen-GUI-Plus
- **容器**: Docker
- **协议**: MCP Protocol

## 🏗️ 架构设计

### Agent 分层代理架构
- **BaseAgent**: 所有代理的基础，定义了代理状态管理和执行循环的核心逻辑
- **ReActAgent**: 实现了 ReAct 模式，Think-Act-Observe 循环
- **ToolCallAgent**: 在 ReActAgent 基础上增加工具调用能力
- **Manus**: OpenManus 的核心智能体实例，集成了各种工具和能力

### 与普通 ReAct 的区别
我的设计是对 ReAct 范式的结构化升级：
- **基础层**: 在具体的工具调用阶段，依然采用了 Think-Act-Observe 的 ReAct 循环，保证了每一步操作的精准性
- **架构层**: 为了避免 ReAct 在长链路任务中容易迷失和发散的问题，引入了 Planner-Executor-Reviewer 的分层架构
  - Planner 负责任务的宏观拆解，提供全局视野
  - Executor 负责执行具体步骤
  - Reviewer 引入了"反思机制"，负责检查结果并修正偏差

## 🛠️ MCP 协议支持

### MCP 与工具系统的集成
- 通过 MCPClients 类（继承自 ToolCollection）将 MCP 服务集成到现有工具系统中
- 动态创建 MCPClientTool 实例作为每个工具的代理
- 通过远程请求执行工具，实现了本地与远程工具的统一代理

### 动态工具代理
每当连接到 MCP 服务器时，系统会动态创建 MCPClientTool 实例作为每个工具的代理，通过向 MCP 发送远程请求来执行工具，实现了工具的热插拔。

## 🔐 安全机制

### Python 代码执行沙箱
- PythonExcute 工具实现了安全的 Python 代码执行环境
- 在执行 Python 代码时启动单独进程，使用独立进程执行代码
- 设置超时时间防止无限循环，能够捕获进程中的输出内容


