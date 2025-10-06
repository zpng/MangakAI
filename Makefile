# MangakAI Makefile v2.0
# 异步架构的前后端分离项目便捷命令

.PHONY: help setup install install-backend install-frontend dev dev-full dev-backend dev-celery dev-frontend \
        build build-frontend clean docker-build docker-up docker-down prod-up prod-down \
        db-init db-migrate db-upgrade test lint format monitor

# 默认目标 - 显示帮助信息
help:
	@echo "🚀 MangakAI v2.0 项目命令："
	@echo ""
	@echo "📋 快速开始："
	@echo "  make setup            - 自动化项目设置 (推荐首次使用)"
	@echo "  make dev-full         - 启动完整开发环境 (后端+Celery+前端)"
	@echo ""
	@echo "📦 安装依赖："
	@echo "  make install          - 安装前后端所有依赖"
	@echo "  make install-backend  - 安装后端依赖 (包含异步组件)"
	@echo "  make install-frontend - 安装前端依赖"
	@echo ""
	@echo "🔧 开发环境："
	@echo "  make dev              - 启动基础开发服务器 (后端+前端)"
	@echo "  make dev-full         - 启动完整开发环境 (包含Celery和监控)"
	@echo "  make dev-backend      - 仅启动后端API服务器 (端口 8000)"
	@echo "  make dev-celery       - 启动Celery异步任务处理器"
	@echo "  make dev-frontend     - 仅启动前端开发服务器 (端口 5173)"
	@echo ""
	@echo "🗄️  数据库管理："
	@echo "  make db-init          - 初始化数据库和迁移"
	@echo "  make db-migrate       - 生成新的数据库迁移"
	@echo "  make db-upgrade       - 应用数据库迁移"
	@echo ""
	@echo "🏗️  构建和部署："
	@echo "  make build            - 构建前端生产版本"
	@echo "  make prod-up          - 启动生产环境 (Docker Compose)"
	@echo "  make prod-down        - 停止生产环境"
	@echo ""
	@echo "🐳 Docker 开发："
	@echo "  make docker-build     - 构建开发环境 Docker 镜像"
	@echo "  make docker-up        - 启动开发环境 Docker 服务"
	@echo "  make docker-down      - 停止 Docker 服务"
	@echo ""
	@echo "📊 监控和工具："
	@echo "  make monitor          - 启动监控服务 (Flower + Metrics)"
	@echo "  make test             - 运行测试套件"
	@echo "  make lint             - 代码检查和格式化"
	@echo "  make clean            - 清理构建文件和缓存"
	@echo ""
	@echo "ℹ️  其他："
	@echo "  make status           - 查看服务运行状态"
	@echo "  make stop             - 停止所有本地服务"
	@echo "  make help             - 显示此帮助信息"

# 自动化项目设置
setup:
	@echo "🚀 开始自动化项目设置..."
	@chmod +x scripts/setup.sh
	@./scripts/setup.sh
	@echo "✅ 项目设置完成！"

# 安装所有依赖
install: install-backend install-frontend
	@echo "✅ 所有依赖安装完成"

# 安装后端依赖 (包含异步组件)
install-backend:
	@echo "📦 安装后端依赖 (包含异步组件)..."
	@if ! command -v uv &> /dev/null; then \
		echo "安装 uv 包管理器..."; \
		curl -LsSf https://astral.sh/uv/install.sh | sh; \
		source $$HOME/.cargo/env; \
	fi
	@echo "同步 Python 依赖..."
	@uv sync
	@echo "✅ 后端依赖安装完成"

# 安装前端依赖
install-frontend:
	@echo "📦 安装前端依赖..."
	@cd frontend && npm install
	@echo "✅ 前端依赖安装完成"

# 数据库初始化
db-init:
	@echo "🗄️  初始化数据库..."
	@if [ ! -f "alembic.ini" ]; then \
		echo "初始化 Alembic..."; \
		uv run alembic init alembic; \
	fi
	@echo "✅ 数据库初始化完成"

# 生成数据库迁移
db-migrate:
	@echo "🗄️  生成数据库迁移..."
	@uv run alembic revision --autogenerate -m "Auto migration"
	@echo "✅ 数据库迁移生成完成"

