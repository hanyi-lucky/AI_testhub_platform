# 生产部署（Linux）

适用路径：`/opt/testhub_platform`  
后端域名/IP：`172.13.6.230`  
前端部署：独立部署在 `/opt/testhub_platform/frontend/dist`

---

## 1) 创建用户与目录

```bash
sudo useradd -m -s /bin/bash testhub
sudo mkdir -p /opt/testhub_platform
sudo chown -R testhub:testhub /opt/testhub_platform
```

将代码放到：
```
/opt/testhub_platform
```

目录结构示例：
```
/opt/testhub_platform/
├── backend/
├── apps/
├── manage.py
├── requirements.txt
├── media/
├── static/
└── frontend/
```

---

## 2) Python 依赖与虚拟环境

```bash
cd /opt/testhub_platform
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install daphne channels channels-redis
```

---

## 3) 环境变量（.env）

创建 `/opt/testhub_platform/.env`：

```env
DEBUG=False
SECRET_KEY=your-secret-key
ALLOWED_HOSTS=172.13.6.230

DB_NAME=testhub
DB_USER=root
DB_PASSWORD=your_db_password
DB_HOST=127.0.0.1
DB_PORT=3306

REDIS_URL=redis://:1234@127.0.0.1:6379/0
```

---

## 4) 收集静态文件

```bash
source /opt/testhub_platform/venv/bin/activate
cd /opt/testhub_platform
python manage.py collectstatic --noinput
```

---

## 5) systemd 服务

### 5.1 ASGI 服务（Daphne）
`/etc/systemd/system/testhub-asgi.service`

```ini
[Unit]
Description=TestHub ASGI (Daphne)
After=network.target

[Service]
User=testhub
WorkingDirectory=/opt/testhub_platform
Environment="DJANGO_SETTINGS_MODULE=backend.settings"
Environment="PYTHONUNBUFFERED=1"
EnvironmentFile=/opt/testhub_platform/.env
ExecStart=/opt/testhub_platform/venv/bin/daphne -b 0.0.0.0 -p 8000 backend.asgi:application
Restart=always

[Install]
WantedBy=multi-user.target
```

### 5.2 Celery Worker 服务
`/etc/systemd/system/testhub-celery.service`

```ini
[Unit]
Description=TestHub Celery Worker
After=network.target

[Service]
User=testhub
WorkingDirectory=/opt/testhub_platform
Environment="DJANGO_SETTINGS_MODULE=backend.settings"
Environment="PYTHONUNBUFFERED=1"
EnvironmentFile=/opt/testhub_platform/.env
ExecStart=/opt/testhub_platform/venv/bin/celery -A backend worker --loglevel=info --pool=solo --concurrency=1
Restart=always

[Install]
WantedBy=multi-user.target
```

### 5.3 启动服务
```bash
sudo systemctl daemon-reload
sudo systemctl enable testhub-asgi testhub-celery
sudo systemctl start testhub-asgi testhub-celery
```

### 5.4 状态与日志
```bash
sudo systemctl status testhub-asgi
sudo systemctl status testhub-celery

journalctl -u testhub-asgi -f
journalctl -u testhub-celery -f
```

---

## 6) Nginx 配置（含 WebSocket）

`/etc/nginx/conf.d/testhub.conf`

```nginx
server {
    listen 80;
    server_name 172.13.6.230;

    # 静态与媒体
    location /static/ {
        alias /opt/testhub_platform/static/;
    }

    location /media/ {
        alias /opt/testhub_platform/media/;
    }

    # API
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    # WebSocket
    location /ws/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }

    # 前端独立部署
    location / {
        root /opt/testhub_platform/frontend/dist;
        try_files $uri /index.html;
    }
}
```

重启 Nginx：
```bash
sudo nginx -t
sudo systemctl restart nginx
```

---

## 7) 前端构建（独立部署）

```bash
cd /opt/testhub_platform/frontend
npm install
npm run build
```

---

## 8) 验证

- API：`http://172.13.6.230/api/`
- WebSocket：`ws://172.13.6.230/ws/app-automation/executions/<id>/`

---

## 9) 一键部署脚本（可选）

> 脚本会写入 `.env`、systemd 与 Nginx 配置，请先确认变量值（如 DB/Redis 密码）。

保存为 `/opt/testhub_platform/deploy_prod.sh`：

```bash
#!/usr/bin/env bash
set -e

APP_DIR="/opt/testhub_platform"
VENV_DIR="$APP_DIR/venv"
NGINX_CONF="/etc/nginx/conf.d/testhub.conf"

echo "=== 1) 创建虚拟环境 ==="
if [ ! -d "$VENV_DIR" ]; then
  python3 -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"

echo "=== 2) 安装依赖 ==="
pip install -r "$APP_DIR/requirements.txt"
pip install daphne channels channels-redis

echo "=== 3) 写入 .env ==="
cat > "$APP_DIR/.env" <<EOF
DEBUG=False
SECRET_KEY=your-secret-key
ALLOWED_HOSTS=172.13.6.230

DB_NAME=testhub
DB_USER=root
DB_PASSWORD=your_db_password
DB_HOST=127.0.0.1
DB_PORT=3306

REDIS_URL=redis://:1234@127.0.0.1:6379/0
EOF

echo "=== 4) 收集静态文件 ==="
python "$APP_DIR/manage.py" collectstatic --noinput

echo "=== 5) systemd 服务 ==="
cat > /etc/systemd/system/testhub-asgi.service <<EOF
[Unit]
Description=TestHub ASGI (Daphne)
After=network.target

[Service]
User=testhub
WorkingDirectory=$APP_DIR
Environment="DJANGO_SETTINGS_MODULE=backend.settings"
Environment="PYTHONUNBUFFERED=1"
EnvironmentFile=$APP_DIR/.env
ExecStart=$VENV_DIR/bin/daphne -b 0.0.0.0 -p 8000 backend.asgi:application
Restart=always

[Install]
WantedBy=multi-user.target
EOF

cat > /etc/systemd/system/testhub-celery.service <<EOF
[Unit]
Description=TestHub Celery Worker
After=network.target

[Service]
User=testhub
WorkingDirectory=$APP_DIR
Environment="DJANGO_SETTINGS_MODULE=backend.settings"
Environment="PYTHONUNBUFFERED=1"
EnvironmentFile=$APP_DIR/.env
ExecStart=$VENV_DIR/bin/celery -A backend worker --loglevel=info --pool=solo --concurrency=1
Restart=always

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable testhub-asgi testhub-celery
systemctl restart testhub-asgi testhub-celery

echo "=== 6) Nginx 配置 ==="
cat > "$NGINX_CONF" <<EOF
server {
    listen 80;
    server_name 172.13.6.230;

    location /static/ {
        alias /opt/testhub_platform/static/;
    }

    location /media/ {
        alias /opt/testhub_platform/media/;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    }

    location /ws/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
    }

    location / {
        root /opt/testhub_platform/frontend/dist;
        try_files \$uri /index.html;
    }
}
EOF

nginx -t
systemctl restart nginx

echo "=== ✅ 部署完成 ==="
```

执行：
```bash
sudo chmod +x /opt/testhub_platform/deploy_prod.sh
sudo /opt/testhub_platform/deploy_prod.sh
```

