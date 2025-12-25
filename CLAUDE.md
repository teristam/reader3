# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

reader3 is a lightweight, self-hosted EPUB reader designed for reading books alongside LLMs. It parses EPUB files, serves them chapter-by-chapter through a web interface, and optionally generates AI illustrations using Google's Gemini API.

## Development Commands

### Running the Application

```bash
# Process an EPUB file (creates a {book_name}_data directory)
uv run reader3.py <file.epub>

# Start the web server (default: http://127.0.0.1:8123)
uv run server.py
```

### Managing Dependencies

```bash
# Install/sync dependencies (uv handles this automatically with 'uv run')
uv sync

# Add a new dependency
uv add <package-name>
```

## Architecture

### Data Flow: EPUB to Web Reader

1. **EPUB Processing** ([reader3.py](reader3.py))
   - `process_epub()` extracts and processes EPUB files
   - Creates a `Book` object containing metadata, spine (chapters), TOC, and images
   - Saves processed data as `book.pkl` in `{book_name}_data/` directory
   - Images are extracted to `{book_name}_data/images/`

2. **Web Server** ([server.py](server.py))
   - FastAPI application serving the reader interface
   - Uses `@lru_cache` for `load_book_cached()` to avoid repeated disk reads
   - Serves both static content (images) and dynamic pages (library, reader)

3. **AI Illustrations** ([illustration_generator.py](illustration_generator.py))
   - Optional feature requiring `GEMINI_API_KEY` environment variable
   - Generates 3 illustrations per chapter using Gemini 2.0 Flash (scene analysis) and Gemini 2.5 Flash Image (image generation)
   - Images cached in `{book_name}_data/images/` with metadata in `generated_images.json`

### Key Data Structures

The Book object hierarchy (defined in [reader3.py](reader3.py)):

```
Book
├── metadata: BookMetadata (title, authors, language, etc.)
├── spine: List[ChapterContent] (actual content in reading order)
├── toc: List[TOCEntry] (navigation tree, can be nested)
└── images: Dict[str, str] (original_path -> local_path)
```

**Important**: The `spine` represents the linear reading order (physical files), while `toc` represents the logical navigation structure. A single spine item (file) may contain multiple TOC entries (chapters).

### File Storage Structure

```
{book_name}_data/
├── book.pkl                    # Serialized Book object
├── images/                     # Extracted EPUB images
│   └── *.jpg, *.png
└── generated_images.json       # AI illustration metadata (optional)
```

## AI Illustration System

### Environment Setup

Set the Gemini API key before running the server:
```bash
export GEMINI_API_KEY=your_api_key_here
```

### How It Works

1. **Auto-generation**: When a chapter is opened, illustrations are generated in the background if not cached
2. **Manual trigger**: Users can click "Generate Illustrations" to manually trigger generation
3. **Scene Analysis**:
   - Chapter text sent to `gemini-2.0-flash-exp` for scene identification
   - Returns 3 scenes with summaries and location percentages (0-100)
4. **Image Generation**:
   - Each scene summary converted to an image prompt
   - Images generated using `gemini-2.5-flash-image` model
   - Saved as `generated_ch{N}_scene{1-3}.png`
5. **HTML Injection**:
   - Images injected into chapter HTML at calculated paragraph positions
   - Position based on scene location percentages

### Caching Strategy

- Generated images are cached in the book's `images/` directory
- Metadata stored in `generated_images.json` with format:
  ```json
  {
    "0": {
      "images": ["images/generated_ch0_scene1.png", ...],
      "scene_locations": [25, 50, 75]
    }
  }
  ```
- `get_cached_images()` checks cache before generation

## Important Implementation Details

### HTML Processing

- [reader3.py](reader3.py) cleans HTML by removing scripts, styles, forms, nav elements
- Image paths are rewritten from EPUB internal paths to local relative paths
- Only the `<body>` content is extracted from EPUB files to avoid HTML wrapper duplication

### Image Serving

Images are served through `/read/{book_id}/images/{image_name}` which:
- Uses `os.path.basename()` for security (prevents directory traversal)
- Resolves to `{book_id}/images/{image_name}` on disk
- Handles both EPUB-extracted images and AI-generated images

### TOC Handling

The TOC parser handles three structures from ebooklib:
- `epub.Link` objects (simple entries)
- `epub.Section` objects (section without children)
- `tuple(Section, [Children])` (nested structure)

If TOC is missing or empty, `get_fallback_toc()` generates a flat TOC from the spine.

### FastAPI Background Tasks

Illustration generation uses `BackgroundTasks` to avoid blocking the HTTP response:
```python
background_tasks.add_task(generate_illustrations_for_chapter, book_id, chapter_index, text)
```

This allows the page to load immediately while images generate asynchronously.

## Templates

- [templates/library.html](templates/library.html) - Library view showing all processed books
- [templates/reader.html](templates/reader.html) - Main reader interface with chapter content, TOC sidebar, and navigation

Both templates use Jinja2 templating and receive data from FastAPI routes.

## Project Philosophy

Per the README, this is a "90% vibe coded" project meant as inspiration rather than a supported product. The architecture is intentionally simple:
- File-based storage (pickle, JSON) instead of databases
- Single-file Python modules
- No complex build process
- Books managed by adding/removing directories
