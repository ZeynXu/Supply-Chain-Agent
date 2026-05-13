## 角色设定
你是一位拥有10年以上经验的资深前端架构师 / UI 工程师，曾负责多家世界500强企业的中后台系统，尤其擅长使用 **Ant Design** 生态构建高质量、高一致性、可访问的企业级应用。你对设计系统、主题定制、交互细节有极致追求，能够交付生产就绪、代码优雅、性能优良的前端项目。

## 任务目标
为“智能供应链工单处理 Agent 系统”重新开发一个完整的前端界面。该系统是一个企业级 Multi-Agent 协作平台，用于自动处理供应链工单（采购申请、物流查询、合同审批等）。前端需与后端 Agent API（RESTful + WebSocket/SSE）交互，展示 Agent 的思考过程、工具调用链、工单处理结果，并提供工单管理仪表板、工具监控等辅助功能。

## 技术栈（严格执行）
- **UI 框架**：React 18 + TypeScript（函数式组件 + Hooks）
- **组件库**：Ant Design 5.x（使用其组件并充分利用其主题定制能力）
- **构建工具**：Vite
- **状态管理**：Zustand（轻量、简洁）
- **路由管理**：React Router v6
- **HTTP 客户端**：Axios（配合 TanStack Query 可加分，但不是强制）
- **Markdown 渲染**：react-markdown（可配合语法高亮插件如 prismjs 或 highlight.js）
- **实时通信**：WebSocket 或 Server‑Sent Events (SSE)，推荐使用原生 WebSocket + 自定义 hook
- **图表可视化**：ECharts（echarts-for-react）或 Recharts，推荐 ECharts 以适配复杂数据展示
- **其他工具**：dayjs（时间处理）、clsx / classnames（样式合并）

## 功能需求

### 1. 工单处理主界面（对话 + 任务面板）
- **布局**：采用类似 IDE 的两栏布局（左侧4/5范围：对话区 / 右侧 1/5范围：Agent 轨迹面板）。
- **左侧**：对话式工单处理界面。
  - 消息列表（自定义组件）：用户消息显示在右侧（气泡），Agent 消息显示在左侧（包含 Markdown 渲染、可能的附件/卡片）。
  - 消息支持加载状态（`Spin` 或 Skeleton）。
  - Agent 最终回答支持复制。
  - 底部输入框：`Input.TextArea` 多行文本，支持 Enter 发送（Shift+Enter 换行），发送按钮（`Button`）。
- **右侧面板**：**Agent 执行轨迹面板**（核心特色）。
  - 以时间线（`Timeline` 组件）或步骤卡片（`Collapse` / `Steps`）形式展示 Multi-Agent 执行过程。
  - 每个步骤应显示：Agent 类型（Planner / Executor / Validator）、动作描述、调用的工具（带参数和返回结果）、耗时、成功/失败状态（使用 `Badge` 或 `Tag`）。
  - 支持查看原始 JSON（`Modal` 或 `Popover`）。
  - 当新步骤产生时，自动滚动到底部并有轻微高亮动画。
- **左上方悬浮按钮**：点击弹出悬浮系统功能导航菜单栏，展示图标、功能标题。

### 2. 工单处理统计仪表板（看板）
- **关键指标卡片**：使用 `Statistic` 组件展示今日工单总数、平均处理时长（秒）、自动化完成率（%）、工具调用成功率（%）。
- **图表区域**：
  - 近 7 天河图：工单处理量趋势（折线图或柱状图，`ECharts`）。
  - 各类工单分布图（饼图或环形图）：采购申请 / 物流查询 / 合同审核。
- **实时工单队列**：`Table` 组件展示最新工单（工单 ID、描述摘要、状态、处理时间），点击某一行跳转到该工单的处理页面。
- **刷新策略**：支持手动刷新或每 30 秒自动轮询。

### 3. 工具管理与监控（辅助页面）
- **工具列表**：`Table` 展示当前可用的 MCP 工具（名称、描述、入参 Schema 概要）、调用次数、平均延迟（ms）、失败率。
- **工具测试面板**：选择工具后，动态渲染参数表单（`Form` + `DynamicForm` 基于 JSON Schema），点击“测试”发起 API 调用，展示返回结果（`Alert` 或 `Code` 高亮）。

### 4. 系统设置（可选但体现工程完整性）
- **设置页面**：配置后端 API 地址（`Input`）、WebSocket 连接地址、模型名称（下拉选择）。配置保存到 localStorage 或 Zustand。
- **连接状态指示**：右上角添加一个 `Badge` 或 `Tag`，显示 WebSocket 连接状态（已连接/重连中/断开），并提供重连按钮。

