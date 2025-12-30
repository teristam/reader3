"""
Module for generating AI illustrations for ebook chapters using Gemini API.
"""

import os
import json
import base64
import traceback
from typing import List, Dict, Optional
from bs4 import BeautifulSoup
from loguru import logger
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

try:
    from google import genai
except ImportError:
    genai = None

# Configure loguru
logger.remove()  # Remove default handler
logger.add(
    lambda msg: print(msg, end=""),  # Print to stdout
    format="<green>{time:HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    colorize=True,
    level="DEBUG"
)

# Add file sink for prompt/response logging (for fine-tuning)
logger.add(
    "logs/illustration_prompts_{time:YYYY-MM-DD}.log",
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
    level="DEBUG",
    rotation="00:00",  # New file each day
    retention="30 days",  # Keep logs for 30 days
    compression="zip"  # Compress old logs
)


def sanitize_chapter_title(title: str, max_length: int = 50) -> str:
    """
    Sanitize chapter title for use in filename.

    Args:
        title: The chapter title to sanitize
        max_length: Maximum length of the sanitized title

    Returns:
        A filesystem-safe version of the title
    """
    # Remove or replace problematic characters
    # Keep alphanumeric, spaces, hyphens, and underscores
    safe_chars = []
    for c in title:
        if c.isalnum() or c in (' ', '-', '_'):
            safe_chars.append(c)
        elif c in ('.', ',', ':', ';', '!', '?', "'", '"'):
            # Skip punctuation
            continue
        else:
            # Replace other characters with underscore
            safe_chars.append('_')

    # Join and clean up
    sanitized = ''.join(safe_chars)

    # Replace multiple spaces/underscores with single underscore
    import re
    sanitized = re.sub(r'[\s_]+', '_', sanitized)

    # Remove leading/trailing underscores
    sanitized = sanitized.strip('_')

    # Truncate to max_length
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length].rstrip('_')

    # Ensure we have something
    if not sanitized:
        sanitized = "chapter"

    return sanitized


def get_gemini_client():
    """Initialize and return Gemini client."""
    if genai is None:
        raise ImportError("google-genai package not installed. Run: uv pip install google-genai")
    
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable not set")
    
    # Client automatically uses GEMINI_API_KEY from environment, but we can also pass it explicitly
    return genai.Client(api_key=api_key)


