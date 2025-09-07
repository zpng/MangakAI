# MangakAI 📚✨

Transform your stories into stunning manga panels with AI! MangakAI is an intelligent manga generation tool that converts written narratives into visual manga-style panels using Google's Gemini AI models.

## 🌟 Features

- **🎨 AI-Powered Generation**: Convert stories into professional manga panels with scene intelligence
- **🎭 Style Customization**: Multiple art styles, moods, color palettes, and composition options
- **🔄 Panel Management**: Regenerate specific panels with custom modifications and reference images
- **📋 Custom Templates**: Upload your own panel layouts for personalized manga creation
- **📁 Export Options**: Generate PDFs and organize panels with version control
- **🖥️ Web Interface**: User-friendly Gradio interface with text/file input and example stories

## 🚀 Quick Start

### Prerequisites
- Python 3.11 or higher
- Google Gemini API key
- UV package manager (recommended) or pip

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/Shiva4113/MangakAI.git
   cd MangakAI
   ```

2. **Install dependencies**
   ```bash
   # Using UV (recommended)
   uv sync
   ```

3. **Set up environment variables**
   ```bash
   # Create .env file
   echo "GEMINI_API_KEY=your_gemini_api_key_here" > .env
   ```

4. **Run the application**
   ```bash
   uv run app.py
   ```

5. **Access the interface**
   Open your browser and navigate to `http://localhost:7860`

## 📖 Usage Guide

### 🖋️ **Generate Manga from Text**

1. Enter your story in the text area
2. Select number of scenes (1-10 panels)
3. Choose style preferences (optional)
4. Upload custom template (optional)
5. Click "Generate Manga"

### 📄 **Generate from File**

1. Upload a .txt story file
2. Configure settings and generate

### 🔄 **Regenerate Panels**

1. Select panel number to modify
2. Enter modification instructions
3. Upload reference image (optional)
4. Choose to replace original or keep both

### 📥 **Export as PDF**

1. Generate your manga first
2. Go to "Download PDF" tab and click "Create PDF"

## 🏗️ Project Structure

```
MangakAI/
├── app.py              # Main Gradio interface
├── manga.py            # Core manga generation logic
├── utils.py            # Utility functions and prompts
├── main.py             # Entry point
├── pyproject.toml      # Project configuration
├── .env               # Environment variables (create this)
├── data/
│   ├── examples/      # Example manga panels
│   │   ├── LittleLantern/
│   │   ├── PaperKite/
│   │   └── StrayPuppy/
│   ├── output/        # Generated manga panels
│   ├── stories/       # Story text files
│   └── templates/     # Panel templates
└── README.md
```

## 🛠️ Configuration

### Environment Variables

Create a `.env` file with the following variables:

```env
GEMINI_API_KEY=your_gemini_api_key_here
TEMPLATE_PATH=data/templates/template1.png
OUTPUT_DIR=data/output
STORIES_DIR=data/stories
IMAGE_MODEL_NAME=gemini-2.5-flash-image-preview
SCENE_MODEL_NAME=gemini-2.0-flash
```

### API Setup

1. **Get Gemini API Key**:
   - Visit [Google AI Studio](https://makersuite.google.com/app/apikey)
   - Create a new API key
   - Add it to your `.env` file

## 🎨 Style Options

Choose from various art styles (Traditional Manga, Shonen, Shoujo, Seinen, Chibi, Cyberpunk, Fantasy, Horror), moods (Epic, Dark, Light, Dramatic, Action-packed), color palettes, character styles, and composition options to create your unique manga aesthetic.

## 🔧 Advanced Features

- **Smart Prompts**: Analyzes story structure and maintains character consistency
- **Custom Templates**: Upload your own panel layouts with automatic AI adaptation
- **Reference Images**: Guide style, composition, and character appearance

## 📋 Examples

The project includes three example stories with generated panels:

1. **The Little Lantern**: A heartwarming tale of courage and kindness
2. **The Paper Kite**: A story about letting go and finding wonder
3. **The Stray Puppy**: A touching story of compassion and friendship



*Transform your imagination into visual stories with the power of AI!*