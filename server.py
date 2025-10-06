import logging
import os
import shutil
import tempfile
from typing import Optional, List

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from api.async_manga import router as async_manga_router
from api.websocket import router as websocket_router
# Import new async components
from database import init_db, check_db_connection
# Import legacy components for backward compatibility
from manga import (
    generate_manga_interface,
    generate_manga_from_file_interface,
    regenerate_panel_interface,
    get_current_panels,
    create_pdf_interface,
    get_global_generator
)
from utils import ART_STYLES, MOOD_OPTIONS, COLOR_PALETTES, CHARACTER_STYLES, LINE_STYLES, COMPOSITION_STYLES

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="MangakAI API",
    description="Transform your stories into manga panels with AI - Now with async processing!",
    version="2.0.0"
)

# CORS middleware to allow frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include new async routers
app.include_router(websocket_router)
app.include_router(async_manga_router)

# Serve static files (generated images, etc.)
app.mount("/static", StaticFiles(directory="data"), name="static")


# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    """Initialize application on startup"""
    try:
        # Check database connection
        if check_db_connection():
            logger.info("Database connection successful")
            # Initialize database tables
            init_db()
            logger.info("Database initialized successfully")
        else:
            logger.error("Database connection failed")
    except Exception as e:
        logger.error(f"Startup error: {str(e)}")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Application shutting down")


# Health check endpoints
@app.get("/health")
async def health_check():
    """Application health check"""
    db_healthy = check_db_connection()

    return {
        "status": "healthy" if db_healthy else "unhealthy",
        "database": "connected" if db_healthy else "disconnected",
        "version": "2.0.0"
    }


@app.get("/ready")
async def readiness_check():
    """Readiness check for Kubernetes"""
    db_healthy = check_db_connection()

    if not db_healthy:
        raise HTTPException(status_code=503, detail="Database not ready")

    return {"status": "ready"}


# Legacy API endpoints for backward compatibility

# Pydantic models for request/response
class GenerateMangaRequest(BaseModel):
    story_text: str
    num_scenes: int = 5
    art_style: Optional[str] = None
    mood: Optional[str] = None
    color_palette: Optional[str] = None
    character_style: Optional[str] = None
    line_style: Optional[str] = None
    composition: Optional[str] = None
    additional_notes: str = ""


class RegeneratePanelRequest(BaseModel):
    panel_number: int
    modification_request: str
    replace_original: bool = False


class MangaResponse(BaseModel):
    success: bool
    message: str
    gallery_images: List[str] = []
    scene_descriptions: str = ""


class PanelResponse(BaseModel):
    success: bool
    message: str
    regenerated_image: Optional[str] = None
    updated_gallery: List[str] = []


class PDFResponse(BaseModel):
    success: bool
    message: str
    pdf_path: Optional[str] = None


class StyleOptionsResponse(BaseModel):
    art_styles: List[str]
    mood_options: List[str]
    color_palettes: List[str]
    character_styles: List[str]
    line_styles: List[str]
    composition_styles: List[str]


class ExampleResponse(BaseModel):
    title: str
    story: str
    panels: List[str]