def summarize_scenes(chapter_text: str, num_scenes: int = 3) -> List[Dict]:
    """
    Sends chapter text to Gemini 3.0 Flash asking for N main scene summaries.

    Args:
        chapter_text: The chapter text to analyze
        num_scenes: Number of scenes to identify (default: 3)

    Returns list of scene dicts with:
    - summary: str - summary of the scene
    - location_in_text: int - approximate character position (0-100 percentage)
    - scene_number: int - 1, 2, 3, etc.
    """
    if not chapter_text or len(chapter_text.strip()) == 0:
        return []

    client = get_gemini_client()

    prompt = f"""Analyze the following chapter from a book and identify the {num_scenes} most important scenes to illustrate.

CRITICAL PLACEMENT INSTRUCTION:
For each scene, identify the exact sentence that should appear BEFORE the illustration.
- The illustration will be inserted immediately AFTER the paragraph containing this sentence
- Choose a sentence that sets up the scene BEFORE key action begins (to establish context, not spoil it)
- This should be a moment of anticipation, setup, or arrival - NOT during the climax
- The anchor sentence should be distinctive and unique to avoid false matches
- Avoid generic phrases like "he said" or "she walked" - choose sentences with specific details

For each scene, provide:
1. A detailed summary of the scene for illustration generation (around 500 words) including settings, people and atmosphere
2. The exact sentence that appears in the paragraph before the illustration (verbatim from the text)
3. An approximate location as a percentage (0-100) as a fallback if text matching fails

EXAMPLE:
If the text contains: "The sky darkened as storm clouds gathered. He approached the ancient door, hand trembling."
And you want the illustration to appear after "storm clouds gathered", provide:
- insert_after_text: "The sky darkened as storm clouds gathered."
- The illustration will be inserted after the paragraph containing this sentence

Format your response as JSON with exactly {num_scenes} scenes in this structure:
{{
    "scenes": [
        {{
            "scene_number": 1,
            "summary": "description of the scene",
            "insert_after_text": "The exact sentence from the chapter.",
            "location_percent": <evenly distributed percentage>
        }},
        ... ({num_scenes} scenes total)
    ]
}}

Chapter text:
{chapter_text[:50000]}  # Limit to 50k chars to avoid token limits
"""

    logger.info("📝 Sending scene analysis request to Gemini")
    logger.debug(f"Chapter text length: {len(chapter_text)} chars (sending first 50000)")
    logger.debug(f"Model: gemini-2.0-flash-exp")
    logger.debug(f"Prompt length: {len(prompt)} chars")

    # Log full prompt for fine-tuning
    logger.debug("=" * 80)
    logger.debug("SCENE ANALYSIS PROMPT:")
    logger.debug(prompt)
    logger.debug("=" * 80)

    try:
        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=[prompt]
        )

        logger.success("✅ Response received from Gemini")
        logger.debug(f"Response type: {type(response)}")
        logger.debug(f"Response parts count: {len(response.parts) if hasattr(response, 'parts') and response.parts is not None else 'N/A'}")
        
        # Extract text response
        response_text = ""
        if response.parts is not None:
            for i, part in enumerate(response.parts):
                logger.trace(f"Part {i}: type={type(part)}, has text={hasattr(part, 'text')}")
                if hasattr(part, 'text') and part.text:
                    response_text += part.text
                    logger.trace(f"Part {i} text length: {len(part.text)} chars")
        else:
            logger.error("❌ Response has no parts (parts is None)")

        logger.debug(f"Full response text length: {len(response_text)} chars")
        logger.trace(f"Response text (first 1000 chars): {response_text[:1000]}")

        # Log full response for fine-tuning
        logger.debug("=" * 80)
        logger.debug("SCENE ANALYSIS RESPONSE:")
        logger.debug(response_text)
        logger.debug("=" * 80)

        # Parse JSON response
        # Sometimes Gemini wraps JSON in markdown code blocks
        response_text = response_text.strip()
        if response_text.startswith("```"):
            logger.debug("Response wrapped in code block, extracting JSON...")
            # Extract JSON from code block
            lines = response_text.split("\n")
            response_text = "\n".join(lines[1:-1]) if len(lines) > 2 else response_text
            logger.debug(f"Extracted JSON length: {len(response_text)} chars")

        logger.debug("Attempting to parse JSON...")
        data = json.loads(response_text)
        logger.success("✅ JSON parsed successfully")
        scenes = data.get("scenes", [])
        logger.info(f"Found {len(scenes)} scenes in response")

        # Validate both fields exist in each scene
        for scene in scenes:
            if "insert_after_text" not in scene:
                logger.warning(f"Scene {scene.get('scene_number')} missing insert_after_text, will use percentage fallback")
                scene["insert_after_text"] = None
            if "location_percent" not in scene:
                logger.warning(f"Scene {scene.get('scene_number')} missing location_percent, using default")
                scene["location_percent"] = 33 * (scene.get("scene_number", 1) - 1)

        # Ensure we have exactly num_scenes scenes, pad if needed
        while len(scenes) < num_scenes:
            idx = len(scenes)
            scenes.append({
                "scene_number": idx + 1,
                "summary": "A scene from the chapter",
                "insert_after_text": None,
                "location_percent": int(100 * (idx + 0.5) / num_scenes)
            })

        logger.info(f"Returning {len(scenes[:num_scenes])} scenes")
        for i, scene in enumerate(scenes[:num_scenes]):
            anchor_preview = scene.get('insert_after_text', 'None')
            if anchor_preview and len(anchor_preview) > 60:
                anchor_preview = anchor_preview[:60] + "..."
            logger.debug(f"Scene {i+1}: number={scene.get('scene_number')}, location={scene.get('location_percent')}%, anchor='{anchor_preview}', summary_length={len(scene.get('summary', ''))}")

        return scenes[:num_scenes]  # Return only requested number

    except json.JSONDecodeError as e:
        logger.error("❌ JSON parsing failed")
        logger.error(f"Error: {e}")
        logger.debug(f"Response text (first 2000 chars): {response_text[:2000]}")
        logger.debug(f"Full response text length: {len(response_text)}")
        # Fallback: create generic scenes
        logger.warning("⚠️ Using fallback scenes")
        fallback_scenes = []
        for i in range(num_scenes):
            fallback_scenes.append({
                "scene_number": i + 1,
                "summary": f"An important scene from the chapter (scene {i+1})",
                "insert_after_text": None,
                "location_percent": int(100 * (i + 0.5) / num_scenes)
            })
        return fallback_scenes
    except Exception as e:
        logger.exception(f"❌ Exception in summarize_scenes: {type(e).__name__}: {str(e)}")
        raise


