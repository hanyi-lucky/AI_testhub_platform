# 🚀 APP自动化测试 - 快速开始指南

本指南帮助你快速上手 TestHub 的 APP 自动化测试功能。

---

## ✅ 环境准备

### 1. 安装 ADB

#### Windows
```bash
# 下载 Android SDK Platform Tools
# https://developer.android.com/studio/releases/platform-tools

# 配置环境变量
setx PATH "%PATH%;C:\path\to\platform-tools"

# 验证安装
adb version
```

#### macOS
```bash
brew install android-platform-tools
adb version
```

#### Linux
```bash
sudo apt-get install android-tools-adb
adb version
```

### 2. 安装 Python 依赖

```bash
# 激活虚拟环境
E:\python_venv\testhub\Scripts\activate.bat  # Windows

# 安装依赖
pip install airtest>=1.3.0
pip install pocoui>=1.0.88
pip install pytest-django>=4.5.0
pip install loguru>=0.7.0
pip install allure-pytest>=2.15.0
```

### 3. 启动 Celery Worker

```bash
# Windows
celery -A backend worker -l info -P eventlet

# Linux/macOS
celery -A backend worker -l info
```

### 4. 准备 Android 设备

#### 方式 1：本地模拟器
```bash
# 启动模拟器（如雷电、夜神、Genymotion等）
# 查看设备列表
adb devices
```

#### 方式 2：USB真机
```bash
# 1. 开启开发者选项
# 2. 开启 USB 调试
# 3. 连接 USB 线
# 4. 查看设备
adb devices
```

#### 方式 3：远程设备
```bash
# 连接远程设备
adb connect 192.168.1.100:5555
```

---

## 🎯 快速体验（5分钟）

### 步骤 1：发现设备

```bash
curl http://localhost:8000/api/app-automation/devices/discover/ \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**返回结果**:
```json
{
  "success": true,
  "message": "发现 1 个设备",
  "devices": [
    {
      "device_id": "emulator-5554",
      "status": "online",
      "name": "Android SDK built for x86",
      "android_version": "11"
    }
  ]
}
```

### 步骤 2：创建应用包名

通过 Admin 后台或 API 创建：

**Admin**: `http://localhost:8000/admin/` → **APP应用包名管理** → **添加**

**API**:
```bash
curl -X POST http://localhost:8000/api/app-automation/packages/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Android设置",
    "package_name": "com.android.settings"
  }'
```

### 步骤 3：创建测试用例

**最简单的测试用例**（点击屏幕中心）:
```bash
curl -X POST http://localhost:8000/api/app-automation/test-cases/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "简单点击测试",
    "description": "测试点击屏幕中心",
    "app_package": 1,
    "ui_flow": {
      "steps": [
        {
          "action": "touch",
          "selector_type": "pos",
          "selector": "500, 500"
        },
        {
          "action": "sleep",
          "duration": 2
        }
      ]
    },
    "variables": []
  }'
```

### 步骤 4：执行测试

```bash
curl -X POST http://localhost:8000/api/app-automation/test-cases/1/execute/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "emulator-5554"
  }'
```

**返回结果**:
```json
{
  "success": true,
  "message": "测试已提交执行",
  "execution": {
    "id": 1,
    "case_name": "简单点击测试",
    "device_name": "emulator-5554",
    "status": "pending",
    "task_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
  }
}
```

### 步骤 5：查看执行结果

```bash
curl http://localhost:8000/api/app-automation/executions/1/ \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**查看 Celery 日志**:
```
[2026-02-04 11:36:00,000: INFO] 开始执行APP测试: 简单点击测试
[2026-02-04 11:36:05,000: INFO] 设备已锁定: emulator-5554
[2026-02-04 11:36:10,000: INFO] Airtest 初始化成功
[2026-02-04 11:36:15,000: INFO] 应用已启动: com.android.settings
[2026-02-04 11:36:20,000: INFO] UI Flow 执行完成
[2026-02-04 11:36:25,000: INFO] 设备已释放: emulator-5554
```

---

## 📝 常用测试场景

### 场景 1：登录测试（图片元素）

#### 1. 准备图片元素

将登录按钮截图保存为 `login_button.png`，放到 `media/app_automation/elements/common/` 目录。

#### 2. 创建元素

```bash
curl -X POST http://localhost:8000/api/app-automation/elements/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "登录按钮",
    "element_type": "image",
    "tags": ["登录", "按钮"],
    "config": {
      "file_path": "common/login_button.png",
      "threshold": 0.7
    }
  }'
