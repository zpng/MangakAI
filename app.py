import gradio as gr
from manga import (
    generate_manga_interface, 
    generate_manga_from_file_interface,
    regenerate_panel_interface,
    get_current_panels,
    create_pdf_interface
)
from utils import ART_STYLES, MOOD_OPTIONS, COLOR_PALETTES, CHARACTER_STYLES, LINE_STYLES, COMPOSITION_STYLES
import os

# Define your example data
EXAMPLES = {
    "The Little Lantern": {
        "title": "The Little Lantern",
        "story": """In a small coastal village, where the sea whispered secrets to the shore, there lived a curious boy named Arun. Every evening, as the sun dipped behind the hills and the sky turned shades of orange and violet, Arun would carry his little lantern and sit on the rocks, watching the restless waves dance under the fading light.

His lantern was old, with a glass chimney slightly cracked, but Arun cared for it as if it were a treasure. "One day, this light will help someone," he would whisper to himself, as the sea breeze tousled his hair.

One night, the sky darkened earlier than usual. Thick clouds rolled in, and the wind began to howl like a wild beast. The sea churned, waves slamming against the shore with fierce force. Arun, worried, held his lantern tighter and scanned the horizon.

Suddenly, through the curtain of rain and spray, he spotted a small fishing boat tossed about by the waves, its lantern barely visible. The boat's crew struggled to control it, fear written on their faces.

Without a second thought, Arun jumped onto the rocks, his lantern held high above his head. "Here! This way!" he shouted through the roar of the wind and water.

The captain of the boat saw the glow and turned the vessel toward the shore. The villagers, alerted by Arun's brave signal, ran to the beach with ropes and nets. Together, they pulled the boat safely onto land.

The captain, drenched but smiling, knelt down and embraced Arun. "You saved us," he said. "Your little lantern became our lighthouse."

From that day forward, Arun's lantern became more than just an object—it became a symbol of courage and kindness. Every evening, Arun continued to sit by the sea, his light shining steadily. The villagers often gathered around him, sharing stories, laughter, and warmth. And whenever a storm brewed on the horizon, Arun's lantern stood as a reminder that even the smallest light, held with love, can brighten the darkest night.""",
        "panels": [
            "data/examples/LittleLantern/scene1.png",
            "data/examples/LittleLantern/scene2.png",
            "data/examples/LittleLantern/scene3.png",
            "data/examples/LittleLantern/scene4.png",
            "data/examples/LittleLantern/scene5.png"
        ]
    },
    "The Paper Kite": {
        "title": "The Paper Kite",
        "story": """Mira loved making kites. She would spend hours folding colorful paper, gluing tails, and tying strings until each kite looked perfect. Her favorite one was a bright red kite with golden edges that danced beautifully in the wind.

One afternoon, while flying it near the meadow, a sudden gust of wind tore the string and the kite soared away. Mira's heart sank as she watched it drift higher and higher, beyond the trees and far into the sky.

Feeling sad, she sat on a rock, staring at the empty sky. Just then, an old man passing by smiled gently. "Sometimes, letting go leads to something wonderful," he said.

The next morning, while walking through the meadow, Mira found her kite caught on a branch. But this time, instead of grabbing it, she smiled and left it there. She realized the wind had given her kite a chance to explore new heights.

From that day on, Mira made many more kites—not all stayed with her, but each one carried her dreams farther than she ever imagined.""",
        "panels": [
            "data/examples/PaperKite/scene1.png",
            "data/examples/PaperKite/scene2.png",
            "data/examples/PaperKite/scene3.png",
            "data/examples/PaperKite/scene4.png",
            "data/examples/PaperKite/scene5.png"
        ]
    },
    "The Stray Puppy": {
        "title": "The Stray Puppy",
        "story": """One chilly evening, as the sun was setting, Leo was walking home from school when he heard soft whimpering near the park bench. Curious, he peeked behind it and found a tiny, shivering puppy with big, sad eyes.

Leo gently picked it up and wrapped it in his jacket. The puppy licked his cheek as if thanking him. He took it home, gave it warm milk, and made a little bed from an old blanket.

The next day, Leo asked his neighbors if the puppy belonged to anyone, but no one came forward. So he decided to keep it and named it “Buddy.”""",
        "panels": [
            "data/examples/StrayPuppy/scene1.png",
            "data/examples/StrayPuppy/scene2.png",
            "data/examples/StrayPuppy/scene3.png",
            "data/examples/StrayPuppy/scene4.png"
        ]
    }
}