# 应用数据库迁移
db-upgrade:
	@echo "🗄️  应用数据库迁移..."
	@uv run alembic upgrade head
	@echo "✅ 数据库迁移应用完成"

# 启动基础开发环境 (后端 + 前端)
dev:
	@echo "🚀 启动基础开发环境..."
	@echo "后端API: http://localhost:8000"
	@echo "前端界面: http://localhost:5173"
	@echo "API文档: http://localhost:8000/docs"
	@echo ""
	@echo "⚠️  注意: 此模式不包含异步任务处理，如需完整功能请使用 'make dev-full'"
	@echo "按 Ctrl+C 停止所有服务"
	@trap 'kill %1 %2 2>/dev/null; exit' INT; \
	make dev-backend & \
	make dev-frontend & \
	wait

# 启动完整开发环境 (后端 + Celery + 前端 + 监控)
dev-full:
	@echo "🚀 启动完整开发环境..."
	@echo "后端API: http://localhost:8000"
	@echo "前端界面: http://localhost:5173"
	@echo "API文档: http://localhost:8000/docs"
	@echo "Flower监控: http://localhost:5555"
	@echo "Prometheus指标: http://localhost:8001/metrics"
	@echo ""
	@echo "✨ 包含完整异步处理功能"
	@echo "按 Ctrl+C 停止所有服务"
	@trap 'kill %1 %2 %3 %4 2>/dev/null; exit' INT; \
	make dev-backend & \
	make dev-celery & \
	make dev-frontend & \
	make monitor & \
	wait

# 启动后端开发服务器
dev-backend:
	@echo "🔧 启动后端API服务器..."
	@if [ ! -f ".env" ]; then \
		echo "⚠️  警告: .env 文件不存在，请运行 'make setup' 或手动创建"; \
		echo "需要配置 GEMINI_API_KEY 等环境变量"; \
	fi
	@uv run uvicorn server:app --host 0.0.0.0 --port 8000 --reload

# 启动Celery异步任务处理器
dev-celery:
	@echo "⚡ 启动Celery异步任务处理器..."
	@echo "启动 Celery Worker..."
	@trap 'kill %1 %2 2>/dev/null; exit' INT; \
	uv run celery -A celery_app worker --loglevel=info --concurrency=2 & \
	sleep 3 && \
	echo "启动 Celery Beat 调度器..." && \
	uv run celery -A celery_app beat --loglevel=info & \
	wait

# 启动前端开发服务器
dev-frontend:
	@echo "⚛️  启动前端开发服务器..."
	@cd frontend && npm run dev

# 启动监控服务
monitor:
	@echo "📊 启动监控服务..."
	@echo "启动 Flower (Celery监控)..."
	@trap 'kill %1 %2 2>/dev/null; exit' INT; \
	uv run celery -A celery_app flower --port=5555 & \
	sleep 2 && \
	echo "启动 Prometheus 指标服务器..." && \
	uv run python -c "from monitoring.metrics import start_metrics_server; start_metrics_server(); import time; time.sleep(3600)" & \
	wait

# 构建前端生产版本
build: build-frontend

build-frontend:
	@echo "🏗️  构建前端生产版本..."
	@cd frontend && npm run build
	@echo "✅ 前端构建完成，文件位于 frontend/dist/"

# 生产环境部署
prod-up:
	@echo "🚀 启动生产环境..."
	@if [ ! -f ".env" ]; then \
		echo "❌ .env 文件不存在，请先配置环境变量"; \
		exit 1; \
	fi
	@echo "构建生产镜像..."
	@docker-compose -f docker-compose.prod.yml build
	@echo "启动生产服务..."
	@docker-compose -f docker-compose.prod.yml up -d
	@echo "等待服务启动..."
	@sleep 10
	@echo "应用数据库迁移..."
	@docker-compose -f docker-compose.prod.yml exec -T backend alembic upgrade head
	@echo ""
	@echo "✅ 生产环境启动完成！"
	@echo "前端: http://localhost:3000"
	@echo "后端API: http://localhost:8000"
	@echo "API文档: http://localhost:8000/docs"
	@echo "Flower监控: http://localhost:5555"
	@echo "Prometheus: http://localhost:9090"
	@echo "Grafana: http://localhost:3001"

# 停止生产环境
prod-down:
	@echo "🛑 停止生产环境..."
	@docker-compose -f docker-compose.prod.yml down
	@echo "✅ 生产环境已停止"

