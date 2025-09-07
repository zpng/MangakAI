import os
import PIL
from io import BytesIO
from google import genai
from dotenv import load_dotenv
import pathlib
from utils import (
    get_scene_splitting_prompt, 
    get_panel_prompt, 
    SCENE_BREAK_DELIMITER,
    get_regeneration_prompt
)
import time
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
import shutil

# Load environment variables
load_dotenv()

class MangaGenerator:
    def __init__(self):
        """Initialize the manga generator with API clients and configuration."""
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.template_path = os.getenv("TEMPLATE_PATH", "data/templates/template.png")
        self.output_dir = os.getenv("OUTPUT_DIR", "data/output")
        self.stories_dir = os.getenv("STORIES_DIR", "data/stories")
        self.user_templates_dir = os.path.join(self.output_dir, "user_templates")
        self.user_references_dir = os.path.join(self.output_dir, "user_references")
        self.image_gen_model_name = os.getenv("IMAGE_MODEL_NAME", "gemini-2.5-flash-image-preview")
        self.scene_gen_model_name = os.getenv("SCENE_MODEL_NAME", "gemini-2.0-flash")
        
        # Initialize clients
        self.image_gen_client = genai.Client(api_key=self.api_key)
        self.scene_gen_client = genai.Client(api_key=self.api_key)
        
        # Ensure output directory exists
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.user_templates_dir, exist_ok=True)
        os.makedirs(self.user_references_dir, exist_ok=True)
        
        # Store current generation data for regeneration
        self.current_generation = {
            'scenes': [],
            'generated_images': [],
            'chat': None,
            'user_preferences': {},
            'current_template_path': self.template_path
        }

    def save_user_template(self, uploaded_file):
        """Save user uploaded template and return the path."""
        if uploaded_file is None:
            return None
        
        try:
            # Generate unique filename with timestamp
            import time
            timestamp = int(time.time())
            filename = f"user_template_{timestamp}.png"
            template_path = os.path.join(self.user_templates_dir, filename)
            
            # Handle different file input types
            if hasattr(uploaded_file, 'name'):  # Gradio file object
                # Copy the uploaded file to our template directory
                shutil.copy2(uploaded_file.name, template_path)
            else:
                # If it's already a PIL Image or path
                if isinstance(uploaded_file, str):
                    shutil.copy2(uploaded_file, template_path)
                elif hasattr(uploaded_file, 'save'):  # PIL Image
                    uploaded_file.save(template_path)
            
            # Verify the template was saved and is a valid image
            test_image = PIL.Image.open(template_path)
            test_image.verify()
            
            print(f"User template saved to: {template_path}")
            return template_path
            
        except Exception as e:
            print(f"Error saving user template: {e}")
            return None

    def save_user_reference_image(self, uploaded_file):
        """Save user uploaded reference image and return the path."""
        if uploaded_file is None:
            return None
        
        try:
            # Generate unique filename with timestamp
            import time
            timestamp = int(time.time())
            filename = f"user_reference_{timestamp}.png"
            reference_path = os.path.join(self.user_references_dir, filename)
            
            # Handle different file input types
            if hasattr(uploaded_file, 'name'):  # Gradio file object
                # Copy the uploaded file to our references directory
                shutil.copy2(uploaded_file.name, reference_path)
            else:
                # If it's already a PIL Image or path
                if isinstance(uploaded_file, str):
                    shutil.copy2(uploaded_file, reference_path)
                elif hasattr(uploaded_file, 'save'):  # PIL Image
                    uploaded_file.save(reference_path)
            
            # Verify the reference was saved and is a valid image
            test_image = PIL.Image.open(reference_path)
            test_image.verify()
            
            print(f"User reference image saved to: {reference_path}")
            return reference_path
            
        except Exception as e:
            print(f"Error saving user reference image: {e}")
            return None

    def set_template_for_generation(self, template_path):
        """Set the template to use for the current generation session."""
        if template_path and os.path.exists(template_path):
            self.current_generation['current_template_path'] = template_path
            return True
        return False

    def get_current_template_path(self):
        """Get the current template path being used."""
        return self.current_generation.get('current_template_path', self.template_path)

    def read_story(self, file_path):
        """Read story text from file."""
        with open(file_path, "r") as f:
            return f.read()

    def split_into_scenes(self, story_text: str, n_scenes: int):
        """Split story into visual scenes with descriptions."""
        prompt = get_scene_splitting_prompt(story_text, n_scenes)
        
        response = self.scene_gen_client.models.generate_content(
            model=self.scene_gen_model_name,
            contents=[prompt]
        )

        full_response_text = ""
        for part in response.candidates[0].content.parts:
            if part.text:
                full_response_text += part.text

        scenes = [scene.strip() for scene in full_response_text.split(SCENE_BREAK_DELIMITER)]
        scenes = [scene for scene in scenes if scene]

        return scenes[:n_scenes]

    def save_image(self, response, path):
        """Save the generated image from response."""
        time.sleep(3)
        for part in response.parts:
            if image := part.as_image():
                image.save(path)
                return image
        return None

    def generate_image_for_scene(self, scene_description: str, output_path: str):
        """Generate image for a single scene."""
        current_template = self.get_current_template_path()
        response = self.image_gen_client.models.generate_content(
            model=self.image_gen_model_name,
            contents=[
                scene_description,
                PIL.Image.open(current_template)
            ]
        )
        
        saved_image = self.save_image(response, output_path)
        return response, saved_image

    def generate_image_with_chat(self, scene_description: str, output_path: str, chat):
        """Generate image using chat context for consistency."""
        current_template = self.get_current_template_path()
        response = chat.send_message([
            scene_description,
            PIL.Image.open(current_template)
        ])
        
        saved_image = self.save_image(response, output_path)
        return response, saved_image

    def generate_image_with_chat_and_reference(self, scene_description: str, output_path: str, chat, reference_image_path=None):
        """Generate image using chat context with optional reference image."""
        current_template = self.get_current_template_path()
        
        # Build the content list with template and optional reference
        content = [scene_description, PIL.Image.open(current_template)]
        
        if reference_image_path and os.path.exists(reference_image_path):
            content.append(PIL.Image.open(reference_image_path))
            print(f"Using reference image: {reference_image_path}")
        
        response = chat.send_message(content)
        saved_image = self.save_image(response, output_path)
        return response, saved_image

    def regenerate_specific_panel(self, panel_index: int, modification_request: str, reference_image=None):
        """Regenerate a specific panel with modifications and optional reference image."""
        if not self.current_generation['scenes'] or not self.current_generation['chat']:
            raise ValueError("No active generation session. Please generate manga first.")
        
        if panel_index >= len(self.current_generation['scenes']):
            raise ValueError(f"Panel index {panel_index} is out of range.")
        
        # Get the original scene
        original_scene = self.current_generation['scenes'][panel_index]
        
        # Handle reference image if provided
        reference_image_path = None
        if reference_image is not None:
            reference_image_path = self.save_user_reference_image(reference_image)
            if reference_image_path:
                # Add reference image instruction to modification request
                modification_request += "\n\nIMPORTANT: Use the provided reference image as visual guidance for style, composition, or specific elements while maintaining the story's integrity."
        
        # Create modified prompt with user preferences
        user_preferences = self.current_generation.get('user_preferences', {})
        modified_prompt = get_regeneration_prompt(
            original_scene, 
            modification_request, 
            is_first_panel=(panel_index == 0),
            user_preferences=user_preferences
        )
        
        # Generate new image with versioning
        current_version = self.current_generation['generated_images'][panel_index].get('version', 1)
        output_path = os.path.join(self.output_dir, f"scene{panel_index+1}_v{current_version + 1}.png")
        
        # Use the new method that supports reference images
        response, saved_image = self.generate_image_with_chat_and_reference(
            modified_prompt, 
            output_path, 
            self.current_generation['chat'],
            reference_image_path
        )
        
        return output_path, saved_image

    def replace_panel(self, panel_index: int, new_image_path: str, new_image: PIL.Image):
        """Replace a panel in the current generation."""
        if not self.current_generation['generated_images']:
            raise ValueError("No active generation session.")
        
        if panel_index >= len(self.current_generation['generated_images']):
            raise ValueError(f"Panel index {panel_index} is out of range.")
        
        # Update the panel information
        current_version = self.current_generation['generated_images'][panel_index].get('version', 1)
        self.current_generation['generated_images'][panel_index].update({
            'image_path': new_image_path,
            'image': new_image,
            'version': current_version + 1
        })

    def get_current_gallery_paths(self):
        """Get current image paths for gallery display."""
        if not self.current_generation['generated_images']:
            return []
        return [img['image_path'] for img in self.current_generation['generated_images']]

    def generate_manga_from_story(self, story_text: str, n_scenes: int = 5, user_preferences: dict = None, user_template=None):
        """Generate complete manga from story text with user preferences and optional custom template."""
        # Handle user template upload
        if user_template is not None:
            template_path = self.save_user_template(user_template)
            if template_path:
                self.set_template_for_generation(template_path)
                print(f"Using user template: {template_path}")
            else:
                print("Failed to save user template, using default template")
        
        # Store user preferences
        if user_preferences is None:
            user_preferences = {}
        
        # Split story into scenes
        scenes = self.split_into_scenes(story_text, n_scenes)
        
        # Create chat for consistency across panels
        chat = self.image_gen_client.chats.create(model=self.image_gen_model_name)
        
        generated_images = []
        responses = []
        
        # Generate images for all scenes
        for i, scene in enumerate(scenes):
            # Use utility function to get appropriate prompt with user preferences
            scene_description = get_panel_prompt(scene, is_first_panel=(i == 0), user_preferences=user_preferences)
            
            output_path = os.path.join(self.output_dir, f"scene{i+1}.png")
            response, saved_image = self.generate_image_with_chat(scene_description, output_path, chat)
            
            responses.append(response)
            generated_images.append({
                'scene_number': i + 1,
                'scene_text': scene,
                'image_path': output_path,
                'image': saved_image,
                'version': 1
            })
            
            print(f"Generated scene {i+1}")
        
        # Store current generation for potential regeneration
        self.current_generation.update({
            'scenes': scenes,
            'generated_images': generated_images,
            'chat': chat,
            'user_preferences': user_preferences
        })
        
        return generated_images, scenes

    def generate_manga_from_file(self, story_file_path: str, n_scenes: int = 5, user_preferences: dict = None, user_template=None):
        """Generate manga from story file with user preferences and optional custom template."""
        story_text = self.read_story(story_file_path)
        return self.generate_manga_from_story(story_text, n_scenes, user_preferences, user_template)

    def get_current_panels(self):
        """Get current panel information for the interface."""
        if not self.current_generation['generated_images']:
            return []
        
        return [(i+1, img['image_path']) for i, img in enumerate(self.current_generation['generated_images'])]

    def create_manga_pdf(self, output_filename=None):
        """Create a PDF file from all current manga panels."""
        if not self.current_generation['generated_images']:
            raise ValueError("No manga panels to export. Please generate manga first.")
        
        if output_filename is None:
            output_filename = os.path.join(self.output_dir, "manga_complete.pdf")
        
        # Create PDF
        c = canvas.Canvas(output_filename, pagesize=A4)
        page_width, page_height = A4
        
        # Add title page
        c.setFont("Helvetica-Bold", 24)
        title_text = "Generated Manga"
        title_width = c.stringWidth(title_text, "Helvetica-Bold", 24)
        c.drawString((page_width - title_width) / 2, page_height - 100, title_text)
        
        c.setFont("Helvetica", 12)
        subtitle_text = f"Total Panels: {len(self.current_generation['generated_images'])}"
        subtitle_width = c.stringWidth(subtitle_text, "Helvetica", 12)
        c.drawString((page_width - subtitle_width) / 2, page_height - 130, subtitle_text)
        
        # Add template info if custom template was used
        current_template = self.get_current_template_path()
        if current_template != self.template_path:
            template_info = "Custom Template Used"
            template_width = c.stringWidth(template_info, "Helvetica", 12)
            c.drawString((page_width - template_width) / 2, page_height - 150, template_info)
        
        c.showPage()
        
        # Add each panel as a page
        for i, panel_data in enumerate(self.current_generation['generated_images']):
            image_path = panel_data['image_path']
            
            if os.path.exists(image_path):
                # Open and process image
                img = Image.open(image_path)
                
                # Calculate dimensions to fit page while maintaining aspect ratio
                img_width, img_height = img.size
                aspect_ratio = img_width / img_height
                
                # Set maximum dimensions (with margins)
                max_width = page_width - 100  # 50px margin on each side
                max_height = page_height - 150  # 75px margin top/bottom
                
                if aspect_ratio > 1:  # Landscape
                    new_width = min(max_width, img_width)
                    new_height = new_width / aspect_ratio
                else:  # Portrait
                    new_height = min(max_height, img_height)
                    new_width = new_height * aspect_ratio
                
                # Center the image on the page
                x = (page_width - new_width) / 2
                y = (page_height - new_height) / 2
                
                # Add image to PDF
                c.drawImage(image_path, x, y, width=new_width, height=new_height)
                
                # Add panel number
                c.setFont("Helvetica", 10)
                c.drawString(50, page_height - 30, f"Panel {i + 1}")
                
                c.showPage()
        
        c.save()
        print(f"PDF saved to: {output_filename}")
        return output_filename

