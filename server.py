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
async def read_chapter(request: Request, book_id: str, chapter_index: int, background_tasks: BackgroundTasks, auto_generate: bool = True):
    """The main reader interface."""
    book = load_book_cached(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    if chapter_index < 0 or chapter_index >= len(book.spine):
        raise HTTPException(status_code=404, detail="Chapter not found")

    current_chapter = book.spine[chapter_index]
    
    # Check if images exist, if not and auto_generate is True, trigger generation in background
    cached_images = get_cached_images(book_id, chapter_index)
    has_images = cached_images is not None
    
    # Inject images if available
    chapter_html = get_chapter_with_images(book_id, chapter_index, current_chapter.content)
    
    # If no images and auto_generate, start generation in background
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
    """Manually trigger illustration generation for a chapter."""
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
    
    # Trigger generation in background
    print(f"[DEBUG] Adding background task for illustration generation...")
    background_tasks.add_task(
        generate_illustrations_for_chapter,
        book_id,
        chapter_index,
        current_chapter.text,
        book.metadata.title,  # Pass book title for thematic context
        current_chapter.title  # Pass chapter title for filename
    )
    print(f"[DEBUG] Background task added successfully")
    
    response_data = {
        "status": "generating",
        "message": "Illustration generation started. Refresh the page in a few moments to see the images."
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

if __name__ == "__main__":
    import uvicorn
    print("Starting server at http://127.0.0.1:8123")
    uvicorn.run("server:app", host="127.0.0.1", port=8123, reload=True)