def load_example(example_name):
    """Load example data when user selects an example."""
    if example_name in EXAMPLES:
        example = EXAMPLES[example_name]
        # Filter panels to only include existing files
        existing_panels = [panel for panel in example["panels"] if os.path.exists(panel)]
        return example["title"], example["story"], existing_panels
    return "", "", []

def regenerate_and_replace_interface(panel_number: int, modification_request: str, replace_original: bool, reference_image=None):
    """Interface function for Gradio - regenerate panel with option to replace original and optional reference image."""
    from manga import get_global_generator
    
    generator = get_global_generator()
    try:
        if not modification_request.strip():
            return "Please provide modification instructions.", None, []
        
        panel_index = panel_number - 1  # Convert to 0-based index
        new_image_path, saved_image = generator.regenerate_specific_panel(panel_index, modification_request, reference_image)
        
        # If replace_original is True, update the main gallery
        updated_gallery = []
        if replace_original and generator.current_generation['generated_images']:
            # Replace the original panel in the current generation
            generator.current_generation['generated_images'][panel_index]['image_path'] = new_image_path
            generator.current_generation['generated_images'][panel_index]['image'] = saved_image
            generator.current_generation['generated_images'][panel_index]['version'] += 1
            
            # Get all current image paths for the gallery
            updated_gallery = [img['image_path'] for img in generator.current_generation['generated_images']]
            
            status_message = f"Panel {panel_number} regenerated and replaced successfully!"
        else:
            status_message = f"Panel {panel_number} regenerated successfully! (Original preserved)"
        
        return status_message, new_image_path, updated_gallery
        
    except Exception as e:
        return f"Error regenerating panel: {e}", None, []

