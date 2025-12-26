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


def summarize_scenes(chapter_text: str) -> List[Dict]:
    """
    Sends chapter text to Gemini 3.0 Flash asking for 3 main scene summaries.

    Returns list of scene dicts with:
    - summary: str - summary of the scene
    - location_in_text: int - approximate character position (0-100 percentage)
    - scene_number: int - 1, 2, or 3
    """
    if not chapter_text or len(chapter_text.strip()) == 0:
        return []

    client = get_gemini_client()

    prompt = f"""Analyze the following chapter from a book and identify the 3 most important scenes.
For each scene, provide:
1. A detailed summary of the scence used for illustratino generation later, including settings, people and atomsphere (around 500 words)
2. An approximate location in the text (as a percentage: 0-100, where 0 is the beginning and 100 is the end)

Format your response as JSON with this structure:
{{
    "scenes": [
        {{
            "scene_number": 1,
            "summary": "description of the scene",
            "location_percent": 25
        }},
        {{
            "scene_number": 2,
            "summary": "description of the scene",
            "location_percent": 50
        }},
        {{
            "scene_number": 3,
            "summary": "description of the scene",
            "location_percent": 75
        }}
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

        # Ensure we have exactly 3 scenes, pad if needed
        while len(scenes) < 3:
            scenes.append({
                "scene_number": len(scenes) + 1,
                "summary": "A scene from the chapter",
                "location_percent": 33 * len(scenes)
            })

        logger.info(f"Returning {len(scenes[:3])} scenes")
        for i, scene in enumerate(scenes[:3]):
            logger.debug(f"Scene {i+1}: number={scene.get('scene_number')}, location={scene.get('location_percent')}%, summary_length={len(scene.get('summary', ''))}")

        return scenes[:3]  # Return only first 3

    except json.JSONDecodeError as e:
        logger.error("❌ JSON parsing failed")
        logger.error(f"Error: {e}")
        logger.debug(f"Response text (first 2000 chars): {response_text[:2000]}")
        logger.debug(f"Full response text length: {len(response_text)}")
        # Fallback: create generic scenes
        logger.warning("⚠️ Using fallback scenes")
        return [
            {"scene_number": 1, "summary": "An important scene from the chapter", "location_percent": 25},
            {"scene_number": 2, "summary": "Another important scene from the chapter", "location_percent": 50},
            {"scene_number": 3, "summary": "A third important scene from the chapter", "location_percent": 75},
        ]
    except Exception as e:
        logger.exception(f"❌ Exception in summarize_scenes: {type(e).__name__}: {str(e)}")
        raise


def create_image_prompt(scene_summary: str, book_title: str = "") -> str:
    """
    Takes a scene summary and creates a detailed, descriptive prompt for image generation.

    Args:
        scene_summary: Summary of the scene to illustrate
        book_title: Title of the book for thematic context
    """
    book_context = f" from the book '{book_title}'" if book_title else " from a book"

    prompt = f"""Create a detailed, cinematic illustration of this scene {book_context}:

{scene_summary}

The image should be:
- High quality and visually appealing
- Appropriate for a book illustration
- Capturing the mood and atmosphere of the scene
- Do not include any text in the image. Avoid making it like a comic
- Detailed and evocative
- In a style suitable for a literary work{f" and consistent with the themes of '{book_title}'" if book_title else ""}

Generate a beautiful illustration that captures the essence of this scene."""

    logger.debug(f"Created image prompt (length: {len(prompt)} chars)")
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
            
            if len(existing_paths) == 3:  # All 3 images exist
                return existing_paths
        
        return None
    except Exception as e:
        print(f"Error reading cache metadata: {e}")
        return None


def save_image_metadata(book_id: str, chapter_index: int, image_paths: List[str], scene_locations: Optional[List[int]] = None):
    """
    Save metadata about generated images to track caching.
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
        "images": image_paths
    }
    if scene_locations:
        chapter_data["scene_locations"] = scene_locations
    metadata[chapter_key] = chapter_data
    
    # Save back
    with open(metadata_file, "w") as f:
        json.dump(metadata, f, indent=2)