def create_image_prompt(scene_summary: str, book_title: str = "", style: str = "") -> str:
    """
    Takes a scene summary and creates a detailed, descriptive prompt for image generation.

    Args:
        scene_summary: Summary of the scene to illustrate
        book_title: Title of the book for thematic context
        style: Artistic style for the illustration (e.g., "anime", "realistic", "watercolor")
    """
    book_context = f" from the book '{book_title}'" if book_title else " from a book"

    prompt = f"""Create a suitable illustration of this scene {book_context}:

{scene_summary}

The image should be:
- High quality and visually appealing
- Capturing the mood and atmosphere of the scene
- Do not include any text in the image. Avoid making it like a comic

You MUST follow the following stylistic instruction closely:
{style}

Generate a beautiful illustration that captures the essence of this scene."""

    logger.debug(f"Created image prompt (length: {len(prompt)} chars)")
    if style:
        logger.debug(f"Using custom style: {style}")
    logger.trace(f"Prompt preview: {prompt[:200]}...")

    return prompt


def generate_image(prompt: str) -> bytes:
    """
    Uses Nano Banana API (gemini-2.5-flash-image model) to generate image bytes.

    Returns image bytes (PNG format).
    """
    logger.info("🎨 Starting image generation")
    logger.debug(f"Model: gemini-2.5-flash-image")
    logger.debug(f"Prompt length: {len(prompt)} chars")

    # Log full image prompt for fine-tuning
    logger.debug("=" * 80)
    logger.debug("IMAGE GENERATION PROMPT:")
    logger.debug(prompt)
    logger.debug("=" * 80)

    client = get_gemini_client()

    try:
        logger.info("📤 Sending request to Gemini Image API...")
        response = client.models.generate_content(
            model="gemini-2.5-flash-image",
            contents=[prompt]
        )

        logger.success("✅ Response received from Gemini")
        logger.debug(f"Response type: {type(response)}")

        # Log all response attributes for debugging
        logger.trace(f"Response attributes: {dir(response)}")

        # Try to access the raw response
        if hasattr(response, '_raw_response'):
            logger.debug(f"Raw response: {response._raw_response}")

        logger.debug(f"Response parts count: {len(response.parts) if hasattr(response, 'parts') and response.parts is not None else 'N/A'}")

        # Check for error or safety information in response
        if hasattr(response, 'prompt_feedback'):
            logger.warning(f"⚠️ Prompt feedback: {response.prompt_feedback}")
        if hasattr(response, 'candidates') and response.candidates:
            for i, candidate in enumerate(response.candidates):
                if hasattr(candidate, 'finish_reason'):
                    logger.info(f"Candidate {i} finish_reason: {candidate.finish_reason}")
                if hasattr(candidate, 'safety_ratings'):
                    logger.info(f"Candidate {i} safety_ratings: {candidate.safety_ratings}")

        # Extract image bytes from response (following official Gemini API pattern)
        if response.parts is not None:
            for i, part in enumerate(response.parts):
                logger.debug(f"Processing part {i}: type={type(part)}")

                # Check for text response (likely an error message)
                if part.text is not None:
                    logger.warning(f"⚠️ Part {i} contains text instead of image:")
                    logger.error(f"Text content: {part.text}")
                    continue

                # Check for image data using the official as_image() method
                if part.inline_data is not None:
                    logger.debug(f"✓ Part {i} has inline_data, extracting image")

                    # Use the official as_image() method (returns PIL Image)
                    pil_image = part.as_image()._pil_image  # type: ignore
                    logger.debug(f"Image type: {type(pil_image)}")

                    # Convert PIL Image to PNG bytes
                    import io
                    img_byte_arr = io.BytesIO()
                    pil_image.save(img_byte_arr, format='PNG')
                    image_bytes = img_byte_arr.getvalue()
                    logger.success(f"✅ Got image using as_image(), length: {len(image_bytes)} bytes")

                    # Log image response metadata for fine-tuning
                    logger.debug("=" * 80)
                    logger.debug("IMAGE GENERATION RESPONSE:")
                    logger.debug(f"  Image size: {pil_image.size}")
                    logger.debug(f"  Image mode: {pil_image.mode}")
                    logger.debug(f"  Image format: {pil_image.format}")
                    logger.debug(f"  Bytes length: {len(image_bytes)}")
                    logger.debug("=" * 80)

                    # Validate size
                    if len(image_bytes) < 1000:
                        logger.warning(f"⚠️ Suspiciously small image: {len(image_bytes)} bytes")
                        raise ValueError(f"Image too small: {len(image_bytes)} bytes")

                    return image_bytes

            logger.error("❌ No image data found in response")
            logger.error(f"Checked {len(response.parts)} parts, none contained image data")
        else:
            logger.error("❌ Response has no parts (parts is None)")

        # Collect all text from response for debugging
        response_text = ""
        if response.parts is not None:
            for part in response.parts:
                if part.text is not None:
                    response_text += part.text

            if response_text:
                logger.error("⚠️ Response contained only text, no image:")
                logger.error(f"{response_text[:500]}")

            raise ValueError(f"No image data found in response. Response had {len(response.parts)} parts. Text: {response_text[:200] if response_text else 'none'}")
        else:
            raise ValueError("No image data found in response. Response.parts is None (likely blocked by safety filters or API error)")

    except Exception as e:
        logger.exception(f"❌ Exception in generate_image: {type(e).__name__}: {str(e)}")
        raise


