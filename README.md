# TestHub 智能测试管理平台

<div align="center">

**AI 驱动的一站式测试管理平台**

*用例管理 · API 测试 · UI 自动化 · APP 自动化 · AI 用例生成 · 数据工厂*

[![Python](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-4.2-green.svg)](https://www.djangoproject.com/)
[![Vue](https://img.shields.io/badge/Vue-3.3-brightgreen.svg)](https://vuejs.org/)
[![Vite](https://img.shields.io/badge/Vite-7-orange.svg)](https://vitejs.dev/)
[![MySQL](https://img.shields.io/badge/MySQL-8.0-ff6f00.svg)](https://www.mysql.com/)

</div>

---

## 项目简介

TestHub 面向测试团队提供从**需求接入 → 用例设计 → 评审 → 执行 → 报告**的全流程管理，并将 AI 能力贯穿其中：上传需求文档即可自动生成测试用例，Browser-use 智能模式可让 AI 直接操作浏览器完成测试。同时覆盖 HTTP/WebSocket 接口测试、Web UI 自动化与 Android APP 自动化三大测试域。

**技术栈**：Django 4.2 + Django REST Framework 后端，Vue 3 + Vite 7 前端，MySQL 8.0 存储，Redis + Celery 处理异步任务，Django Channels 提供 WebSocket 实时通道。

## 功能总览

| 模块 | 核心能力 |
| --- | --- |
| **AI 需求分析** | 解析 PDF/Word/TXT 需求文档，提取业务需求，自动生成测试用例 |
| **智能助手** | 集成 Dify，多会话测试咨询与问题解答 |
| **用例管理** | 步骤化用例（前置条件/步骤/预期结果）、版本控制、附件评论、多维度分类 |
| **用例评审** | 多人评审、评审模板与检查清单、整体/用例/步骤三级意见、状态跟踪 |
| **API 测试** | HTTP/WebSocket、树形集合、环境变量、测试套件、请求历史、定时任务、Allure 报告 |
| **UI 自动化** | Selenium / Playwright 双引擎、元素库、POM、脚本录制回放、多浏览器、截图录像 |
| **AI 智能模式** | Browser-use 驱动，文本（DOM）/视觉（截图）双模式，AI 规划步骤并自动执行 |
| **APP 自动化** | Airtest 图像识别、ADB 设备池与锁定、组件化编排、UI Flow 场景、Celery 异步执行 |
| **测试执行与报告** | 测试计划、执行历史与对比、多维统计图表、Allure 专业报告 |
| **数据工厂** | 51 个数据工具（字符/编码/随机/加密/JSON/Crontab 等），标签化管理，可被接口和 UI 测试引用 |
| **统一配置中心** | 环境检测、驱动一键安装、AI 模型按角色配置与连接测试 |
| **平台能力** | JWT 双 Token 认证、多渠道 Webhook 通知、中英文国际化、项目级权限 |

## 核心亮点

- **AI 全链路**：需求文档 → 用例生成 → 用例评审 → 浏览器智能执行，支持 DeepSeek、通义千问、硅基流动、OpenAI 兼容接口等多种模型，按角色（编写/评审/浏览器）独立配置。
- **三域合一**：一个平台管理接口、Web、Android APP 三类测试资产与执行。
- **实时与异步**：WebSocket 推送 APP 执行进度；Celery + Redis 异步跑测试，不阻塞界面。
- **企业级安全**：JWT 双 Token（30 分钟 Access + 7 天 Refresh）、自动刷新、黑名单防重放、刷新期间请求排队。
- **开箱即用**：统一调度器同时管理 API/UI/APP 定时任务，通知配置（企业微信/钉钉/飞书）跨模块复用。

## 技术架构

```
┌────────────────────────────────────────────────────────┐
│                Vue 3 + Vite 7 前端 (Port 3000)          │
│   Element Plus · Pinia · Vue Router · vue-i18n · ECharts │
│   Monaco Editor · 用例/API/UI/APP/数据工厂 全部页面       │
└────────────────────────┬───────────────────────────────┘
                         │  REST (JWT Bearer) / WebSocket
┌────────────────────────▼───────────────────────────────┐
│              Django 4.2 + DRF 后端 (Port 8000)          │
│  users · projects · testcases · reviews · executions    │
│  api_testing · ui_automation · app_automation            │
│  requirement_analysis · assistant · data_factory · core  │
└───────┬───────────────┬───────────────┬────────────────┘
        │               │               │
   ┌────▼────┐    ┌─────▼─────┐   ┌─────▼──────┐
   │  MySQL  │    │   Redis   │   │  Channels  │
   │  8.0+   │    │  Celery   │   │  WebSocket │
   └─────────┘    └───────────┘   └────────────┘
        │
   Selenium · Playwright · Browser-use · Airtest · Allure
        │
   DeepSeek · 通义千问 · 硅基流动 · OpenAI 兼容 · Dify
```

### 技术栈

| 层级 | 技术 |
| --- | --- |
| 后端框架 | Django 4.2 + Django REST Framework + drf-spectacular (Swagger/ReDoc) |
| 认证安全 | rest_framework_simplejwt（双 Token + 黑名单） |
| 数据库 | MySQL 8.0+（PyMySQL） |
| 异步任务 | Celery 5.3 + Redis（APP 自动化执行） |
| 实时通信 | Django Channels + Daphne（WebSocket 进度推送） |
| 定时任务 | 自研统一调度器 `run_all_scheduled_tasks`（API/UI/APP 三模块） |
| 自动化引擎 | Selenium · Playwright · Browser-use · Airtest · allure-pytest |
| AI 能力 | langchain-openai、browser-use、多模型统一接入、Dify |
| 前端 | Vue 3.3 · Vite 7 · Element Plus · Pinia · Vue Router |
| 前端周边 | vue-i18n（国际化）· ECharts · Monaco Editor · vuedraggable · xlsx · curlconverter |

## 快速开始

### 环境要求

| 依赖 | 版本 | 说明 |
| --- | --- | --- |
| Python | 3.12（推荐） | 其他版本可能存在兼容性问题 |
| Node.js | 18+ | 开发环境必需，生产可不安装 |
| MySQL | 8.0+ | 需安装客户端用于建库与迁移 |
| Java | 17+ | 可选，Allure 报告生成依赖，缺失会导致报告失败 |
| Redis | 6.0+ | 可选，APP 自动化异步执行依赖 |

### 1. 后端

```bash
git clone https://github.com/hanyi-lucky/AI_testhub_platform.git
cd testhub_platform

# 虚拟环境
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/Mac

# 依赖与配置
pip install -r requirements.txt
cp .env.example .env         # 按模板配置数据库等连接信息

# 数据库（先创建库）
mysql -u root -p -e "CREATE DATABASE testhub CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
```

> 首次迁移若报 testcases migrations 缺失，执行：
> `mkdir -p apps/testcases/migrations` 后创建空 `__init__.py` 再重试。

```bash
# 初始化
python manage.py init_locator_strategies   # UI 元素定位策略
python manage.py load_component_pack       # APP 自动化组件库

# 启动
python manage.py run_all_scheduled_tasks   # 统一定时任务调度器
python manage.py runserver                 # Django 服务
celery -A backend worker -l info           # Celery（APP 自动化，可选）
```

数据工厂如需单独迁移：`python manage.py makemigrations data_factory && python manage.py migrate data_factory`

### 2. 前端

```bash
cd frontend
npm install
npm run dev      # 开发服务器
npm run build    # 生产构建
```

### 3. 访问

| 入口 | 地址 |
| --- | --- |
| 前端 | http://localhost:3000 |
| 后端 API | http://localhost:8000 |
| API 文档 | http://localhost:8000/api/docs/ |
| Admin 后台 | http://localhost:8000/admin/ |

## API 路由速查

所有接口统一前缀 `/api/`：

| 前缀 | 模块 |
| --- | --- |
| `/api/auth/`、`/api/users/` | 认证与用户 |
| `/api/projects/`、`/api/versions/` | 项目与版本 |
| `/api/testcases/`、`/api/testsuites/`、`/api/reviews/` | 用例、套件、评审 |
| `/api/executions/`、`/api/reports/` | 执行与报告 |
| `/api/requirement-analysis/`、`/api/assistant/` | AI 需求分析与助手 |
| `/api/` | API 测试（api_testing） |
| `/api/ui-automation/` | UI 自动化 |
| `/api/app-automation/` | APP 自动化 |
| `/api/data-factory/` | 数据工厂 |
| `/api/core/` | 统一通知配置 |
| `/api/docs/`、`/api/redoc/`、`/api/schema/` | Swagger / ReDoc / OpenAPI |

## 项目结构

```
testhub_platform/
├── apps/                            # Django 应用（按业务域拆分）
│   ├── users/  projects/  versions/ # 用户、项目、版本
│   ├── testcases/  testsuites/      # 用例与套件
│   ├── reviews/  executions/  reports/ # 评审、执行、报告
│   ├── requirement_analysis/  assistant/ # AI 需求分析、智能助手
│   ├── api_testing/                 # API 测试
│   ├── ui_automation/               # Web UI 自动化（含 ai/ 智能模式）
│   ├── app_automation/              # Android APP 自动化
│   │   ├── views/                   # 设备/元素/组件/用例/套件/执行等
│   │   ├── runners/  executors/     # UI Flow 与测试执行器
│   │   ├── managers/                # ADB 设备管理
│   │   ├── consumers.py             # WebSocket 进度推送
│   │   └── tasks.py                 # Celery 异步任务
│   ├── data_factory/                # 数据工厂
│   └── core/                        # 统一通知配置 + 管理命令
│       └── management/commands/
│           ├── run_all_scheduled_tasks.py  # 统一定时调度器
│           ├── init_locator_strategies.py  # 定位策略初始化
│           ├── load_component_pack.py      # APP 组件库初始化
│           └── download_webdrivers.py      # 浏览器驱动下载
├── backend/                         # 项目配置（settings/urls/middleware）
├── frontend/                        # Vue 3 前端
│   └── src/
│       ├── api/  stores/  router/  utils/
│       ├── locales/                 # 国际化语言包（zh-cn / en）
│       ├── components/
│       └── views/                   # 按模块分页（auth/projects/testcases/
│                                    #   api-testing/ui-automation/
│                                    #   app-automation/data-factory/...）
├── docs/                            # 项目文档
├── media/  logs/  allure/           # 上传文件、日志、Allure 报告
├── requirements.txt
└── manage.py
```

## 配置说明

### JWT 双 Token

```python
# backend/settings.py
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=30),   # Access Token
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),      # Refresh Token
    'ROTATE_REFRESH_TOKENS': True,                    # 刷新时轮换
    'BLACKLIST_AFTER_ROTATION': True,                 # 旧 Token 入黑名单
    'ALGORITHM': 'HS256',
    'AUTH_HEADER_TYPES': ('Bearer',),
}
```

前端在过期前 5 分钟自动刷新，刷新期间请求排队；登出即吊销 Refresh Token。

### AI 模型

统一配置中心中按**角色**配置，互不干扰：

| 角色 | 用途 |
| --- | --- |
| `testcase_writer` | 测试用例编写 |
| `testcase_reviewer` | 测试用例评审 |
| `browser_use_text` | Browser-use 文本模式（DOM 解析） |
| `browser_use_vision` | Browser-use 视觉模式（截图识别） |

支持 OpenAI、Azure OpenAI、Anthropic、Gemini、DeepSeek、通义千问、硅基流动及任意 OpenAI 兼容接口；配置项含 API Key、Base URL、模型名、Temperature、Max Tokens，并提供连接测试。

### 其他

- **Dify 助手**：配置 API URL + API Key 即可启用。
- **通知**：SMTP 邮件 + 企业微信/钉钉/飞书 Webhook，按模块独立开关，配置于 `/api/core/notification-configs/`。
- **APP 自动化**：配置 ADB 路径与设备连接；执行走 Celery（需 Redis），报告依赖 Java 17+。
- **国际化**：语言包 `frontend/src/locales/lang/{zh-cn,en}`，支持偏好持久化与运行时切换，详见 [I18N国际化使用说明](./docs/I18N国际化使用说明.md)。

## 数据库

| 领域 | 主要表 |
| --- | --- |
| 用户与项目 | `users`, `user_profiles`, `projects`, `project_members`, `versions` |
| 用例与评审 | `testcases`, `testcase_steps`, `testsuites`, `testcase_reviews`, `review_assignments`, `review_templates` |
| 执行与报告 | `test_plans`, `test_runs`, `test_run_cases` |
| AI 与助手 | `requirement_documents`, `generated_test_cases`, `ai_model_configs`, `prompt_configs`, `dify_configs`, `assistant_sessions`, `chat_messages` |
| API 测试 | `api_projects`, `api_collections`, `api_requests`, `api_environments`, `request_history`, `api_scheduled_tasks` |
| UI 自动化 | `ui_projects`, `ui_elements`, `ui_page_objects`, `ui_test_scripts`, `ui_test_suites`, `ui_test_executions`, `ai_cases`, `ai_intelligent_mode_configs` |
| APP 自动化 | `app_projects`, `app_devices`, `app_elements`, `app_components`, `app_component_packages`, `app_test_cases`, `app_test_suites`, `app_test_executions`, `app_scheduled_tasks`, `app_notification_logs` |
| 数据工厂 | `data_factory_record`（含标签与使用历史） |
| 通知与安全 | `core_unifiednotificationconfig`, `blacklisted_token`, `outstanding_token` |

## 文档

| 文档 | 说明 |
| --- | --- |
| [数据工厂快速开始](./docs/数据工厂快速开始.md) | 5 分钟上手数据工厂 |
| [数据工厂使用说明](./docs/数据工厂使用说明.md) | 功能介绍、使用技巧与最佳实践 |
| [数据工厂功能说明](./docs/数据工厂功能说明.md) | 功能详细说明 |
| [数据工厂API接口文档](./docs/数据工厂API接口文档.md) | 数据工厂 API 参考 |
| [UI自动化测试执行说明](./docs/UI自动化测试执行说明.md) | Web UI 自动化执行指南 |
| [WebDriver驱动管理优化说明](./docs/WebDriver驱动管理优化说明.md) | 驱动安装与管理 |
| [用例评审管理功能说明](./docs/用例评审管理功能说明.md) | 评审流程与模板 |
| [I18N国际化使用说明](./docs/I18N国际化使用说明.md) | 中英文国际化方案 |
| [问题排查指南](./docs/问题排查指南.md) | 常见问题与排查 |