# Global generator instance for interface functions
_global_generator = None

def get_global_generator():
    """Get or create the global generator instance."""
    global _global_generator
    if _global_generator is None:
        _global_generator = MangaGenerator()
    return _global_generator

def generate_manga_interface(story_text: str, num_scenes: int = 5, art_style: str = None, mood: str = None, 
                           color_palette: str = None, character_style: str = None, line_style: str = None,
                           composition: str = None, additional_notes: str = "", user_template=None):
    """Interface function for Gradio - generates manga from text input with user preferences and custom template."""
    generator = get_global_generator()
    try:
        # Build user preferences dictionary
        user_preferences = {}
        if art_style and art_style != "None":
            user_preferences['art_style'] = art_style
        if mood and mood != "None":
            user_preferences['mood'] = mood
        if color_palette and color_palette != "None":
            user_preferences['color_palette'] = color_palette
        if character_style and character_style != "None":
            user_preferences['character_style'] = character_style
        if line_style and line_style != "None":
            user_preferences['line_style'] = line_style
        if composition and composition != "None":
            user_preferences['composition'] = composition
        if additional_notes.strip():
            user_preferences['additional_notes'] = additional_notes.strip()
        
        generated_images, scenes = generator.generate_manga_from_story(story_text, num_scenes, user_preferences, user_template)
        
        # Return paths to generated images for Gradio display
        image_paths = [img['image_path'] for img in generated_images]
        scene_descriptions = [img['scene_text'] for img in generated_images]
        
        return image_paths, scene_descriptions
    except Exception as e:
        print(f"Error generating manga: {e}")
        return [], []