def save_image(image_bytes: bytes, book_id: str, chapter_index: int, scene_number: int, chapter_title: str = "") -> str:
    """
    Saves image to {book_id}/images/generated_ch{chapter_index}_{sanitized_title}_scene{scene_number}.png
    and returns relative path.

    Args:
        image_bytes: The image data to save
        book_id: The book directory name
        chapter_index: Index of the chapter
        scene_number: Scene number (1-3)
        chapter_title: Optional chapter title to include in filename

    Returns:
        Relative path to the saved image
    """
    # Validate image bytes
    if not image_bytes or len(image_bytes) < 1000:
        raise ValueError(f"Invalid image data: only {len(image_bytes)} bytes (expected at least 1000 bytes for a valid PNG)")

    logger.debug(f"Validating image data: {len(image_bytes)} bytes")

    # Basic PNG validation - check for PNG header
    PNG_HEADER = b'\x89PNG\r\n\x1a\n'
    if not image_bytes.startswith(PNG_HEADER):
        logger.warning(f"⚠️ Image data does not start with PNG header")
        logger.debug(f"First 16 bytes: {image_bytes[:16]}")
        # Try to detect if it's a base64-encoded string that wasn't decoded
        try:
            decoded = base64.b64decode(image_bytes)
            if decoded.startswith(PNG_HEADER):
                logger.info("✓ Image was double-encoded, using decoded version")
                image_bytes = decoded
            else:
                raise ValueError(f"Image data is not a valid PNG (header: {image_bytes[:16]})")
        except:
            raise ValueError(f"Image data is not a valid PNG (header: {image_bytes[:16]})")

    # Ensure images directory exists
    images_dir = os.path.join(book_id, "images")
    os.makedirs(images_dir, exist_ok=True)

    # Create filename with chapter title if provided
    if chapter_title:
        sanitized_title = sanitize_chapter_title(chapter_title)
        filename = f"generated_ch{chapter_index}_{sanitized_title}_scene{scene_number}.png"
    else:
        filename = f"generated_ch{chapter_index}_scene{scene_number}.png"

    filepath = os.path.join(images_dir, filename)

    # Save image
    logger.success(f"💾 Saving valid PNG image to: {filepath}")
    with open(filepath, "wb") as f:
        f.write(image_bytes)

    # Return relative path
    return f"images/{filename}"


