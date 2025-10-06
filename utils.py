"""
Utility functions and constants for MangakAI
"""
import uuid
import time
import random
import string

# Art style options
ART_STYLES = [
    "None",
    "Anime/Manga",
    "Realistic",
    "Cartoon",
    "Watercolor",
    "Oil Painting",
    "Sketch",
    "Digital Art",
    "Minimalist",
    "Vintage",
    "Comic Book"
]

# Mood options
MOOD_OPTIONS = [
    "None",
    "Happy",
    "Sad",
    "Mysterious",
    "Adventurous",
    "Romantic",
    "Dark",
    "Peaceful",
    "Energetic",
    "Nostalgic",
    "Dramatic"
]

# Color palette options
COLOR_PALETTES = [
    "None",
    "Vibrant",
    "Pastel",
    "Monochrome",
    "Warm Tones",
    "Cool Tones",
    "Earth Tones",
    "Neon",
    "Sepia",
    "Black and White",
    "Sunset Colors"
]

# Character style options
CHARACTER_STYLES = [
    "None",
    "Realistic Proportions",
    "Chibi/Cute",
    "Heroic/Muscular",
    "Elegant/Graceful",
    "Cartoonish",
    "Detailed Faces",
    "Simple/Minimalist",
    "Expressive Eyes",
    "Dynamic Poses"
]

# Line style options
LINE_STYLES = [
    "None",
    "Clean Lines",
    "Sketchy",
    "Bold Outlines",
    "Soft Lines",
    "Detailed Linework",
    "Minimal Lines",
    "Crosshatching",
    "Smooth Curves",
    "Sharp Angles"
]

# Composition options
COMPOSITION_STYLES = [
    "None",
    "Close-up",
    "Wide Shot",
    "Action Scene",
    "Portrait Style",
    "Landscape View",
    "Dynamic Angle",
    "Centered Composition",
    "Rule of Thirds",
    "Dramatic Perspective"
]

# Scene break delimiter for story splitting
SCENE_BREAK_DELIMITER = "---SCENE_BREAK---"

def generate_session_id() -> str:
    """
    Generate a unique session ID
    """
    timestamp = str(int(time.time()))
    random_part = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return f"session_{timestamp}_{random_part}"

def generate_task_id() -> str:
    """
    Generate a unique task ID
    """
    return str(uuid.uuid4())

def get_scene_splitting_prompt(story_text: str, n_scenes: int) -> str:
    """
    Generate prompt for splitting story into scenes
    """
    return f"""
Please analyze the following story and split it into exactly {n_scenes} distinct scenes for a manga/comic adaptation.

Story:
{story_text}

Requirements:
1. Each scene should be a complete moment or action that can be visualized as a single manga panel
2. Scenes should flow logically and maintain story continuity
3. Include key visual elements, character actions, and emotional moments
4. Each scene should be detailed enough for AI image generation
5. Separate each scene with "{SCENE_BREAK_DELIMITER}"

Format your response as:
Scene 1 description
{SCENE_BREAK_DELIMITER}
Scene 2 description
{SCENE_BREAK_DELIMITER}
...and so on for all {n_scenes} scenes.

Make sure each scene description is vivid and includes:
- Character positions and expressions
- Setting and background details
- Key objects or props
- Mood and atmosphere
- Any important visual elements that advance the story
"""

