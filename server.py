import os
import pickle
import json
from functools import lru_cache
from typing import Optional, List

from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from reader3 import Book, BookMetadata, ChapterContent, TOCEntry
from illustration_generator import (
    generate_illustrations_for_chapter,
    get_cached_images,
    inject_images_into_html,
    summarize_scenes
)
from tts_generator import (
    generate_tts_for_paragraph,
    get_cached_audio,
    generate_paragraph_hash
)

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# Where are the book folders located?
BOOKS_DIR = "."

@lru_cache(maxsize=10)
def load_book_cached(folder_name: str) -> Optional[Book]:
    """
    Loads the book from the pickle file.
    Cached so we don't re-read the disk on every click.
    """
    file_path = os.path.join(BOOKS_DIR, folder_name, "book.pkl")
    if not os.path.exists(file_path):
        return None

    try:
        with open(file_path, "rb") as f:
            book = pickle.load(f)
        return book
    except Exception as e:
        print(f"Error loading book {folder_name}: {e}")
        return None

@app.get("/", response_class=HTMLResponse)
async def library_view(request: Request):
    """Lists all available processed books."""
    books = []

    # Scan directory for folders ending in '_data' that have a book.pkl
    if os.path.exists(BOOKS_DIR):
        for item in os.listdir(BOOKS_DIR):
            if item.endswith("_data") and os.path.isdir(item):
                # Try to load it to get the title
                book = load_book_cached(item)
                if book:
                    books.append({
                        "id": item,
                        "title": book.metadata.title,
                        "author": ", ".join(book.metadata.authors),
                        "chapters": len(book.spine)
                    })

    return templates.TemplateResponse("library.html", {"request": request, "books": books})

@app.get("/read/{book_id}", response_class=HTMLResponse)
async def redirect_to_first_chapter(request: Request, book_id: str, background_tasks: BackgroundTasks):
    """Helper to just go to chapter 0."""
    return await read_chapter(request=request, book_id=book_id, chapter_index=0, background_tasks=background_tasks)

def get_chapter_with_images(book_id: str, chapter_index: int, chapter_content: str) -> str:
    """
    Get chapter HTML with images injected if available.
    """
    # Check for cached images
    cached_images = get_cached_images(book_id, chapter_index)
    
    if cached_images:
        # Try to load scene locations from metadata if available
        # Otherwise use default distribution
        scene_locations = [25, 50, 75]  # Default: distribute evenly
        
        # Try to get scene locations from metadata
        metadata_file = os.path.join(book_id, "generated_images.json")
        if os.path.exists(metadata_file):
            try:
                with open(metadata_file, "r") as f:
                    metadata = json.load(f)
                chapter_key = str(chapter_index)
                if chapter_key in metadata:
                    chapter_data = metadata[chapter_key]
                    if isinstance(chapter_data, dict) and "scene_locations" in chapter_data:
                        scene_locations = chapter_data["scene_locations"]
            except:
                pass
        
        # Inject images into HTML
        return inject_images_into_html(chapter_content, cached_images, scene_locations)
    
    return chapter_content


