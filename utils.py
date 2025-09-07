"""
Utility functions and prompt templates for manga generation.
"""

def get_scene_splitting_prompt(story_text: str, n_scenes: int) -> str:
    """Generate the prompt for splitting a story into scenes."""
    return f"""
    Act as a master film director and veteran comic book artist, with an exceptional eye for cinematic composition and dramatic effect. Your task is to read the following story and transmute it into {n_scenes} distinct, visually-dense scene descriptions, including key dialogues and a reference to the original text.

    The goal is to create a powerful visual description for each scene that can be used directly as a prompt for an AI image generator, while also capturing the most important lines spoken and preserving the source text.

    **STORY:**
    {story_text}

    ---

    **CRITICAL INSTRUCTIONS FOR EACH SCENE'S DESCRIPTION:**
    - **Reference the Source:** In the 'Original Scene Text' field, you must include the exact, unaltered passage from the story that you are adapting for this scene.
    - **Be the Camera:** Describe the scene as if looking through a camera lens. Explicitly mention the shot type (e.g., wide shot, extreme close-up, over-the-shoulder), camera angle, and the composition of elements.
    - **Paint the Atmosphere:** Weave together the setting, time of day, weather, and mood. Use lighting (e.g., "harsh neon glare," "soft morning light," "dramatic chiaroscuro shadows") to establish the tone.
    - **Focus on the Subject:** Detail the characters' specific poses, actions, and intense facial expressions. Describe their clothing and how it interacts with their actions and the environment (e.g., "a rain-soaked cloak clinging to their frame," "wind-whipped hair").
    - **Emphasize the Core Moment:** Ensure the description builds towards the single most important visual element, action, or emotional beat in the scene.
    - **Isolate Key Dialogue:** If the scene contains crucial, plot-advancing dialogue, extract the most impactful line(s) verbatim.

    **OUTPUT FORMAT:**
    You must use the following format. Separate each scene block with '---SCENE_BREAK---'.

    **Scene:** [Scene Number]
    **Original Scene Text:** [The exact, unaltered passage from the story for this scene.]
    **Visual Description:** [A single, comprehensive paragraph combining all the visual instructions. This must be a self-contained prompt for an image model. **DO NOT include dialogue here**.]
    **Key Dialogue:** [The most important line(s) of dialogue from the scene. If there is no dialogue, write 'None'.]
    ---SCENE_BREAK---
    """

def get_first_panel_prompt(scene: str, user_preferences: dict = None) -> str:
    """Generate the prompt for the first manga panel."""
    style_instructions = get_style_instructions(user_preferences) if user_preferences else ""
    
    return f"""
    **Act as a master mangaka creating the first panel of a new manga.**

    **YOUR TASK:** Create a visually stunning manga page based on the scene description below. You have two creative options:

    1.  **USE A TEMPLATE:** Choose ONE of the three provided panel templates. Your illustration must perfectly integrate into the chosen panel's borders, using its layout as the foundation for a dynamic composition.
    
    2.  **CREATE A SPLASH PAGE:** If the scene is a powerful establishing shot or a highly dramatic moment, you may ignore the templates and create a full-page, borderless splash image that captures the full impact of the scene.

    **CRITICAL:** You must adhere strictly to the visual details in the scene description.
    - **Style:** The art style, line weight, and shading must remain consistent.
    - **Original Story:** Do not deviate from the original story text. Every scene must accurately reflect the source material as well.
    - **Ensure that there is no repetition of scenes. Each panel must advance the story.**
    - **If the scene contains dialogue, include the exact lines in speech bubbles.**
    - **Create multiple panels per page to maintain pacing.**
    - **Include good story narration boxes so the reader can follow the story.**

    {style_instructions}
    
    ---
    **SCENE DESCRIPTION:**
    {scene}
    """

def get_subsequent_panel_prompt(scene: str, user_preferences: dict = None) -> str:
    """Generate the prompt for subsequent manga panels."""
    style_instructions = get_style_instructions(user_preferences) if user_preferences else ""
    
    return f"""
    **Act as a master mangaka continuing a manga sequence.**

    **YOUR TASK:** Create the next manga page, ensuring it flows perfectly from the previous panel. You have two creative options:

    1.  **USE A TEMPLATE:** Choose ONE of the three provided panel templates to best fit the action. Your illustration must integrate perfectly into the chosen panel's borders.
    
    2.  **CREATE A SPLASH PAGE:** If this scene is a major climax or a dramatic shift, you may ignore the templates and create a full-page, borderless splash image.

    **CRITICAL - MAINTAIN VISUAL CONTINUITY:**
    - **Characters:** Must have the exact same appearance, clothing, and features as the previous panel.
    - **Style:** The art style, line weight, and shading must remain consistent.
    - **Environment:** The setting and lighting must logically follow the previous panel.
    - **Original Story:** Do not deviate from the original story text. Every scene must accurately reflect the source material as well.
    - **Ensure that there is no repetition of scenes. Each panel must advance the story.**
    - **If the scene contains dialogue, include the exact lines in speech bubbles.**
    - **Create multiple panels per page to maintain pacing.**
    - **Include good story narration boxes so the reader can follow the story.**

    {style_instructions}
    
    ---
    **SCENE DESCRIPTION:**
    {scene}
    """

