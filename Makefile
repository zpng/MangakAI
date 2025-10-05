# MangakAI Makefile
# 前后端分离项目的便捷命令

.PHONY: help install install-backend install-frontend dev dev-backend dev-frontend build build-frontend clean docker-build docker-up docker-down

# 默认目标 - 显示帮助信息
help:
	@echo "MangakAI 项目命令："
	@echo ""
	@echo "安装依赖："
	@echo "  make install          - 安装前后端所有依赖"
	@echo "  make install-backend  - 安装后端依赖"
	@echo "  make install-frontend - 安装前端依赖"
	@echo ""
	@echo "开发环境："
	@echo "  make dev              - 同时启动前后端开发服务器"
	@echo "  make dev-backend      - 启动后端开发服务器 (端口 8000)"
	@echo "  make dev-frontend     - 启动前端开发服务器 (端口 5173)"
	@echo ""
	@echo "构建："
	@echo "  make build            - 构建前端生产版本"
	@echo "  make build-frontend   - 构建前端生产版本"
	@echo ""
	@echo "Docker："
	@echo "  make docker-build     - 构建 Docker 镜像"
	@echo "  make docker-up        - 启动 Docker Compose 服务"
	@echo "  make docker-down      - 停止 Docker Compose 服务"
	@echo ""
	@echo "其他："
	@echo "  make clean            - 清理构建文件和缓存"
	@echo "  make help             - 显示此帮助信息"

# 安装所有依赖
install: install-backend install-frontend
	@echo "✅ 所有依赖安装完成"

# 安装后端依赖
install-backend:
	@echo "📦 安装后端依赖..."
	@if [ ! -d ".venv" ]; then \
		echo "创建虚拟环境..."; \
		uv venv; \
	fi
	@echo "激活虚拟环境并安装依赖..."
	@uv pip install -e .
	@echo "✅ 后端依赖安装完成"

# 安装前端依赖
install-frontend:
	@echo "📦 安装前端依赖..."
	@cd frontend && npm install
	@echo "✅ 前端依赖安装完成"

# 同时启动前后端开发服务器
dev:
	@echo "🚀 启动前后端开发服务器..."
	@echo "后端: http://localhost:8000"
	@echo "前端: http://localhost:5173"
	@echo "API文档: http://localhost:8000/docs"
	@echo ""
	@echo "按 Ctrl+C 停止所有服务"
	@trap 'kill %1 %2 2>/dev/null; exit' INT; \
	make dev-backend & \
	make dev-frontend & \
	wait

# 启动后端开发服务器
dev-backend:
	@echo "🔧 启动后端服务器..."
	@if [ ! -f ".env" ]; then \
		echo "⚠️  警告: .env 文件不存在，请创建并配置 GEMINI_API_KEY"; \
	fi
	@source .venv/bin/activate && uvicorn server:app --host 0.0.0.0 --port 8000 --reload

# 启动前端开发服务器
dev-frontend:
	@echo "⚛️  启动前端服务器..."
	@cd frontend && npm run dev

# 构建前端生产版本
build: build-frontend

build-frontend:
	@echo "🏗️  构建前端生产版本..."
	@cd frontend && npm run build
	@echo "✅ 前端构建完成，文件位于 frontend/dist/"

# 清理构建文件和缓存
clean:
	@echo "🧹 清理构建文件和缓存..."
	@rm -rf frontend/dist/
	@rm -rf frontend/node_modules/.vite/
	@rm -rf data/output/*.png
	@rm -rf data/output/*.pdf
	@echo "✅ 清理完成"

# Docker 相关命令
docker-build:
	@echo "🐳 构建 Docker 镜像..."
	@docker-compose build
	@echo "✅ Docker 镜像构建完成"

docker-up:
	@echo "🐳 启动 Docker Compose 服务..."
	@if [ ! -f ".env" ]; then \
		echo "⚠️  警告: .env 文件不存在，请创建并配置环境变量"; \
		exit 1; \
	fi
	@docker-compose up -d
	@echo "✅ 服务已启动"
	@echo "前端: http://localhost:3000"
	@echo "后端: http://localhost:8000"

docker-down:
	@echo "🐳 停止 Docker Compose 服务..."
	@docker-compose down
	@echo "✅ 服务已停止"

# 检查环境
check-env:
	@echo "🔍 检查环境配置..."
	@if [ ! -f ".env" ]; then \
		echo "❌ .env 文件不存在"; \
		echo "请创建 .env 文件并添加以下配置:"; \
		echo "GEMINI_API_KEY=your_api_key_here"; \
		exit 1; \
	else \
		echo "✅ .env 文件存在"; \
	fi
	@if [ ! -d ".venv" ]; then \
		echo "❌ 虚拟环境不存在，请运行 make install-backend"; \
		exit 1; \
	else \
		echo "✅ 虚拟环境存在"; \
	fi
	@if [ ! -d "frontend/node_modules" ]; then \
		echo "❌ 前端依赖未安装，请运行 make install-frontend"; \
		exit 1; \
	else \
		echo "✅ 前端依赖已安装"; \
	fi
	@echo "✅ 环境检查通过"

# 快速启动 (检查环境后启动)
start: check-env dev

# 生产环境启动
prod-backend:
	@echo "🚀 启动生产环境后端..."
	@source .venv/bin/activate && gunicorn server:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000

# 显示服务状态
status:
	@echo "📊 服务状态："
	@echo ""
	@if pgrep -f "uvicorn server:app" > /dev/null; then \
		echo "✅ 后端服务正在运行"; \
	else \
		echo "❌ 后端服务未运行"; \
	fi
	@if pgrep -f "vite.*--port 5173" > /dev/null; then \
		echo "✅ 前端服务正在运行"; \
	else \
		echo "❌ 前端服务未运行"; \
	fi

# 停止所有服务
stop:
	@echo "🛑 停止所有服务..."
	@pkill -f "uvicorn server:app" 2>/dev/null || true
	@pkill -f "vite.*--port 5173" 2>/dev/null || true
	@echo "✅ 所有服务已停止"