# 生产环境重启
prod-restart: prod-down prod-up

# 查看生产环境日志
prod-logs:
	@echo "📋 查看生产环境日志..."
	@docker-compose -f docker-compose.prod.yml logs -f

# 清理构建文件和缓存
clean:
	@echo "🧹 清理构建文件和缓存..."
	@rm -rf frontend/dist/
	@rm -rf frontend/node_modules/.vite/
	@rm -rf data/output/*.png
	@rm -rf data/output/*.pdf
	@rm -rf data/cloud_storage/
	@rm -rf __pycache__/
	@rm -rf .pytest_cache/
	@find . -name "*.pyc" -delete
	@find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
	@echo "✅ 清理完成"

# Docker 开发环境
docker-build:
	@echo "🐳 构建开发环境 Docker 镜像..."
	@docker-compose build
	@echo "✅ Docker 镜像构建完成"

docker-up:
	@echo "🐳 启动开发环境 Docker 服务..."
	@if [ ! -f ".env" ]; then \
		echo "⚠️  警告: .env 文件不存在，请创建并配置环境变量"; \
		exit 1; \
	fi
	@docker-compose up -d
	@echo "等待服务启动..."
	@sleep 10
	@echo "应用数据库迁移..."
	@docker-compose exec -T backend alembic upgrade head
	@echo "✅ 开发环境已启动"
	@echo "前端: http://localhost:5173"
	@echo "后端: http://localhost:8000"

docker-down:
	@echo "🐳 停止 Docker 服务..."
	@docker-compose down
	@echo "✅ Docker 服务已停止"

# 测试相关命令
test:
	@echo "🧪 运行测试套件..."
	@uv run pytest tests/ -v
	@echo "✅ 测试完成"

test-coverage:
	@echo "🧪 运行测试并生成覆盖率报告..."
	@uv run pytest tests/ --cov=. --cov-report=html --cov-report=term
	@echo "✅ 测试覆盖率报告生成完成，查看 htmlcov/index.html"

# 代码质量检查
lint:
	@echo "🔍 运行代码检查..."
	@echo "检查 Python 代码..."
	@uv run black --check . || (echo "运行 'make format' 格式化代码" && exit 1)
	@uv run isort --check-only . || (echo "运行 'make format' 格式化导入" && exit 1)
	@uv run flake8 . || true
	@echo "检查前端代码..."
	@cd frontend && npm run lint
	@echo "✅ 代码检查完成"

# 代码格式化
format:
	@echo "✨ 格式化代码..."
	@echo "格式化 Python 代码..."
	@uv run black .
	@uv run isort .
	@echo "格式化前端代码..."
	@cd frontend && npm run format
	@echo "✅ 代码格式化完成"

# 检查环境配置
check-env:
	@echo "🔍 检查环境配置..."
	@if [ ! -f ".env" ]; then \
		echo "❌ .env 文件不存在"; \
		echo "请运行 'make setup' 或手动创建 .env 文件"; \
		echo "需要配置: GEMINI_API_KEY, DATABASE_URL, REDIS_URL 等"; \
		exit 1; \
	else \
		echo "✅ .env 文件存在"; \
	fi
	@if ! command -v uv &> /dev/null; then \
		echo "❌ uv 包管理器未安装，请运行 'make install-backend'"; \
		exit 1; \
	else \
		echo "✅ uv 包管理器已安装"; \
	fi
	@if [ ! -d "frontend/node_modules" ]; then \
		echo "❌ 前端依赖未安装，请运行 'make install-frontend'"; \
		exit 1; \
	else \
		echo "✅ 前端依赖已安装"; \
	fi
	@echo "✅ 环境检查通过"

# 快速启动 (检查环境后启动完整开发环境)
start: check-env dev-full

# 显示服务状态
status:
	@echo "📊 服务运行状态："
	@echo ""
	@echo "🔧 本地开发服务："
	@if pgrep -f "uvicorn server:app" > /dev/null; then \
		echo "  ✅ 后端API服务 (端口 8000)"; \
	else \
		echo "  ❌ 后端API服务未运行"; \
	fi
	@if pgrep -f "celery.*worker" > /dev/null; then \
		echo "  ✅ Celery Worker (异步任务)"; \
	else \
		echo "  ❌ Celery Worker 未运行"; \
	fi
	@if pgrep -f "celery.*beat" > /dev/null; then \
		echo "  ✅ Celery Beat (任务调度)"; \
	else \
		echo "  ❌ Celery Beat 未运行"; \
	fi
	@if pgrep -f "vite.*--port 5173" > /dev/null; then \
		echo "  ✅ 前端开发服务 (端口 5173)"; \
	else \
		echo "  ❌ 前端开发服务未运行"; \
	fi
	@if pgrep -f "celery.*flower" > /dev/null; then \
		echo "  ✅ Flower 监控 (端口 5555)"; \
	else \
		echo "  ❌ Flower 监控未运行"; \
	fi
	@echo ""
	@echo "🐳 Docker 服务："
	@if docker-compose ps | grep -q "Up"; then \
		echo "  ✅ Docker 开发环境运行中"; \
		docker-compose ps; \
	else \
		echo "  ❌ Docker 开发环境未运行"; \
	fi
	@echo ""
	@if docker-compose -f docker-compose.prod.yml ps | grep -q "Up"; then \
		echo "  ✅ Docker 生产环境运行中"; \
		docker-compose -f docker-compose.prod.yml ps; \
	else \
		echo "  ❌ Docker 生产环境未运行"; \
	fi

# 停止所有本地服务
stop:
	@echo "🛑 停止所有本地服务..."
	@echo "停止后端服务..."
	@pkill -f "uvicorn server:app" 2>/dev/null || true
	@echo "停止 Celery 服务..."
	@pkill -f "celery.*worker" 2>/dev/null || true
	@pkill -f "celery.*beat" 2>/dev/null || true
	@pkill -f "celery.*flower" 2>/dev/null || true
	@echo "停止前端服务..."
	@pkill -f "vite.*--port 5173" 2>/dev/null || true
	@echo "停止监控服务..."
	@pkill -f "prometheus" 2>/dev/null || true
	@echo "✅ 所有本地服务已停止"

# 重启所有服务
restart: stop dev-full

# 查看日志
logs:
	@echo "📋 查看应用日志..."
	@if [ -d "logs" ]; then \
		tail -f logs/*.log; \
	else \
		echo "日志目录不存在，请先启动服务"; \
	fi

# 数据库管理工具
db-reset:
	@echo "⚠️  重置数据库 (危险操作)..."
	@read -p "确定要重置数据库吗? (y/N): " confirm; \
	if [ "$$confirm" = "y" ] || [ "$$confirm" = "Y" ]; then \
		echo "删除数据库迁移..."; \
		rm -rf alembic/versions/*.py; \
		echo "重新生成迁移..."; \
		uv run alembic revision --autogenerate -m "Initial migration"; \
		echo "应用迁移..."; \
		uv run alembic upgrade head; \
		echo "✅ 数据库重置完成"; \
	else \
		echo "操作已取消"; \
	fi

# 备份数据库
db-backup:
	@echo "💾 备份数据库..."
	@mkdir -p backups
	@TIMESTAMP=$$(date +%Y%m%d_%H%M%S); \
	if grep -q "postgresql" .env; then \
		DB_URL=$$(grep DATABASE_URL .env | cut -d'=' -f2); \
		pg_dump "$$DB_URL" > "backups/backup_$$TIMESTAMP.sql"; \
		echo "✅ 数据库备份完成: backups/backup_$$TIMESTAMP.sql"; \
	else \
		echo "⚠️  仅支持 PostgreSQL 数据库备份"; \
	fi

# 性能测试
perf-test:
	@echo "⚡ 运行性能测试..."
	@if command -v ab &> /dev/null; then \
		echo "测试后端API性能..."; \
		ab -n 100 -c 10 http://localhost:8000/health; \
	else \
		echo "请安装 apache2-utils (ab 命令) 进行性能测试"; \
	fi

# 安全检查
security-check:
	@echo "🔒 运行安全检查..."
	@uv run safety check
	@echo "检查前端依赖安全性..."
	@cd frontend && npm audit

# 更新依赖
update-deps:
	@echo "📦 更新项目依赖..."
	@echo "更新后端依赖..."
	@uv sync --upgrade
	@echo "更新前端依赖..."
	@cd frontend && npm update
	@echo "✅ 依赖更新完成"