# Example data
EXAMPLES = {
    "The Little Lantern": {
        "title": "The Little Lantern",
        "story": "In a small coastal village, where the sea whispered secrets to the shore, there lived a curious boy named Arun. Every evening, as the sun dipped behind the hills and the sky turned shades of orange and violet, Arun would carry his little lantern and sit on the rocks, watching the restless waves dance under the fading light. His lantern was old, with a glass chimney slightly cracked, but Arun cared for it as if it were a treasure. One day, this light will help someone, he would whisper to himself, as the sea breeze tousled his hair. One night, the sky darkened earlier than usual. Thick clouds rolled in, and the wind began to howl like a wild beast. The sea churned, waves slamming against the shore with fierce force. Arun, worried, held his lantern tighter and scanned the horizon. Suddenly, through the curtain of rain and spray, he spotted a small fishing boat tossed about by the waves, its lantern barely visible. The boat's crew struggled to control it, fear written on their faces. Without a second thought, Arun jumped onto the rocks, his lantern held high above his head. Here! This way! he shouted through the roar of the wind and water. The captain of the boat saw the glow and turned the vessel toward the shore. The villagers, alerted by Arun's brave signal, ran to the beach with ropes and nets. Together, they pulled the boat safely onto land. The captain, drenched but smiling, knelt down and embraced Arun. You saved us, he said. Your little lantern became our lighthouse. From that day forward, Arun's lantern became more than just an object—it became a symbol of courage and kindness. Every evening, Arun continued to sit by the sea, his light shining steadily. The villagers often gathered around him, sharing stories, laughter, and warmth. And whenever a storm brewed on the horizon, Arun's lantern stood as a reminder that even the smallest light, held with love, can brighten the darkest night.",
        "panels": [
            "/static/examples/LittleLantern/scene1.png",
            "/static/examples/LittleLantern/scene2.png",
            "/static/examples/LittleLantern/scene3.png",
            "/static/examples/LittleLantern/scene4.png",
            "/static/examples/LittleLantern/scene5.png"
        ]
    },
    "The Paper Kite": {
        "title": "The Paper Kite",
        "story": "Mira loved making kites. She would spend hours folding colorful paper, gluing tails, and tying strings until each kite looked perfect. Her favorite one was a bright red kite with golden edges that danced beautifully in the wind. One afternoon, while flying it near the meadow, a sudden gust of wind tore the string and the kite soared away. Mira's heart sank as she watched it drift higher and higher, beyond the trees and far into the sky. Feeling sad, she sat on a rock, staring at the empty sky. Just then, an old man passing by smiled gently. Sometimes, letting go leads to something wonderful, he said. The next morning, while walking through the meadow, Mira found her kite caught on a branch. But this time, instead of grabbing it, she smiled and left it there. She realized the wind had given her kite a chance to explore new heights. From that day on, Mira made many more kites—not all stayed with her, but each one carried her dreams farther than she ever imagined.",
        "panels": [
            "/static/examples/PaperKite/scene1.png",
            "/static/examples/PaperKite/scene2.png",
            "/static/examples/PaperKite/scene3.png",
            "/static/examples/PaperKite/scene4.png",
            "/static/examples/PaperKite/scene5.png"
        ]
    },
    "The Stray Puppy": {
        "title": "The Stray Puppy",
        "story": "One chilly evening, as the sun was setting, Leo was walking home from school when he heard soft whimpering near the park bench. Curious, he peeked behind it and found a tiny, shivering puppy with big, sad eyes. Leo gently picked it up and wrapped it in his jacket. The puppy licked his cheek as if thanking him. He took it home, gave it warm milk, and made a little bed from an old blanket. The next day, Leo asked his neighbors if the puppy belonged to anyone, but no one came forward. So he decided to keep it and named it Buddy.",
        "panels": [
            "/static/examples/StrayPuppy/scene1.png",
            "/static/examples/StrayPuppy/scene2.png",
            "/static/examples/StrayPuppy/scene3.png",
            "/static/examples/StrayPuppy/scene4.png"
        ]
    }
}


@app.get("/")
async def root():
    return {"message": "MangakAI API is running"}


@app.get("/api/style-options", response_model=StyleOptionsResponse)
async def get_style_options():
    """Get all available style options for manga generation"""
    return StyleOptionsResponse(
        art_styles=ART_STYLES,
        mood_options=MOOD_OPTIONS,
        color_palettes=COLOR_PALETTES,
        character_styles=CHARACTER_STYLES,
        line_styles=LINE_STYLES,
        composition_styles=COMPOSITION_STYLES
    )


@app.get("/api/examples")
async def get_examples():
    """Get all example stories"""
    return {"examples": list(EXAMPLES.keys())}


@app.get("/api/examples/{example_name}", response_model=ExampleResponse)
async def get_example(example_name: str):
    """Get a specific example story"""
    if example_name not in EXAMPLES:
        raise HTTPException(status_code=404, detail="Example not found")

    example = EXAMPLES[example_name]
    return ExampleResponse(
        title=example["title"],
        story=example["story"],
        panels=example["panels"]
    )