```

#### 3. 创建测试用例

```json
{
  "name": "登录测试",
  "app_package": 1,
  "ui_flow": {
    "steps": [
      {
        "action": "wait",
        "element_id": 1,
        "timeout": 10
      },
      {
        "action": "touch",
        "element_id": 1
      },
      {
        "action": "sleep",
        "duration": 1
      },
      {
        "action": "text",
        "text": "admin"
      },
      {
        "action": "sleep",
        "duration": 1
      },
      {
        "action": "text",
        "text": "123456"
      },
      {
        "action": "snapshot",
        "name": "login_complete"
      }
    ]
  },
  "variables": []
}
```

### 场景 2：滑动测试

```json
{
  "name": "滑动测试",
  "app_package": 1,
  "ui_flow": {
    "steps": [
      {
        "action": "swipe",
        "start": "500, 1000",
        "end": "500, 500",
        "duration": 0.5
      },
      {
        "action": "sleep",
        "duration": 1
      },
      {
        "action": "swipe",
        "start": "500, 500",
        "end": "500, 1000",
        "duration": 0.5
      }
    ]
  }
}
```

### 场景 3：变量使用

```json
{
  "name": "变量测试",
  "app_package": 1,
  "ui_flow": {
    "steps": [
      {
        "action": "text",
        "text": "{{username}}"
      },
      {
        "action": "text",
        "text": "{{password}}"
      },
      {
        "action": "set_variable",
        "name": "login_time",
        "value": "2026-02-04",
        "scope": "outputs"
      }
    ]
  },
  "variables": [
    {
      "name": "username",
      "value": "admin",
      "scope": "local"
    },
    {
      "name": "password",
      "value": "123456",
      "scope": "local"
    }
  ]
}
```

### 场景 4：条件判断

```json
{
  "name": "条件判断测试",
  "app_package": 1,
  "ui_flow": {
    "steps": [
      {
        "action": "exists",
        "selector_type": "pos",
        "selector": "500, 500",
        "save_to": "element_found"
      },
      {
        "action": "assert",
        "condition": true,
        "message": "元素必须存在"
      }
    ]
  }
}
```

---

## 🎨 UI Flow 动作完整参考

### 1. touch/click - 点击

```json
{
  "action": "touch",
  "selector_type": "image",
  "selector": "button.png",
  "image_scope": "common",
  "threshold": 0.7
}

// 或使用元素ID
{
  "action": "touch",
  "element_id": 1
}

// 或使用坐标
{
  "action": "touch",
  "selector_type": "pos",
  "selector": "500, 500"
}
```

### 2. double_click - 双击

```json
{
  "action": "double_click",
  "selector_type": "pos",
  "selector": "500, 500"
}
```

### 3. swipe - 滑动

```json
{
  "action": "swipe",
  "start": "500, 1000",
  "end": "500, 500",
  "duration": 0.5
}
```

### 4. wait - 等待元素

```json
{
  "action": "wait",
  "element_id": 1,
  "timeout": 10
}
```

### 5. sleep - 休眠

```json
{
  "action": "sleep",
  "duration": 2
}
```

### 6. exists - 检查存在

```json
{
  "action": "exists",
  "element_id": 1,
  "save_to": "element_found"
}
```

### 7. snapshot - 截图

```json
{
  "action": "snapshot",
  "name": "screenshot_name"
}
```

### 8. text - 输入文本

```json
{
  "action": "text",
  "text": "Hello World"
}

// 使用变量
{
  "action": "text",
  "text": "{{username}}"
}
```

### 9. set_variable - 设置变量

```json
{
  "action": "set_variable",
  "name": "result",
  "value": "success",
  "scope": "outputs"
}
```

### 10. assert - 断言

```json
{
  "action": "assert",
  "condition": true,
  "message": "断言失败信息"
}
```

---

## 🐛 常见问题

### Q1: 找不到 ADB 命令？

**A**: 确保 ADB 已安装并配置环境变量：
```bash
# Windows
where adb

# Linux/macOS
which adb
```

### Q2: 设备连接失败？

**A**: 检查设备是否已连接并开启 USB 调试：
```bash
adb devices

# 如果设备显示 offline，重启 adb
adb kill-server
adb start-server
```

### Q3: Celery 任务不执行？

**A**: 确保 Celery Worker 已启动：
```bash
# 查看 Celery 日志
celery -A backend worker -l info -P eventlet
```

### Q4: Airtest 初始化失败？

**A**: 检查设备连接和权限：
```bash
# 测试设备连接
adb -s emulator-5554 shell

# 检查应用权限
adb shell pm list packages
```

### Q5: 图片元素找不到？

**A**: 检查图片路径和阈值：
- 确保图片在 `media/app_automation/elements/` 目录
- 调整 `threshold` 值（0.5 - 0.9）
- 确保图片清晰度

---

## 📊 监控和调试

### 1. 查看 Celery 日志

```bash
# 实时查看 Celery Worker 输出
# 会显示所有任务执行情况
```

### 2. 查看 Django 日志

```bash
# 查看 Django 服务器日志
# 会显示 API 请求和数据库操作
```

### 3. 查看执行进度

```bash
curl http://localhost:8000/api/app-automation/executions/1/ \
  -H "Authorization: Bearer YOUR_TOKEN"

# 返回：
# {
#   "id": 1,
#   "status": "running",
#   "progress": 50,
#   "passed_steps": 3,
#   "failed_steps": 0,
#   "total_steps": 6
# }
```

### 4. 停止执行

```bash
curl -X POST http://localhost:8000/api/app-automation/executions/1/stop/ \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

## 🎓 进阶使用

### 1. 批量创建元素

```python
# Django Shell
python manage.py shell

from apps.app_automation.models import AppElement

elements = [
    {
        'name': '登录按钮',
        'element_type': 'image',
        'config': {'file_path': 'common/login.png'}
    },
    {
        'name': '确定按钮',
        'element_type': 'image',
        'config': {'file_path': 'common/confirm.png'}
    },
]

for elem in elements:
    AppElement.objects.create(**elem)
```

### 2. 定时执行（扩展）

可以结合 Django-Celery-Beat 实现定时执行：

```python
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    'run-app-test-every-hour': {
        'task': 'apps.app_automation.tasks.execute_app_test_task',
        'schedule': crontab(minute=0, hour='*/1'),
        'args': (1,)  # execution_id
    },
}
```

### 3. 自定义 Allure 报告

修改 `apps/app_automation/executors/test_executor.py` 中的报告生成逻辑。

---

## 📞 获取帮助

- **文档**: `docs/APP自动化集成说明.md`
- **完成报告**: `docs/Phase3-4集成完成报告.md`
- **模块README**: `apps/app_automation/README.md`

---

**快速开始版本**: v1.0  
**最后更新**: 2026-02-04