def get_cached_images(book_id: str, chapter_index: int) -> Optional[List[str]]:
    """
    Check if images are cached for a chapter.
    Returns list of image paths if cached, None otherwise.
    """
    metadata_file = os.path.join(book_id, "generated_images.json")

    if not os.path.exists(metadata_file):
        return None

    try:
        with open(metadata_file, "r") as f:
            metadata = json.load(f)

        chapter_key = str(chapter_index)
        if chapter_key in metadata:
            # Handle both old format (list) and new format (dict with "images" key)
            chapter_data = metadata[chapter_key]
            if isinstance(chapter_data, list):
                image_paths = chapter_data
            elif isinstance(chapter_data, dict) and "images" in chapter_data:
                image_paths = chapter_data["images"]
            else:
                return None

            # Verify images actually exist
            existing_paths = []
            for img_path in image_paths:
                full_path = os.path.join(book_id, img_path)
                if os.path.exists(full_path):
                    existing_paths.append(img_path)

            # Return cached images if all exist and status is completed
            if existing_paths and isinstance(chapter_data, dict):
                # Check if generation is complete
                if chapter_data.get("status") == "completed" and len(existing_paths) == len(image_paths):
                    return existing_paths
            elif existing_paths and len(existing_paths) == len(image_paths):
                # Legacy format (list) - just check all images exist
                return existing_paths

        return None
    except Exception as e:
        print(f"Error reading cache metadata: {e}")
        return None


def save_image_metadata(
    book_id: str,
    chapter_index: int,
    image_paths: List[str],
    scene_locations: Optional[List[int]] = None,
    anchor_texts: Optional[List[Optional[str]]] = None,
    status: str = "completed",
    error: Optional[str] = None,
    current_image_count: Optional[int] = None
):
    """
    Save metadata about generated images to track caching.

    Args:
        book_id: The book directory name
        chapter_index: Index of the chapter
        image_paths: List of generated image paths
        scene_locations: Optional list of scene location percentages (fallback)
        anchor_texts: Optional list of anchor sentences for precise placement
        status: Generation status - "generating", "completed", or "error"
        error: Error message if status is "error"
        current_image_count: Number of images completed so far (for progress tracking)
    """
    metadata_file = os.path.join(book_id, "generated_images.json")

    # Load existing metadata
    metadata = {}
    if os.path.exists(metadata_file):
        try:
            with open(metadata_file, "r") as f:
                metadata = json.load(f)
        except:
            metadata = {}

    # Update with new chapter images
    chapter_key = str(chapter_index)
    chapter_data = {
        "images": image_paths,
        "status": status,
        "schema_version": 2  # Track schema version for backward compatibility
    }
    if scene_locations:
        chapter_data["scene_locations"] = scene_locations
    if anchor_texts:
        chapter_data["anchor_texts"] = anchor_texts
    if error:
        chapter_data["error"] = error
    if current_image_count is not None:
        chapter_data["current_image_count"] = current_image_count
    metadata[chapter_key] = chapter_data

    # Save back
    with open(metadata_file, "w") as f:
        json.dump(metadata, f, indent=2)