@app.post("/api/generate-manga", response_model=MangaResponse)
async def generate_manga(request: GenerateMangaRequest):
    """Generate manga from story text"""
    try:
        # Convert None values to "None" strings for the interface
        art_style = request.art_style if request.art_style else "None"
        mood = request.mood if request.mood else "None"
        color_palette = request.color_palette if request.color_palette else "None"
        character_style = request.character_style if request.character_style else "None"
        line_style = request.line_style if request.line_style else "None"
        composition = request.composition if request.composition else "None"

        gallery_images, scene_descriptions = generate_manga_interface(
            story_text=request.story_text,
            num_scenes=request.num_scenes,
            art_style=art_style,
            mood=mood,
            color_palette=color_palette,
            character_style=character_style,
            line_style=line_style,
            composition=composition,
            additional_notes=request.additional_notes,
            user_template=None
        )

        # Convert local paths to API paths
        api_gallery_images = []
        if gallery_images:
            for img_path in gallery_images:
                if isinstance(img_path, str) and os.path.exists(img_path):
                    # Convert absolute path to relative API path
                    relative_path = os.path.relpath(img_path, "data")
                    api_path = f"/static/{relative_path}"
                    api_gallery_images.append(api_path)

        # Convert scene_descriptions list to string if it's a list
        scene_descriptions_str = ""
        if scene_descriptions:
            if isinstance(scene_descriptions, list):
                scene_descriptions_str = "\n\n".join(scene_descriptions)
            else:
                scene_descriptions_str = str(scene_descriptions)

        return MangaResponse(
            success=True,
            message="Manga generated successfully!",
            gallery_images=api_gallery_images,
            scene_descriptions=scene_descriptions_str
        )

    except Exception as e:
        return MangaResponse(
            success=False,
            message=f"Error generating manga: {str(e)}",
            gallery_images=[],
            scene_descriptions=""
        )


@app.post("/api/generate-manga-from-file", response_model=MangaResponse)
async def generate_manga_from_file(
        file: UploadFile = File(...),
        num_scenes: int = Form(5),
        art_style: Optional[str] = Form(None),
        mood: Optional[str] = Form(None),
        color_palette: Optional[str] = Form(None),
        character_style: Optional[str] = Form(None),
        line_style: Optional[str] = Form(None),
        composition: Optional[str] = Form(None),
        additional_notes: str = Form("")
):
    """Generate manga from uploaded story file"""
    try:
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as temp_file:
            shutil.copyfileobj(file.file, temp_file)
            temp_path = temp_file.name

        try:
            # Convert None values to "None" strings for the interface
            art_style = art_style if art_style else "None"
            mood = mood if mood else "None"
            color_palette = color_palette if color_palette else "None"
            character_style = character_style if character_style else "None"
            line_style = line_style if line_style else "None"
            composition = composition if composition else "None"

            gallery_images, scene_descriptions = generate_manga_from_file_interface(
                story_file=temp_path,
                num_scenes=num_scenes,
                art_style=art_style,
                mood=mood,
                color_palette=color_palette,
                character_style=character_style,
                line_style=line_style,
                composition=composition,
                additional_notes=additional_notes,
                user_template=None
            )

            # Convert local paths to API paths
            api_gallery_images = []
            if gallery_images:
                for img_path in gallery_images:
                    if isinstance(img_path, str) and os.path.exists(img_path):
                        relative_path = os.path.relpath(img_path, "data")
                        api_path = f"/static/{relative_path}"
                        api_gallery_images.append(api_path)

            # Convert scene_descriptions list to string if it's a list
            scene_descriptions_str = ""
            if scene_descriptions:
                if isinstance(scene_descriptions, list):
                    scene_descriptions_str = "\n\n".join(scene_descriptions)
                else:
                    scene_descriptions_str = str(scene_descriptions)

            return MangaResponse(
                success=True,
                message="Manga generated successfully from file!",
                gallery_images=api_gallery_images,
                scene_descriptions=scene_descriptions_str
            )

        finally:
            # Clean up temporary file
            os.unlink(temp_path)

    except Exception as e:
        return MangaResponse(
            success=False,
            message=f"Error generating manga from file: {str(e)}",
            gallery_images=[],
            scene_descriptions=""
        )


@app.get("/api/session-status")
async def get_session_status():
    """Get the current session status."""
    try:
        generator = get_global_generator()
        has_active_session = bool(generator.current_generation['generated_images'])
        panel_count = len(generator.current_generation['generated_images']) if has_active_session else 0

        return {
            "success": True,
            "has_active_session": has_active_session,
            "panel_count": panel_count,
            "message": f"Active session with {panel_count} panels" if has_active_session else "No active session"
        }
    except Exception as e:
        return {
            "success": False,
            "has_active_session": False,
            "panel_count": 0,
            "message": f"Error checking session status: {str(e)}"
        }