def get_panel_prompt(scene_description: str, user_preferences: dict = None, is_first_panel: bool = False) -> str:
    """
    Generate enhanced prompt for manga panel generation
    """
    base_prompt = f"""
Create a manga/comic panel for the following scene:

{scene_description}

Style requirements:
- Manga/anime art style
- Clear composition suitable for a comic panel
- Expressive characters with detailed faces
- Dynamic visual storytelling
"""
    
    if is_first_panel:
        base_prompt += "\n- This is the opening panel, make it engaging and set the scene"
    
    if user_preferences:
        if user_preferences.get('art_style') and user_preferences['art_style'] != 'None':
            base_prompt += f"\n- Art style: {user_preferences['art_style']}"
        
        if user_preferences.get('mood') and user_preferences['mood'] != 'None':
            base_prompt += f"\n- Mood: {user_preferences['mood']}"
        
        if user_preferences.get('color_palette') and user_preferences['color_palette'] != 'None':
            base_prompt += f"\n- Color palette: {user_preferences['color_palette']}"
        
        if user_preferences.get('character_style') and user_preferences['character_style'] != 'None':
            base_prompt += f"\n- Character style: {user_preferences['character_style']}"
        
        if user_preferences.get('line_style') and user_preferences['line_style'] != 'None':
            base_prompt += f"\n- Line style: {user_preferences['line_style']}"
        
        if user_preferences.get('composition') and user_preferences['composition'] != 'None':
            base_prompt += f"\n- Composition: {user_preferences['composition']}"
        
        if user_preferences.get('additional_notes'):
            base_prompt += f"\n- Additional notes: {user_preferences['additional_notes']}"
    
    return base_prompt

def get_regeneration_prompt(original_scene: str, modification_request: str, is_first_panel: bool = False, user_preferences: dict = None) -> str:
    """
    Generate prompt for panel regeneration with modifications
    """
    base_prompt = f"""
Regenerate this manga panel with the following modifications:

Original scene: {original_scene}

Modification request: {modification_request}

Please maintain the core story elements while incorporating the requested changes.
"""
    
    # Add user preferences if available
    enhanced_prompt = get_panel_prompt(base_prompt, user_preferences, is_first_panel)
    
    return enhanced_prompt

def validate_story_text(story_text: str) -> tuple[bool, str]:
    """
    Validate story text input
    """
    if not story_text or not story_text.strip():
        return False, "故事内容不能为空"
    
    if len(story_text.strip()) < 50:
        return False, "故事内容太短，请提供更详细的故事"
    
    if len(story_text) > 10000:
        return False, "故事内容太长，请控制在10000字符以内"
    
    return True, "验证通过"

def validate_num_scenes(num_scenes: int) -> tuple[bool, str]:
    """
    Validate number of scenes
    """
    if not isinstance(num_scenes, int):
        return False, "场景数量必须是整数"
    
    if num_scenes < 1:
        return False, "场景数量不能少于1个"
    
    if num_scenes > 10:
        return False, "场景数量不能超过10个"
    
    return True, "验证通过"

def format_error_message(error: Exception) -> str:
    """
    Format error message for user display
    """
    error_str = str(error)
    
    # Common error mappings
    error_mappings = {
        "API key": "API密钥错误，请检查配置",
        "quota": "API配额不足，请稍后重试",
        "network": "网络连接错误，请检查网络",
        "timeout": "请求超时，请重试",
        "rate limit": "请求频率过高，请稍后重试"
    }
    
    for key, message in error_mappings.items():
        if key.lower() in error_str.lower():
            return message
    
    return f"处理失败: {error_str}"

def get_file_extension(filename: str) -> str:
    """
    Get file extension from filename
    """
    return filename.split('.')[-1].lower() if '.' in filename else ''

def is_valid_image_file(filename: str) -> bool:
    """
    Check if file is a valid image
    """
    valid_extensions = ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp']
    return get_file_extension(filename) in valid_extensions

def is_valid_text_file(filename: str) -> bool:
    """
    Check if file is a valid text file
    """
    valid_extensions = ['txt', 'md', 'rtf']
    return get_file_extension(filename) in valid_extensions

def truncate_text(text: str, max_length: int = 100) -> str:
    """
    Truncate text to specified length
    """
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."

def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename for safe storage
    """
    # Remove or replace unsafe characters
    unsafe_chars = '<>:"/\\|?*'
    for char in unsafe_chars:
        filename = filename.replace(char, '_')
    
    # Limit length
    if len(filename) > 255:
        name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
        max_name_length = 255 - len(ext) - 1
        filename = name[:max_name_length] + ('.' + ext if ext else '')
    
    return filename