def generate_manga_from_file_interface(story_file, num_scenes: int = 5, art_style: str = None, mood: str = None,
                                     color_palette: str = None, character_style: str = None, line_style: str = None,
                                     composition: str = None, additional_notes: str = "", user_template=None):
    """Interface function for Gradio - generates manga from uploaded file with user preferences and custom template."""
    generator = get_global_generator()
    try:
        # Handle file reading
        if hasattr(story_file, 'name'):  # Gradio file object
            with open(story_file.name, 'r') as f:
                story_text = f.read()
        else:
            story_text = str(story_file)
        
        # Build user preferences dictionary
        user_preferences = {}
        if art_style and art_style != "None":
            user_preferences['art_style'] = art_style
        if mood and mood != "None":
            user_preferences['mood'] = mood
        if color_palette and color_palette != "None":
            user_preferences['color_palette'] = color_palette
        if character_style and character_style != "None":
            user_preferences['character_style'] = character_style
        if line_style and line_style != "None":
            user_preferences['line_style'] = line_style
        if composition and composition != "None":
            user_preferences['composition'] = composition
        if additional_notes.strip():
            user_preferences['additional_notes'] = additional_notes.strip()
            
        generated_images, scenes = generator.generate_manga_from_story(story_text, num_scenes, user_preferences, user_template)
        
        # Return paths to generated images for Gradio display
        image_paths = [img['image_path'] for img in generated_images]
        scene_descriptions = [img['scene_text'] for img in generated_images]
        
        return image_paths, scene_descriptions
    except Exception as e:
        print(f"Error generating manga: {e}")
        return [], []

