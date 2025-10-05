# MangakAI - 前后端分离版本

Transform your stories into manga panels with AI and custom style preferences!

## 项目结构

这是一个前后端分离的漫画生成应用：

- **后端**: FastAPI服务器 (Python)
- **前端**: React应用 (JavaScript/Vite)

## 功能特性

- 📝 **文本输入生成**: 直接输入故事文本生成漫画
- 📁 **文件上传生成**: 上传.txt文件生成漫画
- 🎨 **风格自定义**: 多种艺术风格、情绪、色彩等选项
- 🔄 **面板重新生成**: 对特定面板进行修改和重新生成
- 📥 **PDF导出**: 将生成的漫画导出为PDF文件
- 🎯 **示例展示**: 内置示例故事和漫画面板

## 环境要求

### 后端
- Python 3.11+
- 虚拟环境 (推荐使用 uv 或 venv)

### 前端
- Node.js 20.19+ 或 22.12+
- npm 或 yarn

## 快速开始 (推荐使用 Makefile)

### 1. 一键安装和启动

```bash
# 克隆项目
git clone <repository-url>
cd MangakAI

# 设置环境变量
cp .env.example .env
# 编辑 .env 文件，添加你的 GEMINI_API_KEY

# 安装所有依赖
make install

# 启动前后端服务器
make dev
```

### 2. 常用 Makefile 命令

```bash
# 查看所有可用命令
make help

# 安装依赖
make install              # 安装前后端所有依赖
make install-backend      # 仅安装后端依赖
make install-frontend     # 仅安装前端依赖

# 开发环境
make dev                  # 同时启动前后端 (推荐)
make dev-backend          # 仅启动后端 (端口 8000)
make dev-frontend         # 仅启动前端 (端口 5173)

# 构建和部署
make build                # 构建前端生产版本
make docker-up            # 使用 Docker Compose 启动
make docker-down          # 停止 Docker 服务

# 工具命令
make status               # 查看服务运行状态
make stop                 # 停止所有服务
make clean                # 清理构建文件
```

### 3. 手动安装和运行

如果不使用 Makefile，也可以手动执行：

#### 后端设置

```bash
# 创建虚拟环境 (使用 uv)
uv venv
source .venv/bin/activate  # Linux/Mac
# 或
.venv\Scripts\activate     # Windows

# 安装依赖
uv pip install -e .

# 启动后端服务器
uvicorn server:app --host 0.0.0.0 --port 8000
```

后端服务器将在 http://localhost:8000 运行

#### 前端设置

```bash
# 进入前端目录
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

前端应用将在 http://localhost:5173 运行

### 3. 生产环境部署

#### 后端部署
```bash
# 使用 gunicorn 部署
pip install gunicorn
gunicorn server:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000

# 或使用 Docker
docker build -t mangakai-backend .
docker run -p 8000:8000 mangakai-backend
```

#### 前端部署
```bash
# 构建生产版本
npm run build

# 部署到静态文件服务器 (nginx, Apache, 或 CDN)
# 构建文件位于 dist/ 目录
```

## API 文档

后端提供完整的 REST API，启动后端服务器后访问：
- API 文档: http://localhost:8000/docs
- 交互式 API: http://localhost:8000/redoc

### 主要 API 端点

- `GET /api/style-options` - 获取所有样式选项
- `POST /api/generate-manga` - 从文本生成漫画
- `POST /api/generate-manga-from-file` - 从文件生成漫画
- `POST /api/regenerate-panel` - 重新生成特定面板
- `POST /api/create-pdf` - 创建PDF文件
- `GET /api/examples` - 获取示例列表
- `GET /api/examples/{name}` - 获取特定示例

## 配置说明

### 环境变量 (.env)

```env
GEMINI_API_KEY=your_gemini_api_key_here
TEMPLATE_PATH=data/templates/template.png
OUTPUT_DIR=data/output
STORIES_DIR=data/stories
IMAGE_MODEL_NAME=gemini-2.5-flash-image-preview
SCENE_MODEL_NAME=gemini-2.0-flash
```

### 前端配置

前端默认连接到 `http://localhost:8000` 的后端API。如需修改，请编辑 `frontend/src/App.jsx` 中的 `API_BASE_URL` 常量。

## 项目文件结构

```
MangakAI/
├── server.py              # FastAPI 后端服务器
├── manga.py               # 漫画生成核心逻辑
├── utils.py               # 工具函数和提示模板
├── app.py                 # 原始 Gradio 应用 (已弃用)
├── pyproject.toml         # Python 依赖配置
├── data/                  # 数据目录
│   ├── examples/          # 示例漫画
│   ├── output/            # 生成的漫画输出
│   └── templates/         # 漫画模板
└── frontend/              # React 前端应用
    ├── src/
    │   ├── App.jsx        # 主应用组件
    │   ├── App.css        # 样式文件
    │   └── main.jsx       # 入口文件
    ├── package.json       # Node.js 依赖
    └── vite.config.js     # Vite 配置
```

## 开发说明

### 添加新功能

1. **后端**: 在 `server.py` 中添加新的API端点
2. **前端**: 在 `frontend/src/App.jsx` 中添加对应的UI组件和API调用

### 样式自定义

- 后端样式选项在 `utils.py` 中定义
- 前端样式在 `frontend/src/App.css` 中定义

### 调试

- 后端日志: 查看终端输出或配置日志文件
- 前端调试: 使用浏览器开发者工具

## 故障排除

### 常见问题

1. **CORS 错误**: 确保后端 CORS 配置正确
2. **API 连接失败**: 检查后端服务器是否运行在正确端口
3. **图片加载失败**: 确保静态文件服务配置正确
4. **Node.js 版本警告**: 升级到 Node.js 20.19+ 或 22.12+

### 日志查看

```bash
# 后端日志
tail -f logs/server.log

# 前端开发服务器日志
# 查看终端输出
```

## 许可证

[添加你的许可证信息]

## 贡献

欢迎提交 Issue 和 Pull Request！

## 联系方式

[添加联系信息]