@app.get("/read/{book_id}/{chapter_index}", response_class=HTMLResponse)
async def read_chapter(request: Request, book_id: str, chapter_index: int, background_tasks: BackgroundTasks, auto_generate: bool = False):
    """The main reader interface."""
    book = load_book_cached(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    if chapter_index < 0 or chapter_index >= len(book.spine):
        raise HTTPException(status_code=404, detail="Chapter not found")

    current_chapter = book.spine[chapter_index]

    # Check if images exist
    cached_images = get_cached_images(book_id, chapter_index)
    has_images = cached_images is not None

    # Inject images if available
    chapter_html = get_chapter_with_images(book_id, chapter_index, current_chapter.content)

    # Auto-generation is disabled by default - user must click the button to generate
    # If auto_generate query param is explicitly set to true, generate in background
    if not has_images and auto_generate:
        # Trigger background generation (non-blocking)
        background_tasks.add_task(
            generate_illustrations_for_chapter,
            book_id,
            chapter_index,
            current_chapter.text,
            book.metadata.title,  # Pass book title for thematic context
            current_chapter.title  # Pass chapter title for filename
        )

    # Calculate Prev/Next links
    prev_idx = chapter_index - 1 if chapter_index > 0 else None
    next_idx = chapter_index + 1 if chapter_index < len(book.spine) - 1 else None

    return templates.TemplateResponse("reader.html", {
        "request": request,
        "book": book,
        "current_chapter": ChapterContent(
            id=current_chapter.id,
            href=current_chapter.href,
            title=current_chapter.title,
            content=chapter_html,  # Use modified HTML with images
            text=current_chapter.text,
            order=current_chapter.order
        ),
        "chapter_index": chapter_index,
        "book_id": book_id,
        "prev_idx": prev_idx,
        "next_idx": next_idx,
        "has_illustrations": has_images
    })




@app.post("/read/{book_id}/{chapter_index}/generate-illustrations")
async def generate_illustrations_endpoint(book_id: str, chapter_index: int, background_tasks: BackgroundTasks):
    """Manually trigger illustration generation for a chapter (force regenerate)."""
    print(f"[DEBUG] ===== POST /generate-illustrations endpoint called ======")
    print(f"[DEBUG] Book ID: {book_id}")
    print(f"[DEBUG] Chapter Index: {chapter_index}")

    book = load_book_cached(book_id)
    if not book:
        print(f"[DEBUG] ERROR: Book not found")
        raise HTTPException(status_code=404, detail="Book not found")

    if chapter_index < 0 or chapter_index >= len(book.spine):
        print(f"[DEBUG] ERROR: Chapter index out of range (0-{len(book.spine)-1})")
        raise HTTPException(status_code=404, detail="Chapter not found")

    current_chapter = book.spine[chapter_index]
    print(f"[DEBUG] Chapter found: {current_chapter.title}")
    print(f"[DEBUG] Chapter text length: {len(current_chapter.text)} chars")

    # Trigger generation in background with force_regenerate=True
    print(f"[DEBUG] Adding background task for illustration generation (force regenerate)...")
    background_tasks.add_task(
        generate_illustrations_for_chapter,
        book_id,
        chapter_index,
        current_chapter.text,
        book.metadata.title,  # Pass book title for thematic context
        current_chapter.title,  # Pass chapter title for filename
        True  # force_regenerate=True
    )
    print(f"[DEBUG] Background task added successfully")

    response_data = {
        "status": "generating",
        "message": "Illustration regeneration started. Refresh the page in a few moments to see the new images."
    }
    print(f"[DEBUG] Returning response: {response_data}")
    return JSONResponse(response_data)


@app.get("/read/{book_id}/{chapter_index}/illustration-status")
async def illustration_status(book_id: str, chapter_index: int):
    """Check if illustrations exist for a chapter."""
    cached_images = get_cached_images(book_id, chapter_index)
    return JSONResponse({
        "has_illustrations": cached_images is not None,
        "image_count": len(cached_images) if cached_images else 0
    })

@app.get("/read/{book_id}/images/{image_name}")
async def serve_image(book_id: str, image_name: str):
    """
    Serves images specifically for a book.
    The HTML contains <img src="images/pic.jpg">.
    The browser resolves this to /read/{book_id}/images/pic.jpg.
    """
    # Security check: ensure book_id is clean
    safe_book_id = os.path.basename(book_id)
    safe_image_name = os.path.basename(image_name)

    img_path = os.path.join(BOOKS_DIR, safe_book_id, "images", safe_image_name)

    if not os.path.exists(img_path):
        raise HTTPException(status_code=404, detail="Image not found")

    return FileResponse(img_path)


# ============= TTS ENDPOINTS =============

@app.post("/read/{book_id}/generate-tts")
async def generate_tts_endpoint(
    book_id: str,
    request: Request,
    background_tasks: BackgroundTasks
):
    """Generate TTS audio for a paragraph."""
    print(f"[TTS DEBUG] ===== POST /generate-tts endpoint called =====")
    print(f"[TTS DEBUG] Book ID: {book_id}")

    # Parse request body
    body = await request.json()
    paragraph_text = body.get("text", "")

    if not paragraph_text:
        print(f"[TTS ERROR] No text provided in request")
        raise HTTPException(status_code=400, detail="No text provided")

    print(f"[TTS DEBUG] Text length: {len(paragraph_text)} chars")

    # Validate book exists
    book = load_book_cached(book_id)
    if not book:
        print(f"[TTS ERROR] Book not found")
        raise HTTPException(status_code=404, detail="Book not found")

    # Generate hash for paragraph
    para_hash = generate_paragraph_hash(paragraph_text)
    print(f"[TTS DEBUG] Paragraph hash: {para_hash}")

    # Check cache first
    cached = get_cached_audio(book_id, para_hash)
    if cached:
        print(f"[TTS DEBUG] Audio already cached: {cached}")
        return JSONResponse({
            "status": "cached",
            "audio_path": cached,
            "para_hash": para_hash
        })

    # Trigger background generation
    print(f"[TTS DEBUG] Adding background task for TTS generation...")
    background_tasks.add_task(
        generate_tts_for_paragraph,
        book_id,
        paragraph_text
    )
    print(f"[TTS DEBUG] Background task added successfully")

    response_data = {
        "status": "generating",
        "para_hash": para_hash
    }
    print(f"[TTS DEBUG] Returning response: {response_data}")
    return JSONResponse(response_data)


@app.get("/read/{book_id}/audio/{audio_name}")
async def serve_audio(book_id: str, audio_name: str):
    """
    Serve audio files for TTS playback.
    Similar to serve_image but for audio files.
    """
    print(f"[TTS DEBUG] Serving audio: {book_id}/{audio_name}")

    # Security: sanitize paths to prevent directory traversal
    safe_book_id = os.path.basename(book_id)
    safe_audio_name = os.path.basename(audio_name)

    audio_path = os.path.join(BOOKS_DIR, safe_book_id, "audio", safe_audio_name)

    if not os.path.exists(audio_path):
        print(f"[TTS ERROR] Audio file not found: {audio_path}")
        raise HTTPException(status_code=404, detail="Audio not found")

    print(f"[TTS DEBUG] Serving audio file: {audio_path}")
    return FileResponse(
        audio_path,
        media_type="audio/wav",
        headers={
            "Cache-Control": "public, max-age=31536000",  # Cache for 1 year
            "Accept-Ranges": "bytes"  # Enable range requests for seeking
        }
    )


@app.get("/read/{book_id}/tts-status/{para_hash}")
async def tts_status(book_id: str, para_hash: str):
    """Check TTS generation status for a paragraph."""
    print(f"[TTS DEBUG] Checking TTS status for hash: {para_hash}")

    cached = get_cached_audio(book_id, para_hash)
    is_ready = cached is not None

    print(f"[TTS DEBUG] Status - Ready: {is_ready}, Path: {cached}")

    return JSONResponse({
        "ready": is_ready,
        "audio_path": cached if cached else None
    })


if __name__ == "__main__":
    import uvicorn
    print("Starting server at http://127.0.0.1:8123")
    uvicorn.run("server:app", host="127.0.0.1", port=8123, reload=True)