@app.post("/api/regenerate-panel", response_model=PanelResponse)
async def regenerate_panel(
        panel_number: int = Form(...),
        modification_request: str = Form(...),
        replace_original: bool = Form(False),
        reference_image: Optional[UploadFile] = File(None)
):
    """Regenerate a specific panel with modifications"""
    try:
        reference_path = None
        if reference_image:
            # Save reference image temporarily
            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as temp_file:
                shutil.copyfileobj(reference_image.file, temp_file)
                reference_path = temp_file.name

        try:
            if replace_original:
                # Use the regenerate and replace interface
                from app import regenerate_and_replace_interface
                status, new_image_path, updated_gallery = regenerate_and_replace_interface(
                    panel_number=panel_number,
                    modification_request=modification_request,
                    replace_original=replace_original,
                    reference_image=reference_path
                )

                # Convert paths to API paths
                api_new_image = None
                if new_image_path and os.path.exists(new_image_path):
                    relative_path = os.path.relpath(new_image_path, "data")
                    api_new_image = f"/static/{relative_path}"

                api_updated_gallery = []
                if updated_gallery:
                    for img_path in updated_gallery:
                        if isinstance(img_path, str) and os.path.exists(img_path):
                            relative_path = os.path.relpath(img_path, "data")
                            api_path = f"/static/{relative_path}"
                            api_updated_gallery.append(api_path)

                return PanelResponse(
                    success=True,
                    message=status,
                    regenerated_image=api_new_image,
                    updated_gallery=api_updated_gallery
                )
            else:
                # Use the regular regenerate interface
                status_message, new_image_path = regenerate_panel_interface(
                    panel_number=panel_number,
                    modification_request=modification_request,
                    reference_image=reference_path
                )

                api_new_image = None
                if new_image_path and os.path.exists(new_image_path):
                    relative_path = os.path.relpath(new_image_path, "data")
                    api_new_image = f"/static/{relative_path}"

                return PanelResponse(
                    success=True,
                    message=status_message,
                    regenerated_image=api_new_image,
                    updated_gallery=[]
                )

        finally:
            # Clean up reference image if it was uploaded
            if reference_path and os.path.exists(reference_path):
                os.unlink(reference_path)

    except Exception as e:
        return PanelResponse(
            success=False,
            message=f"Error regenerating panel: {str(e)}",
            regenerated_image=None,
            updated_gallery=[]
        )


@app.post("/api/create-pdf", response_model=PDFResponse)
async def create_pdf():
    """Create PDF from current manga panels"""
    try:
        status, pdf_path = create_pdf_interface()

        if pdf_path and os.path.exists(pdf_path):
            # Convert to API path
            relative_path = os.path.relpath(pdf_path, "data")
            api_pdf_path = f"/static/{relative_path}"

            return PDFResponse(
                success=True,
                message=status,
                pdf_path=api_pdf_path
            )
        else:
            return PDFResponse(
                success=False,
                message=status,
                pdf_path=None
            )

    except Exception as e:
        return PDFResponse(
            success=False,
            message=f"Error creating PDF: {str(e)}",
            pdf_path=None
        )


@app.get("/api/current-panels")
async def get_current_panels_api():
    """Get current manga panels"""
    try:
        panels = get_current_panels()

        # Convert paths to API paths
        api_panels = []
        if panels:
            for panel_path in panels:
                if isinstance(panel_path, str) and os.path.exists(panel_path):
                    relative_path = os.path.relpath(panel_path, "data")
                    api_path = f"/static/{relative_path}"
                    api_panels.append(api_path)

        return {"panels": api_panels}

    except Exception as e:
        return {"error": f"Error getting current panels: {str(e)}", "panels": []}


@app.post("/api/upload-template")
async def upload_template(file: UploadFile = File(...)):
    """Upload custom template"""
    try:
        # Save template to user templates directory
        generator = get_global_generator()
        template_path = generator.save_user_template(file.file)

        if template_path:
            relative_path = os.path.relpath(template_path, "data")
            api_path = f"/static/{relative_path}"
            return {"success": True, "message": "Template uploaded successfully", "template_path": api_path}
        else:
            return {"success": False, "message": "Failed to upload template"}

    except Exception as e:
        return {"success": False, "message": f"Error uploading template: {str(e)}"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
