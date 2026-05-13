# 智能供应链Agent系统 - 前端

基于 React 18 + TypeScript + Ant Design 5 + ECharts 构建的企业级前端界面。

## 技术栈

- **React 18** - 现代化UI框架
- **TypeScript 5** - 类型安全开发
- **Vite 5** - 快速构建工具
- **Ant Design 5** - 企业级UI组件库
- **ECharts** - 数据可视化图表
- **Zustand** - 轻量级状态管理
- **React Markdown** - Markdown渲染
- **dayjs** - 时间处理库

## 核心功能

### 1. 智能对话界面
- 类似IDE的两栏布局（左侧对话区 + 右侧Agent轨迹面板）
- 实时展示Multi-Agent协作过程
- 支持工具调用详情查看
- 暗色模式支持

### 2. 工单处理统计仪表板
- 关键指标卡片（工单数、处理时长、自动化率、成功率）
- 近7天趋势图（折线图）
- 工单类型分布（饼图）
- 实时工单队列（表格）
- 30秒自动轮询刷新

### 3. 工具管理
- MCP工具列表展示
- 工具健康度监控
- 工具参数动态表单
- 工具测试与结果查看

### 4. 系统设置
- API地址配置
- WebSocket地址配置
- 模型选择
- Mock模式切换
- 暗色/亮色模式切换

## 快速开始

### 环境准备

- **Node.js**: 18+
- **npm**: 9+

### 安装依赖

```bash
cd /root/Supply_Chain_Agent/supply_chain_agent/frontend
npm install
```

### 开发模式运行

```bash
npm run dev
```

访问 http://localhost:3000

### 生产构建

```bash
npm run build
```

构建后的文件位于 `dist/` 目录

### 预览生产版本

```bash
npm run preview
```

## 环境变量配置

创建 `.env.local` 文件配置本地环境：

```env
# API基础URL（开发时使用代理）
VITE_API_BASE_URL=/api

# WebSocket地址
VITE_WS_URL=ws://localhost:8000/ws
```

## 项目结构

```
src/
├── api/                    # API服务层
│   ├── client.ts           # Axios封装
│   ├── chatService.ts      # 对话服务
│   ├── statsService.ts     # 统计服务
│   ├── toolService.ts      # 工具服务
│   └── mock/               # Mock数据
│       └── chatMock.ts
├── components/             # 组件
│   ├── layout/             # 布局组件
│   │   ├── AppLayout.tsx
│   │   ├── SidebarMenu.tsx
│   │   └── *.css
│   ├── chat/               # 聊天组件
│   │   ├── ChatMessage.tsx
│   │   ├── ChatInput.tsx
│   │   ├── ChatCard.tsx
│   │   └── *.css
│   ├── agent/              # Agent组件
│   │   ├── AgentTrajectory.tsx
│   │   ├── ToolCallCard.tsx
│   │   └── *.css
│   └── common/             # 通用组件
│       ├── ErrorBoundary.tsx
├── hooks/                  # 自定义Hooks
│   ├── useWebSocket.ts
│   ├── useAgentEvents.ts
│   ├── useLocalStorage.ts
│   └── useTimeAgo.ts
├── pages/                  # 页面
│   ├── chat/
│   │   ├── ChatPage.tsx
│   │   └── ChatPage.css
│   ├── dashboard/
│   │   ├── DashboardPage.tsx
│   │   └── DashboardPage.css
│   ├── tools/
│   │   ├── ToolsPage.tsx
│   │   └── ToolsPage.css
│   └── settings/
│       ├── SettingsPage.tsx
│       └── SettingsPage.css
├── store/                  # Zustand状态管理
│   ├── uiStore.ts          # UI状态
│   ├── conversationStore.ts # 对话状态
│   └── toolStore.ts        # 工具状态
├── types/                  # TypeScript类型
│   ├── agent.ts
│   ├── conversation.ts
│   ├── tool.ts
│   ├── dashboard.ts
│   └── index.ts
├── styles/                 # 全局样式
│   ├── variables.css
│   └── global.css
├── utils/                  # 工具函数
│   └── classNames.ts
├── AppRoutes.tsx           # 路由配置
├── AppLogic.tsx            # 应用逻辑封装
└── main.tsx                # 入口文件
```

## 功能说明

### Mock模式 vs 真实API模式

在设置页面可以切换：
- **Mock模式**：使用 `src/api/mock/chatMock.ts` 中的模拟数据进行前端开发，无需启动后端
- **真实API模式**：连接后端服务 `http://localhost:8000`

### 暗色模式

通过右上角开关切换，支持：
- 整个系统的暗色/亮色主题
- Ant Design组件自动适配
- 自定义组件颜色适配

### WebSocket连接

- 自动连接WebSocket
- 连接状态实时显示在Header
- 断线自动重连（最多5次）

## 后端API对接

假设后端运行在 `http://localhost:8000`，提供以下接口：

### 核心接口

| 接口 | 方法 | 描述 |
|------|------|------|
| `/api/process` | POST | 处理用户查询 |
| `/api/sessions` | POST/GET/DELETE | 会话管理 |
| `/api/tools` | GET/POST | 工具管理 |
| `/api/metrics` | GET | 性能指标 |
| `/ws/process` | WebSocket | 实时处理流 |

详细的API文档请参考项目根目录的 `docs/API_DOCUMENTATION.md`

## 开发规范

- 所有组件使用 TypeScript，禁止 `any`
- 函数式组件 + React.memo 优化
- 样式使用 CSS + CSS Variables，支持暗色模式
- 组件命名 PascalCase，文件命名保持一致

## 浏览器支持

- Chrome 90+
- Firefox 90+
- Safari 15+
- Edge 90+

## 许可证

MIT License