def generate_illustrations_for_chapter(book_id: str, chapter_index: int, chapter_text: str, book_title: str = "", chapter_title: str = "", force_regenerate: bool = False, num_images: int = 3, style: str = "") -> List[str]:
    """
    Main function to generate illustrations for a chapter.

    Args:
        book_id: The book directory name
        chapter_index: Index of the chapter in the book's spine
        chapter_text: Full text content of the chapter
        book_title: Title of the book for thematic context in image generation
        chapter_title: Title of the chapter for filename generation
        force_regenerate: If True, regenerate images even if cached versions exist
        num_images: Number of illustrations to generate (default: 3)
        style: Artistic style for the illustrations (e.g., "anime", "realistic", "watercolor")

    Returns:
        List of image paths (relative to book directory)
    """
    logger.info("=" * 60)
    logger.info("🎬 STARTING ILLUSTRATION GENERATION")
    logger.info("=" * 60)
    logger.info(f"Book ID: {book_id}")
    logger.info(f"Book Title: {book_title}")
    logger.info(f"Chapter Index: {chapter_index}")
    logger.info(f"Chapter Title: {chapter_title}")
    logger.debug(f"Chapter text length: {len(chapter_text)} chars")
    logger.info(f"Force regenerate: {force_regenerate}")
    logger.info(f"Number of images: {num_images}")
    logger.info(f"Style: {style if style else '(default)'}")

    # Check cache first (unless force_regenerate is True)
    if not force_regenerate:
        cached = get_cached_images(book_id, chapter_index)
        if cached and len(cached) == num_images:
            logger.success(f"✅ Found {len(cached)} cached images: {cached}")
            return cached
        elif cached:
            logger.warning(f"⚠️ Found {len(cached)} cached images, but need {num_images}. Will regenerate.")
            force_regenerate = True

    if force_regenerate:
        logger.warning("🗑️  Force regenerate enabled, deleting old images...")
        # Delete old cached images if they exist
        metadata_file = os.path.join(book_id, "generated_images.json")
        if os.path.exists(metadata_file):
            try:
                with open(metadata_file, "r") as f:
                    metadata = json.load(f)
                chapter_key = str(chapter_index)
                if chapter_key in metadata:
                    # Get old image paths
                    chapter_data = metadata[chapter_key]
                    if isinstance(chapter_data, list):
                        old_paths = chapter_data
                    elif isinstance(chapter_data, dict) and "images" in chapter_data:
                        old_paths = chapter_data["images"]
                    else:
                        old_paths = []

                    # Delete old image files
                    for img_path in old_paths:
                        full_path = os.path.join(book_id, img_path)
                        if os.path.exists(full_path):
                            os.remove(full_path)
                            logger.info(f"🗑️  Deleted old image: {full_path}")

                    # Remove chapter from metadata so get_cached_images() returns None during regeneration
                    del metadata[chapter_key]
                    with open(metadata_file, "w") as f:
                        json.dump(metadata, f, indent=2)
                    logger.info(f"✅ Removed chapter {chapter_key} from metadata")
            except Exception as e:
                logger.error(f"❌ Error cleaning up old images: {e}")

    # Mark as generating
    save_image_metadata(book_id, chapter_index, [], status="generating", current_image_count=0)
    logger.info("🆕 Generating new images...")

    try:
        # Generate scenes
        logger.info("📋 Step 1: Summarizing scenes...")
        scenes = summarize_scenes(chapter_text, num_scenes=num_images)
        logger.success(f"✅ Got {len(scenes)} scenes")

        image_paths = []
        scene_locations = []
        anchor_texts = []  # NEW: Collect anchor texts

        for i, scene in enumerate(scenes):
            logger.info("=" * 60)
            logger.info(f"🎨 Processing Scene {i+1}/{len(scenes)}")
            logger.info("=" * 60)
            scene_num = scene["scene_number"]
            scene_summary = scene["summary"]
            scene_location = scene.get("location_percent", int(100 * (i + 0.5) / num_images))
            scene_anchor = scene.get("insert_after_text")  # NEW: Extract anchor text

            scene_locations.append(scene_location)
            anchor_texts.append(scene_anchor)  # NEW: Store anchor text

            logger.info(f"Summary: {scene_summary[:100]}...")
            logger.info(f"Location: {scene_location}%")
            if scene_anchor:
                anchor_preview = scene_anchor if len(scene_anchor) <= 80 else scene_anchor[:80] + "..."
                logger.info(f"Anchor text: '{anchor_preview}'")

            try:
                # Create image prompt
                logger.info(f"📝 Step 2: Creating image prompt for scene {i+1}...")
                prompt = create_image_prompt(scene_summary, book_title, style)

                # Generate image
                logger.info(f"🎨 Step 3: Generating image for scene {i+1}...")
                image_bytes = generate_image(prompt)
                logger.info(f"Generated image: {len(image_bytes)} bytes")

                # Validate before saving
                if len(image_bytes) < 1000:
                    raise ValueError(f"Image too small: {len(image_bytes)} bytes - likely an error response")

                # Save image
                logger.info(f"💾 Step 4: Saving image for scene {i+1}...")
                img_path = save_image(image_bytes, book_id, chapter_index, scene_num, chapter_title)
                logger.success(f"✅ Saved image to: {img_path}")
                image_paths.append(img_path)

                # Update progress after each image
                save_image_metadata(
                    book_id,
                    chapter_index,
                    image_paths,
                    scene_locations[:i+1],  # Only include locations for completed images
                    anchor_texts[:i+1],     # Only include anchors for completed images
                    status="generating",
                    current_image_count=len(image_paths)
                )
                logger.info(f"📊 Progress: {len(image_paths)}/{num_images} images completed")

            except Exception as e:
                logger.error("=" * 60)
                logger.error(f"❌ ERROR processing scene {i+1}")
                logger.error("=" * 60)
                logger.error(f"Error type: {type(e).__name__}")
                logger.error(f"Error message: {str(e)}")
                logger.exception("Full traceback:")
                # Re-raise to stop generation - we don't want partial results
                raise Exception(f"Failed to generate image for scene {i+1}: {str(e)}") from e

        # Save metadata with scene locations and anchor texts
        logger.info("💾 Step 5: Saving metadata...")
        save_image_metadata(book_id, chapter_index, image_paths, scene_locations, anchor_texts, status="completed")
        logger.success("=" * 60)
        logger.success("🎉 GENERATION COMPLETE!")
        logger.success("=" * 60)
        logger.success(f"Generated {len(image_paths)} images: {image_paths}")

        return image_paths

    except Exception as e:
        # Save error to metadata
        error_message = str(e)
        logger.error(f"❌ Generation failed: {error_message}")

        # Extract a user-friendly error message
        if "No image data found in response" in error_message:
            if "blocked by safety filters" in error_message:
                user_error = "Image generation blocked by safety filters. Try regenerating with different content."
            else:
                user_error = "Image generation failed - no image data received from API."
        elif "Failed to generate image for scene" in error_message:
            user_error = error_message  # Already user-friendly
        else:
            user_error = f"Generation error: {error_message}"

        save_image_metadata(book_id, chapter_index, [], status="error", error=user_error)
        logger.error(f"❌ Saved error to metadata: {user_error}")

        # Re-raise to ensure the error is logged
        raise