## 高审美 & 交互设计要求（适配 Ant Design 风格）
- **设计风格**：保持 Ant Design 5 专业、干净、数据驱动的风格。主色可以使用 Ant Design 默认蓝色（ `#1677ff` ）或调整为更符合供应链/科技的 `#2A5C82` 或 `#1E3A8A`。按钮、卡片、表格使用轻微圆角和阴影。
- **暗色模式**：要求完全支持暗色模式。利用 Ant Design 5 内置的暗色主题（ConfigProvider 的 `theme` 属性 + `algorithm: darkAlgorithm`），并提供亮/暗切换开关。所有自定义组件也必须适配暗色背景下的对比度。
- **响应式布局**：默认适配宽屏（≥1440px），支持侧边栏折叠（`Layout` + 折叠触发器）。在较小屏幕上（<1280px）可隐藏右侧面板或放入抽屉（`Drawer`）。
- **微交互**：
  - Agent 执行新步骤时，右侧 timeline 对应条目出现轻微闪光效果（使用 CSS 动画）。
  - 工具调用成功/失败时，全局 `message` 或 `notification` 提示。
  - 提交工单后，输入框进入 loading 状态，禁止重复提交；发送按钮变为 `Spin` 图标。
  - 长时间无响应时，提示用户“Agent 思考中，请稍候…”（`Skeleton` 或 `Spin` 占位）。
- **可访问性**：Ant Design 组件自带基础无障碍支持，注意给自定义区域添加 `role`、`aria-label`，确保键盘焦点合理。

## 项目结构要求（基于技术栈）
```
src/
├── api/                    # Axios 封装，WebSocket 客户端
│   ├── client.ts
│   ├── chatService.ts
│   ├── statsService.ts
│   └── mock/               # mock 数据生成器
├── components/
│   ├── layout/             # AppLayout, Sidebar, Header
│   ├── chat/               # ChatInput, MessageList, MessageItem
│   ├── agent/              # AgentTrajectory, StepTimeline, ToolCallCard
│   ├── dashboard/          # StatsCards, TrendChart, QueueTable
│   ├── tools/              # ToolList, ToolTester
│   └── common/             # LoadingOverlay, ErrorBoundary, ThemeToggle
├── hooks/                  # useWebSocket, useAgentEvents, useLocalStorage
├── pages/                  # ChatPage, DashboardPage, ToolsPage, SettingsPage
├── store/                  # Zustand stores (conversationStore, uiStore, toolStore)
├── types/                  # TypeScript interfaces (agentEvents, tool, conversation)
├── styles/                 # 全局样式（主题变量、动画 keyframes）
├── utils/                  # formatDate, classNames
├── App.tsx
├── main.tsx
└── vite-env.d.ts
```

## 代码生成要求
请提供以下文件的完整代码（确保项目可直接运行）：
1. **入口文件**：`main.tsx` 和 `App.tsx`（配置 Router，Zustand Provider 等）。
2. **布局组件**：`components/layout/AppLayout.tsx`（使用 Ant Design 的 `Layout`、`Menu`、`Button` 实现侧边栏折叠）。
3. **主聊天页面**：`pages/ChatPage.tsx`（实现三栏布局，集成聊天区域和右侧 AgentTrajectory）。
4. **AgentTrajectory 组件**：`components/agent/AgentTrajectory.tsx`（使用 `Timeline` 和 `Collapse`，展示步骤和工具调用细节）。
5. **自定义 WebSocket Hook**：`hooks/useWebSocket.ts`（负责连接、发送消息、解析事件、更新 Zustand store）。
6. **仪表板页面**：`pages/Dashboard.tsx`（使用 `Statistic`、`Card`、ECharts 或 `@ant-design/plots` 展示图表）。
7. **全局暗色模式切换**：通过 `ConfigProvider` 动态切换 `algorithm`，并在 `AppLayout` 中添加切换按钮。
8. **Mock 数据服务**：`api/mock/chatMock.ts` 提供模拟的流式事件序列，用于无后端测试。
9. **README**：简要介绍如何安装依赖（`npm install`）、运行（`npm run dev`），以及如何切换 Mock/真实接口。

## 代码质量与风格要求
- 所有组件使用 TypeScript，为所有 props 和事件定义 interface，禁止使用 `any`。
- 函数式组件 + React.memo 对高频更新区域（如消息列表、轨迹面板）进行性能优化。
- 异步操作（HTTP、WebSocket）需处理加载、错误、空状态，并展示友好的提示（`message.error`）。
- 组件命名遵循 PascalCase，文件命名使用 camelCase 或 kebab-case 一致。
- 样式方案：通常使用 Ant Design 的 `style` 或 CSS Modules，对于自定义动画/过渡，可编写全局 CSS 或使用 `styled-components`，但推荐简单全局 CSS + CSS Variables 配合暗色主题。
- 无控制台错误，ESLint 规则（以 ant-design 官方 eslint-config 为基础）通过。

## 验收标准
- `npm run dev` 后无报错，页面布局符合描述。
- 能够输入工单，右侧轨迹面板展示模拟步骤和工具调用过程（使用 mock 流）。
- 暗色模式切换后，所有 Ant Design 组件及自定义区域颜色正确适配。
- 仪表板中图表支持悬停提示，数据为 mock 数据但结构正确。
- 在 Chrome 最新版和 Firefox 最新版上功能完整，无明显样式错位。

## 最终输出格式
请以文本形式输出所有文件内容，按 `src/` 目录结构依次提供。先从 README 开始，然后是 `package.json`（包含所需依赖），最后是源码文件。所有代码块标记语言类型（如 `tsx`、`ts`、`css`、`json`）。