def create_gradio_interface():
    with gr.Blocks(title="Manga Generator", theme=gr.themes.Soft()) as demo:
        gr.Markdown("# 📚 Story to Manga Generator")
        gr.Markdown("Transform your stories into manga panels with AI and custom style preferences!")
        
        with gr.Tab("📝 Generate Manga"):
            with gr.Tab("Text Input"):
                with gr.Row():
                    with gr.Column(scale=2):
                        story_input = gr.Textbox(
                            label="Enter your story", 
                            placeholder="Once upon a time...",
                            lines=10
                        )
                    with gr.Column(scale=1):
                        num_scenes_text = gr.Slider(
                            minimum=1, 
                            maximum=10, 
                            value=5,
                            step=1,
                            label="Number of Scenes"
                        )
                
                # Style Preferences Section
                gr.Markdown("### 🎨 Style Preferences")
                with gr.Row():
                    with gr.Column():
                        art_style_text = gr.Dropdown(
                            choices=["None"] + ART_STYLES,
                            value="None",
                            label="Art Style"
                        )
                        mood_text = gr.Dropdown(
                            choices=["None"] + MOOD_OPTIONS,
                            value="None",
                            label="Overall Mood"
                        )
                        color_palette_text = gr.Dropdown(
                            choices=["None"] + COLOR_PALETTES,
                            value="None",
                            label="Color Palette"
                        )
                    with gr.Column():
                        character_style_text = gr.Dropdown(
                            choices=["None"] + CHARACTER_STYLES,
                            value="None",
                            label="Character Style"
                        )
                        line_style_text = gr.Dropdown(
                            choices=["None"] + LINE_STYLES,
                            value="None",
                            label="Line Art Style"
                        )
                        composition_text = gr.Dropdown(
                            choices=["None"] + COMPOSITION_STYLES,
                            value="None",
                            label="Composition Style"
                        )
                
                additional_notes_text = gr.Textbox(
                    label="Additional Style Notes",
                    placeholder="Any specific style preferences, character descriptions, or artistic directions...",
                    lines=3
                )
                
                # Custom Template Upload Section
                gr.Markdown("### 📋 Custom Template (Optional)")
                gr.Markdown("*Upload your own manga panel template. If not provided, default template will be used.*")
                with gr.Row():
                    user_template_text = gr.File(
                        label="Upload Custom Template",
                        file_types=[".png", ".jpg", ".jpeg", ".webp"]
                    )
                
                gr.Markdown("**Template Guidelines:**")
                gr.Markdown("""
                - Use PNG format for best results
                - Template should have clear panel borders
                - Recommended size: 1024x1024 or higher
                - The AI will use your template as a guide for panel layout
                """)
                
                generate_btn = gr.Button("🎨 Generate Manga", variant="primary", size="lg")
                
                with gr.Row():
                    output_gallery = gr.Gallery(
                        label="Generated Manga Panels",
                        show_label=True,
                        elem_id="gallery",
                        columns=2,
                        rows=3,
                        height="auto"
                    )
                
                scene_output = gr.Textbox(
                    label="Scene Descriptions",
                    lines=5,
                    max_lines=10
                )
            
            with gr.Tab("File Upload"):
                with gr.Row():
                    with gr.Column(scale=2):
                        file_input = gr.File(
                            label="Upload Story File (.txt)",
                            file_types=[".txt"]
                        )
                    with gr.Column(scale=1):
                        num_scenes_file = gr.Slider(
                            minimum=1,
                            maximum=10, 
                            value=5,
                            step=1,
                            label="Number of Scenes"
                        )
                
                # Style Preferences Section for File Upload
                gr.Markdown("### 🎨 Style Preferences")
                with gr.Row():
                    with gr.Column():
                        art_style_file = gr.Dropdown(
                            choices=["None"] + ART_STYLES,
                            value="None",
                            label="Art Style"
                        )
                        mood_file = gr.Dropdown(
                            choices=["None"] + MOOD_OPTIONS,
                            value="None",
                            label="Overall Mood"
                        )
                        color_palette_file = gr.Dropdown(
                            choices=["None"] + COLOR_PALETTES,
                            value="None",
                            label="Color Palette"
                        )
                    with gr.Column():
                        character_style_file = gr.Dropdown(
                            choices=["None"] + CHARACTER_STYLES,
                            value="None",
                            label="Character Style"
                        )
                        line_style_file = gr.Dropdown(
                            choices=["None"] + LINE_STYLES,
                            value="None",
                            label="Line Art Style"
                        )
                        composition_file = gr.Dropdown(
                            choices=["None"] + COMPOSITION_STYLES,
                            value="None",
                            label="Composition Style"
                        )
                
                additional_notes_file = gr.Textbox(
                    label="Additional Style Notes",
                    placeholder="Any specific style preferences, character descriptions, or artistic directions...",
                    lines=3
                )
                
                # Custom Template Upload Section for File Upload
                gr.Markdown("### 📋 Custom Template (Optional)")
                gr.Markdown("*Upload your own manga panel template. If not provided, default template will be used.*")
                with gr.Row():
                    user_template_file = gr.File(
                        label="Upload Custom Template",
                        file_types=[".png", ".jpg", ".jpeg", ".webp"]
                    )
                
                generate_file_btn = gr.Button("🎨 Generate Manga from File", variant="primary", size="lg")
                
                with gr.Row():
                    output_gallery_file = gr.Gallery(
                        label="Generated Manga Panels",
                        show_label=True,
                        columns=2,
                        rows=3,
                        height="auto"
                    )
                
                scene_output_file = gr.Textbox(
                    label="Scene Descriptions",
                    lines=5,
                    max_lines=10
                )
        
        with gr.Tab("🔄 Regenerate Panels"):
            gr.Markdown("### Select a panel to regenerate with modifications")
            gr.Markdown("**Note:** You must generate manga first before you can regenerate panels.")
            
            with gr.Row():
                with gr.Column(scale=1):
                    panel_selector = gr.Number(
                        label="Panel Number to Regenerate",
                        value=1,
                        minimum=1,
                        maximum=10,
                        precision=0
                    )
                    
                    modification_input = gr.Textbox(
                        label="Modification Instructions",
                        placeholder="e.g., 'Make the lighting more dramatic', 'Change character expression to angry', 'Add more action lines'",
                        lines=3
                    )
                    
                    # Reference Image Upload Section
                    gr.Markdown("### 🖼️ Reference Image (Optional)")
                    gr.Markdown("*Upload an image to guide the regeneration style, composition, or specific elements*")
                    reference_image_upload = gr.File(
                        label="Upload Reference Image",
                        file_types=[".png", ".jpg", ".jpeg", ".webp"]
                    )
                    
                    replace_checkbox = gr.Checkbox(
                        label="Replace original panel",
                        value=False
                    )
                    gr.Markdown("*Check this to replace the original panel in the main gallery*")
                    
                    regenerate_btn = gr.Button("🔄 Regenerate Panel", variant="secondary", size="lg")
                
                with gr.Column(scale=2):
                    regenerated_image = gr.Image(
                        label="Regenerated Panel",
                        show_label=True
                    )
            
            regeneration_status = gr.Textbox(
                label="Status",
                interactive=False
            )
            
            # Updated main gallery display (shows when panels are replaced)
            with gr.Row():
                updated_main_gallery = gr.Gallery(
                    label="Updated Main Gallery (when replacing panels)",
                    show_label=True,
                    columns=2,
                    rows=3,
                    height="auto",
                    visible=False
                )
            
            gr.Markdown("### Reference Image Guidelines:")
            gr.Markdown("""
            - **Style Reference**: Upload an image with the art style you want to emulate
            - **Composition Reference**: Show the camera angle, pose, or layout you prefer
            - **Color Reference**: Provide color palette or lighting inspiration
            - **Character Reference**: Show specific character appearances or expressions
            - **Environment Reference**: Demonstrate background or setting elements
            """)
            
            gr.Markdown("### Common Modification Examples:")
            gr.Markdown("""
            - **Lighting**: "Make it darker with more shadows", "Add bright sunlight", "Create moody twilight atmosphere"
            - **Character**: "Make character look more angry", "Change pose to defensive stance", "Add more detailed facial expression"
            - **Composition**: "Change to close-up shot", "Make it a wide establishing shot", "Add more dynamic camera angle"
            - **Style**: "Add more action lines", "Make it more dramatic", "Simplify the background"
            - **Details**: "Add more environmental details", "Remove background clutter", "Focus more on the character"
            """)
            
            gr.Markdown("### Replace Panel Option:")
            gr.Markdown("""
            - **Unchecked**: The regenerated panel is shown separately, original is preserved
            - **Checked**: The regenerated panel replaces the original in the main gallery
            """)
        
        with gr.Tab("📥 Download PDF"):
            gr.Markdown("### Export your manga as a PDF")
            gr.Markdown("**Note:** You must generate manga first before you can create a PDF.")
            
            with gr.Row():
                with gr.Column(scale=1):
                    create_pdf_btn = gr.Button("📥 Create PDF", variant="primary", size="lg")
                
                with gr.Column(scale=2):
                    pdf_status = gr.Textbox(
                        label="Status",
                        interactive=False
                    )
                    
                    download_pdf = gr.File(
                        label="Download PDF",
                        visible=False
                    )
            
            gr.Markdown("### PDF Features:")
            gr.Markdown("""
            - **A4 format** with proper margins and professional layout
            - **One panel per page** with panel numbering
            - **Title page** with manga information
            - **Custom template notation** if user template was used
            - **Automatic image scaling** to fit pages while maintaining aspect ratio
            """)
        
        with gr.Tab("🎯 Examples"):
            gr.Markdown("### Explore Example Stories and Manga")
            gr.Markdown("Select from our curated examples to see how stories transform into manga panels!")
            
            with gr.Row():
                with gr.Column(scale=1):
                    example_selector = gr.Dropdown(
                        choices=list(EXAMPLES.keys()),
                        label="Select Example",
                        value=list(EXAMPLES.keys())[0] if EXAMPLES else None
                    )
                    
                    example_title = gr.Textbox(
                        label="Story Title",
                        interactive=False,
                        lines=1
                    )
                    
                    example_story = gr.Textbox(
                        label="Story Text",
                        interactive=False,
                        lines=8,
                        max_lines=12
                    )
                
                with gr.Column(scale=2):
                    example_gallery = gr.Gallery(
                        label="Manga Panels",
                        show_label=True,
                        columns=2,
                        rows=3,
                        height="auto"
                    )
            
            gr.Markdown("### How It Works:")
            gr.Markdown("""
            1. **Select an Example**: Choose from the dropdown above
            2. **View the Story**: Read the original story text
            3. **See the Manga**: Observe how AI transforms text into visual panels
            4. **Try Your Own**: Use the "Generate Manga" tab to create your own!
            """)
            
            # Load first example by default
            def load_first_example():
                if EXAMPLES:
                    first_key = list(EXAMPLES.keys())[0]
                    return load_example(first_key)
                return "", "", []
            
            # Event handler for example selection
            example_selector.change(
                fn=load_example,
                inputs=[example_selector],
                outputs=[example_title, example_story, example_gallery]
            )
        
        # Helper function to update gallery visibility
        def update_gallery_visibility(gallery_images):
            if gallery_images:
                return gr.Gallery(visible=True, value=gallery_images)
            else:
                return gr.Gallery(visible=False)
        
        # Helper function to handle PDF creation and make file available for download
        def create_and_provide_pdf():
            status, pdf_path = create_pdf_interface()
            if pdf_path:
                return status, gr.File(value=pdf_path, visible=True)
            else:
                return status, gr.File(visible=False)
        
        # Event handlers
        generate_btn.click(
            fn=generate_manga_interface,
            inputs=[story_input, num_scenes_text, art_style_text, mood_text, color_palette_text, 
                   character_style_text, line_style_text, composition_text, additional_notes_text, user_template_text],
            outputs=[output_gallery, scene_output]
        )
        
        generate_file_btn.click(
            fn=generate_manga_from_file_interface,
            inputs=[file_input, num_scenes_file, art_style_file, mood_file, color_palette_file,
                   character_style_file, line_style_file, composition_file, additional_notes_file, user_template_file],
            outputs=[output_gallery_file, scene_output_file]
        )
        
        regenerate_btn.click(
            fn=regenerate_and_replace_interface,
            inputs=[panel_selector, modification_input, replace_checkbox, reference_image_upload],
            outputs=[regeneration_status, regenerated_image, updated_main_gallery]
        ).then(
            fn=update_gallery_visibility,
            inputs=[updated_main_gallery],
            outputs=[updated_main_gallery]
        )
        
        create_pdf_btn.click(
            fn=create_and_provide_pdf,
            outputs=[pdf_status, download_pdf]
        )
        
        # Load first example on startup
        demo.load(
            fn=load_first_example,
            outputs=[example_title, example_story, example_gallery]
        )
    
    return demo

if __name__ == "__main__":
    demo = create_gradio_interface()
    demo.launch(share=True, server_name="0.0.0.0", server_port=7860)