def find_insertion_point(
    paragraphs: List,
    anchor_text: Optional[str],
    fallback_percent: int,
    scene_number: int
) -> int:
    """
    Find the paragraph index after which to insert an illustration.

    Searches for the paragraph containing the anchor sentence, then inserts after it.
    Uses fuzzy matching with threshold, falls back to percentage if no good match.

    Args:
        paragraphs: List of BeautifulSoup paragraph tags
        anchor_text: The sentence that should appear in the paragraph before insertion (from Gemini)
        fallback_percent: Percentage-based location (0-100) as fallback
        scene_number: Scene number for logging

    Returns:
        Paragraph index (0-based) - illustration will be inserted AFTER this paragraph
    """
    # Fallback if no anchor text
    if not anchor_text or not anchor_text.strip():
        logger.warning(f"Scene {scene_number}: No anchor text, using percentage ({fallback_percent}%)")
        para_idx = int((fallback_percent / 100) * len(paragraphs))
        return min(para_idx, len(paragraphs) - 1)

    # Try fuzzy matching
    try:
        from rapidfuzz import fuzz
    except ImportError:
        logger.error("rapidfuzz not installed, falling back to percentage")
        para_idx = int((fallback_percent / 100) * len(paragraphs))
        return min(para_idx, len(paragraphs) - 1)

    # Extract text from all paragraphs (cache to avoid repeated calls)
    paragraph_texts = [para.get_text(separator=' ', strip=True) for para in paragraphs]

    # Configuration
    SIMILARITY_THRESHOLD = 80  # Require 80% similarity (0-100 scale)
    PARTIAL_THRESHOLD = 85     # Higher threshold for partial matching

    # Clean anchor text
    anchor_clean = ' '.join(anchor_text.split())

    # Try exact match first (case-insensitive)
    # Find paragraph containing the anchor sentence
    for i, para_text in enumerate(paragraph_texts):
        if anchor_clean.lower() in para_text.lower():
            logger.success(f"Scene {scene_number}: Exact match found in paragraph {i}")
            logger.debug(f"  Anchor sentence: '{anchor_clean[:80]}...'")
            logger.debug(f"  Found in paragraph: '{para_text[:100]}...'")
            logger.info(f"  → Illustration will be inserted AFTER paragraph {i}")
            return i

    # Try fuzzy matching with full ratio
    best_match_idx = -1
    best_match_score = 0

    for i, para_text in enumerate(paragraph_texts):
        score = fuzz.ratio(anchor_clean.lower(), para_text.lower())
        if score > best_match_score:
            best_match_score = score
            best_match_idx = i

    # Check if best match exceeds threshold
    if best_match_score >= SIMILARITY_THRESHOLD:
        logger.success(f"Scene {scene_number}: Fuzzy match (score={best_match_score:.1f}) found in paragraph {best_match_idx}")
        logger.debug(f"  Anchor sentence: '{anchor_clean[:80]}...'")
        logger.debug(f"  Matched paragraph: '{paragraph_texts[best_match_idx][:80]}...'")
        logger.info(f"  → Illustration will be inserted AFTER paragraph {best_match_idx}")
        return best_match_idx

    # Try partial ratio (substring matching)
    best_partial_idx = -1
    best_partial_score = 0

    for i, para_text in enumerate(paragraph_texts):
        score = fuzz.partial_ratio(anchor_clean.lower(), para_text.lower())
        if score > best_partial_score:
            best_partial_score = score
            best_partial_idx = i

    if best_partial_score >= PARTIAL_THRESHOLD:
        logger.success(f"Scene {scene_number}: Partial match (score={best_partial_score:.1f}) found in paragraph {best_partial_idx}")
        logger.debug(f"  Anchor sentence: '{anchor_clean[:80]}...'")
        logger.debug(f"  Matched paragraph: '{paragraph_texts[best_partial_idx][:80]}...'")
        logger.info(f"  → Illustration will be inserted AFTER paragraph {best_partial_idx}")
        return best_partial_idx

    # No good match - fall back to percentage
    logger.warning(
        f"Scene {scene_number}: No match above threshold "
        f"(best={best_match_score:.1f}/{best_partial_score:.1f}), "
        f"using percentage ({fallback_percent}%)"
    )
    logger.debug(f"  Failed anchor: '{anchor_clean[:100]}...'")
    if best_match_idx >= 0:
        logger.debug(f"  Best match: '{paragraph_texts[best_match_idx][:100]}...'")

    para_idx = int((fallback_percent / 100) * len(paragraphs))
    return min(para_idx, len(paragraphs) - 1)