def generate_illustrations_for_chapter(book_id: str, chapter_index: int, chapter_text: str, book_title: str = "", chapter_title: str = "", force_regenerate: bool = False) -> List[str]:
    """
    Main function to generate illustrations for a chapter.

    Args:
        book_id: The book directory name
        chapter_index: Index of the chapter in the book's spine
        chapter_text: Full text content of the chapter
        book_title: Title of the book for thematic context in image generation
        chapter_title: Title of the chapter for filename generation
        force_regenerate: If True, regenerate images even if cached versions exist

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

    # Check cache first (unless force_regenerate is True)
    if not force_regenerate:
        cached = get_cached_images(book_id, chapter_index)
        if cached:
            logger.success(f"✅ Found cached images: {cached}")
            return cached

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

    logger.info("🆕 Generating new images...")

    # Generate scenes
    logger.info("📋 Step 1: Summarizing scenes...")
    scenes = summarize_scenes(chapter_text)
    logger.success(f"✅ Got {len(scenes)} scenes")

    image_paths = []
    scene_locations = []

    for i, scene in enumerate(scenes):
        logger.info("=" * 60)
        logger.info(f"🎨 Processing Scene {i+1}/{len(scenes)}")
        logger.info("=" * 60)
        scene_num = scene["scene_number"]
        scene_summary = scene["summary"]
        scene_location = scene.get("location_percent", 33 * (scene_num - 1))
        scene_locations.append(scene_location)

        logger.info(f"Summary: {scene_summary[:100]}...")
        logger.info(f"Location: {scene_location}%")

        try:
            # Create image prompt
            logger.info(f"📝 Step 2: Creating image prompt for scene {i+1}...")
            prompt = create_image_prompt(scene_summary, book_title)

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

        except Exception as e:
            logger.error("=" * 60)
            logger.error(f"❌ ERROR processing scene {i+1}")
            logger.error("=" * 60)
            logger.error(f"Error type: {type(e).__name__}")
            logger.error(f"Error message: {str(e)}")
            logger.exception("Full traceback:")
            # Re-raise to stop generation - we don't want partial results
            raise Exception(f"Failed to generate image for scene {i+1}: {str(e)}") from e

    # Save metadata with scene locations
    logger.info("💾 Step 5: Saving metadata...")
    save_image_metadata(book_id, chapter_index, image_paths, scene_locations)
    logger.success("=" * 60)
    logger.success("🎉 GENERATION COMPLETE!")
    logger.success("=" * 60)
    logger.success(f"Generated {len(image_paths)} images: {image_paths}")

    return image_paths


def inject_images_into_html(html_content: str, image_paths: List[str], scene_locations: List[int]) -> str:
    """
    Inject image HTML into chapter content at appropriate locations.
    
    Args:
        html_content: Original HTML content
        image_paths: List of image paths (relative, e.g., "images/generated_ch0_scene1.png")
        scene_locations: List of location percentages (0-100) for each scene
    
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
        for img_path in image_paths:
            img_tag = soup.new_tag('img', src=img_path)
            img_tag['style'] = 'max-width: 100%; height: auto; display: block; margin: 20px auto;'
            soup.append(img_tag)
        return str(soup)
    
    # Calculate insertion points based on scene locations
    insertion_points = []
    for i, loc_percent in enumerate(scene_locations):
        # Convert percentage to paragraph index
        para_idx = int((loc_percent / 100) * len(paragraphs))
        para_idx = min(para_idx, len(paragraphs) - 1)
        insertion_points.append((para_idx, image_paths[i]))
    
    # Sort by paragraph index (descending) so we can insert without shifting indices
    insertion_points.sort(reverse=True, key=lambda x: x[0])
    
    # Insert images after the specified paragraphs
    for para_idx, img_path in insertion_points:
        if para_idx < len(paragraphs):
            para = paragraphs[para_idx]
            img_tag = soup.new_tag('img', src=img_path)
            img_tag['style'] = 'max-width: 100%; height: auto; display: block; margin: 20px auto;'
            img_tag['alt'] = f'Generated illustration for scene'
            # Insert after the paragraph
            para.insert_after(img_tag)
    
    return str(soup)