def regenerate_panel_interface(panel_number: int, modification_request: str, reference_image=None):
    """Interface function for Gradio - regenerate specific panel with optional reference image."""
    generator = get_global_generator()
    try:
        if not modification_request.strip():
            return "Please provide modification instructions.", None
        
        panel_index = panel_number - 1  # Convert to 0-based index
        new_image_path, saved_image = generator.regenerate_specific_panel(panel_index, modification_request, reference_image)
        
        return f"Panel {panel_number} regenerated successfully!", new_image_path
    except Exception as e:
        return f"Error regenerating panel: {e}", None

def regenerate_and_replace_interface(panel_number: int, modification_request: str, replace_original: bool, reference_image=None):
    """Interface function for Gradio - regenerate panel with option to replace original and optional reference image."""
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
            generator.replace_panel(panel_index, new_image_path, saved_image)
            
            # Get all current image paths for the gallery
            updated_gallery = generator.get_current_gallery_paths()
            
            status_message = f"Panel {panel_number} regenerated and replaced successfully!"
        else:
            status_message = f"Panel {panel_number} regenerated successfully! (Original preserved)"
        
        return status_message, new_image_path, updated_gallery
        
    except Exception as e:
        return f"Error regenerating panel: {e}", None, []

def create_pdf_interface():
    """Interface function for Gradio - create PDF from current panels."""
    generator = get_global_generator()
    try:
        if not generator.current_generation['generated_images']:
            return "No manga panels to export. Please generate manga first.", None
        
        pdf_path = generator.create_manga_pdf()
        message = f"PDF created successfully! ({len(generator.current_generation['generated_images'])} panels)"
        
        return message, pdf_path
    except Exception as e:
        return f"Error creating PDF: {e}", None

def get_current_panels():
    """Get current panel information for the interface."""
    generator = get_global_generator()
    return generator.get_current_panels()