def get_panel_prompt(scene: str, is_first_panel: bool = False, user_preferences: dict = None) -> str:
    """Get the appropriate panel prompt based on whether it's the first panel or not."""
    if is_first_panel:
        return get_first_panel_prompt(scene, user_preferences)
    else:
        return get_subsequent_panel_prompt(scene, user_preferences)

def get_regeneration_prompt(original_scene: str, modification_request: str, is_first_panel: bool = False, user_preferences: dict = None) -> str:
    """Generate prompt for regenerating a panel with modifications."""
    base_instruction = get_first_panel_prompt(original_scene, user_preferences) if is_first_panel else get_subsequent_panel_prompt(original_scene, user_preferences)
    
    return f"""
    {base_instruction}

    ---
    **MODIFICATION REQUEST:**
    The user has requested the following changes to this panel:
    {modification_request}

    **CRITICAL:** Incorporate these modifications while maintaining all other aspects of the original scene description and ensuring visual continuity with the manga sequence.
    """

def get_style_instructions(user_preferences: dict) -> str:
    """Generate style instructions based on user preferences."""
    if not user_preferences:
        return ""
    
    instructions = "\n**USER STYLE PREFERENCES:**"
    
    if user_preferences.get('art_style'):
        instructions += f"\n- **Art Style:** {user_preferences['art_style']}"
    
    if user_preferences.get('mood'):
        instructions += f"\n- **Overall Mood:** {user_preferences['mood']}"
    
    if user_preferences.get('color_palette'):
        instructions += f"\n- **Color Palette:** {user_preferences['color_palette']}"
    
    if user_preferences.get('character_style'):
        instructions += f"\n- **Character Design:** {user_preferences['character_style']}"
    
    if user_preferences.get('line_style'):
        instructions += f"\n- **Line Art Style:** {user_preferences['line_style']}"
    
    if user_preferences.get('composition'):
        instructions += f"\n- **Composition Preference:** {user_preferences['composition']}"
    
    if user_preferences.get('additional_notes'):
        instructions += f"\n- **Additional Notes:** {user_preferences['additional_notes']}"
    
    instructions += "\n\n**CRITICAL:** Incorporate ALL these style preferences while maintaining the story integrity, visual continuity, and all the requirements above."
    
    return instructions

# Constants
SCENE_BREAK_DELIMITER = "---SCENE_BREAK---"

# Pre-defined style options for the interface
ART_STYLES = [
    "Traditional Manga/Anime",
    "Shonen (Bold, Dynamic)",
    "Shoujo (Soft, Romantic)",
    "Seinen (Mature, Detailed)",
    "Chibi (Cute, Simplified)",
    "Realistic",
    "Semi-Realistic",
    "Minimalist",
    "Dark/Gothic",
    "Cyberpunk",
    "Fantasy",
    "Horror",
    "Comedy/Cartoon"
]

MOOD_OPTIONS = [
    "Epic/Heroic",
    "Dark/Mysterious",
    "Light/Cheerful",
    "Dramatic/Intense",
    "Romantic",
    "Action-Packed",
    "Peaceful/Serene",
    "Suspenseful",
    "Melancholic",
    "Whimsical"
]

COLOR_PALETTES = [
    "Full Color",
    "Black and White",
    "Sepia/Vintage",
    "Monochromatic Blue",
    "Monochromatic Red",
    "Warm Tones",
    "Cool Tones",
    "High Contrast",
    "Pastel Colors",
    "Neon/Vibrant"
]

CHARACTER_STYLES = [
    "Detailed/Realistic",
    "Stylized/Expressive",
    "Simple/Clean",
    "Muscular/Athletic",
    "Elegant/Graceful",
    "Cute/Moe",
    "Mature/Adult",
    "Young/Teen",
    "Fantasy/Otherworldly"
]

LINE_STYLES = [
    "Clean/Precise",
    "Rough/Sketchy",
    "Bold/Thick",
    "Fine/Delicate",
    "Variable Weight",
    "Minimalist",
    "Detailed/Complex"
]

COMPOSITION_STYLES = [
    "Dynamic/Action",
    "Balanced/Stable",
    "Asymmetrical",
    "Close-up Focus",
    "Wide/Environmental",
    "Dramatic Angles",
    "Traditional/Conservative"
]

# Optional: Additional utility functions for prompt customization
def customize_scene_prompt(base_prompt: str, **kwargs) -> str:
    """Allow for dynamic prompt customization if needed."""
    return base_prompt.format(**kwargs)

def get_style_modifiers() -> dict:
    """Return common style modifiers that can be added to prompts."""
    return {
        "manga_style": "in traditional manga/anime art style with clean line art and dynamic compositions",
        "dark_theme": "with dark, moody atmosphere and dramatic shadows",
        "action_focus": "emphasizing dynamic action and movement",
        "character_focus": "with detailed character expressions and emotions",
        "cinematic": "with cinematic camera angles and professional composition"
    }