def inject_images_into_html(
    html_content: str,
    image_paths: List[str],
    scene_locations: List[int],
    anchor_texts: Optional[List[Optional[str]]] = None
) -> str:
    """
    Inject image HTML into chapter content at appropriate locations.

    Args:
        html_content: Original HTML content
        image_paths: List of image paths (relative, e.g., "images/generated_ch0_scene1.png")
        scene_locations: List of location percentages (0-100) for each scene (fallback)
        anchor_texts: List of anchor sentences for precise placement (optional)

    Returns:
        Modified HTML with images inserted
    """
    if not image_paths:
        return html_content

    soup = BeautifulSoup(html_content, 'html.parser')

    # Find all paragraphs
    paragraphs = soup.find_all('p')

    if not paragraphs:
        # If no paragraphs, just append images at the end
        logger.warning("No paragraphs found in HTML, appending images at end")
        for img_path in image_paths:
            img_tag = soup.new_tag('img', src=img_path)
            img_tag['style'] = 'max-width: 100%; height: auto; display: block; margin: 20px auto;'
            soup.append(img_tag)
        return str(soup)

    # Calculate insertion points using new smart matching
    insertion_points = []
    for i in range(len(image_paths)):
        # Get anchor text (handle None or missing)
        anchor_text = None
        if anchor_texts and i < len(anchor_texts):
            anchor_text = anchor_texts[i]

        # Get fallback percentage
        fallback_percent = scene_locations[i] if i < len(scene_locations) else 50

        # Find insertion point (uses new find_insertion_point function)
        para_idx = find_insertion_point(
            paragraphs=paragraphs,
            anchor_text=anchor_text,
            fallback_percent=fallback_percent,
            scene_number=i + 1
        )

        insertion_points.append((para_idx, image_paths[i]))
        logger.info(f"Scene {i+1}: Will insert after paragraph {para_idx}/{len(paragraphs)}")

    # Sort by paragraph index (descending) so we can insert without shifting indices
    insertion_points.sort(reverse=True, key=lambda x: x[0])

    # Insert images after the specified paragraphs
    for para_idx, img_path in insertion_points:
        if para_idx < len(paragraphs):
            para = paragraphs[para_idx]
            img_tag = soup.new_tag('img', src=img_path)
            img_tag['style'] = 'max-width: 100%; height: auto; display: block; margin: 20px auto;'
            img_tag['alt'] = 'Generated illustration for scene'
            # Insert after the paragraph
            para.insert_after(img_tag)
    
    return str(soup)

