"""
Module for generating AI illustrations for ebook chapters using Gemini API.
"""

import os
import json
import base64
from typing import List, Dict, Optional
from bs4 import BeautifulSoup

try:
    from google import genai
except ImportError:
    genai = None


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
1. A brief summary (2-3 sentences)
2. An approximate location in the text (as a percentage: 0-100, where 0 is the beginning and 100 is the end)

Format your response as JSON with this structure:
{{
    "scenes": [
        {{
            "scene_number": 1,
            "summary": "Brief description of the scene",
            "location_percent": 25
        }},
        {{
            "scene_number": 2,
            "summary": "Brief description of the scene",
            "location_percent": 50
        }},
        {{
            "scene_number": 3,
            "summary": "Brief description of the scene",
            "location_percent": 75
        }}
    ]
}}

Chapter text:
{chapter_text[:50000]}  # Limit to 50k chars to avoid token limits
"""
    
    print(f"[DEBUG] ===== summarize_scenes: Sending request to Gemini ======")
    print(f"[DEBUG] Chapter text length: {len(chapter_text)} chars (sending first 50000)")
    print(f"[DEBUG] Model: gemini-2.0-flash-exp")
    print(f"[DEBUG] Prompt length: {len(prompt)} chars")
    
    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash-exp",
            contents=prompt
        )
        
        print(f"[DEBUG] Response received from Gemini")
        print(f"[DEBUG] Response type: {type(response)}")
        print(f"[DEBUG] Response parts count: {len(response.parts) if hasattr(response, 'parts') else 'N/A'}")
        
        # Extract text response
        response_text = ""
        for i, part in enumerate(response.parts):
            print(f"[DEBUG] Part {i}: type={type(part)}, has text={hasattr(part, 'text')}")
            if hasattr(part, 'text') and part.text:
                response_text += part.text
                print(f"[DEBUG] Part {i} text length: {len(part.text)} chars")
        
        print(f"[DEBUG] Full response text length: {len(response_text)} chars")
        print(f"[DEBUG] Response text (first 1000 chars): {response_text[:1000]}")
        
        # Parse JSON response
        # Sometimes Gemini wraps JSON in markdown code blocks
        response_text = response_text.strip()
        if response_text.startswith("```"):
            print(f"[DEBUG] Response wrapped in code block, extracting JSON...")
            # Extract JSON from code block
            lines = response_text.split("\n")
            response_text = "\n".join(lines[1:-1]) if len(lines) > 2 else response_text
            print(f"[DEBUG] Extracted JSON length: {len(response_text)} chars")
        
        print(f"[DEBUG] Attempting to parse JSON...")
        data = json.loads(response_text)
        print(f"[DEBUG] JSON parsed successfully")
        scenes = data.get("scenes", [])
        print(f"[DEBUG] Found {len(scenes)} scenes in response")
        
        # Ensure we have exactly 3 scenes, pad if needed
        while len(scenes) < 3:
            scenes.append({
                "scene_number": len(scenes) + 1,
                "summary": "A scene from the chapter",
                "location_percent": 33 * len(scenes)
            })
        
        print(f"[DEBUG] Returning {len(scenes[:3])} scenes")
        for i, scene in enumerate(scenes[:3]):
            print(f"[DEBUG] Scene {i+1}: number={scene.get('scene_number')}, location={scene.get('location_percent')}%, summary_length={len(scene.get('summary', ''))}")
        
        return scenes[:3]  # Return only first 3
        
    except json.JSONDecodeError as e:
        print(f"[DEBUG] ===== ERROR: JSON parsing failed ======")
        print(f"[DEBUG] Error: {e}")
        print(f"[DEBUG] Response text (first 2000 chars): {response_text[:2000]}")
        print(f"[DEBUG] Full response text length: {len(response_text)}")
        # Fallback: create generic scenes
        print(f"[DEBUG] Using fallback scenes")
        return [
            {"scene_number": 1, "summary": "An important scene from the chapter", "location_percent": 25},
            {"scene_number": 2, "summary": "Another important scene from the chapter", "location_percent": 50},
            {"scene_number": 3, "summary": "A third important scene from the chapter", "location_percent": 75},
        ]
    except Exception as e:
        print(f"[DEBUG] ===== ERROR: Exception in summarize_scenes ======")
        print(f"[DEBUG] Error type: {type(e).__name__}")
        print(f"[DEBUG] Error message: {str(e)}")
        import traceback
        print(f"[DEBUG] Traceback:\n{traceback.format_exc()}")
        raise


def create_image_prompt(scene_summary: str, book_title: str = "") -> str:
    """
    Takes a scene summary and creates a detailed, descriptive prompt for image generation.

    Args:
        scene_summary: Summary of the scene to illustrate
        book_title: Title of the book for thematic context
    """
    book_context = f" from the book '{book_title}'" if book_title else " from a book"

    prompt = f"""Create a detailed, cinematic illustration of this scene{book_context}:

{scene_summary}

The image should be:
- High quality and visually appealing
- Appropriate for a book illustration
- Capturing the mood and atmosphere of the scene
- Detailed and evocative
- In a style suitable for a literary work{f" and consistent with the themes of '{book_title}'" if book_title else ""}

Generate a beautiful illustration that captures the essence of this scene."""

    print(f"[DEBUG] Created image prompt (length: {len(prompt)} chars)")
    print(f"[DEBUG] Prompt preview: {prompt[:200]}...")

    return prompt


def generate_image(prompt: str) -> bytes:
    """
    Uses Nano Banana API (gemini-2.5-flash-image model) to generate image bytes.
    
    Returns image bytes (PNG format).
    """
    print(f"[DEBUG] ===== generate_image: Starting image generation ======")
    print(f"[DEBUG] Model: gemini-2.5-flash-image")
    print(f"[DEBUG] Prompt length: {len(prompt)} chars")
    
    client = get_gemini_client()
    
    try:
        print(f"[DEBUG] Sending request to Gemini...")
        response = client.models.generate_content(
            model="gemini-2.5-flash-image",
            contents=prompt
        )
        
        print(f"[DEBUG] Response received from Gemini")
        print(f"[DEBUG] Response type: {type(response)}")
        print(f"[DEBUG] Response parts count: {len(response.parts) if hasattr(response, 'parts') else 'N/A'}")
        
        # Extract image bytes from response
        for i, part in enumerate(response.parts):
            print(f"[DEBUG] Processing part {i}: type={type(part)}")
            print(f"[DEBUG] Part {i} attributes: {dir(part)}")

            # Primary method: try inline_data first (most reliable for Gemini image responses)
            if hasattr(part, 'inline_data') and part.inline_data:
                print(f"[DEBUG] Part {i} has inline_data attribute")
                print(f"[DEBUG] inline_data type: {type(part.inline_data)}")
                print(f"[DEBUG] inline_data attributes: {dir(part.inline_data)}")
                try:
                    # inline_data.data might be base64 encoded or raw bytes
                    data = part.inline_data.data
                    print(f"[DEBUG] inline_data.data type: {type(data)}")

                    if isinstance(data, bytes):
                        # If it's already bytes, use directly
                        print(f"[DEBUG] Data is bytes, length: {len(data)} bytes")
                        return data
                    elif isinstance(data, str):
                        # If it's a string, it's likely base64
                        print(f"[DEBUG] Data is string (length: {len(data)}), decoding as base64...")
                        image_bytes = base64.b64decode(data)
                        print(f"[DEBUG] Decoded to {len(image_bytes)} bytes")
                        return image_bytes
                    else:
                        print(f"[DEBUG] Unexpected data type: {type(data)}")
                except Exception as e:
                    print(f"[DEBUG] Error processing inline_data: {type(e).__name__}: {e}")
                    import traceback
                    print(f"[DEBUG] Traceback:\n{traceback.format_exc()}")

            # Fallback: try text field (might be base64 encoded image)
            if hasattr(part, 'text') and part.text:
                print(f"[DEBUG] Part {i} has text field, trying as base64...")
                try:
                    image_bytes = base64.b64decode(part.text)
                    print(f"[DEBUG] Successfully decoded text as base64: {len(image_bytes)} bytes")
                    return image_bytes
                except Exception as e:
                    print(f"[DEBUG] Text field is not base64 image data: {type(e).__name__}")
        
        print(f"[DEBUG] ===== ERROR: No image data found in response ======")
        print(f"[DEBUG] Checked {len(response.parts)} parts, none contained image data")
        raise ValueError("No image data found in response")
        
    except Exception as e:
        print(f"[DEBUG] ===== ERROR: Exception in generate_image ======")
        print(f"[DEBUG] Error type: {type(e).__name__}")
        print(f"[DEBUG] Error message: {str(e)}")
        import traceback
        print(f"[DEBUG] Traceback:\n{traceback.format_exc()}")
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


def generate_illustrations_for_chapter(book_id: str, chapter_index: int, chapter_text: str, book_title: str = "", chapter_title: str = "") -> List[str]:
    """
    Main function to generate illustrations for a chapter.

    Args:
        book_id: The book directory name
        chapter_index: Index of the chapter in the book's spine
        chapter_text: Full text content of the chapter
        book_title: Title of the book for thematic context in image generation
        chapter_title: Title of the chapter for filename generation

    Returns:
        List of image paths (relative to book directory)
    """
    print(f"[DEBUG] ===== generate_illustrations_for_chapter ======")
    print(f"[DEBUG] Book ID: {book_id}")
    print(f"[DEBUG] Book Title: {book_title}")
    print(f"[DEBUG] Chapter Index: {chapter_index}")
    print(f"[DEBUG] Chapter Title: {chapter_title}")
    print(f"[DEBUG] Chapter text length: {len(chapter_text)} chars")

    # Check cache first
    cached = get_cached_images(book_id, chapter_index)
    if cached:
        print(f"[DEBUG] Found cached images: {cached}")
        return cached

    print(f"[DEBUG] No cached images, generating new ones...")

    # Generate scenes
    print(f"[DEBUG] Step 1: Summarizing scenes...")
    scenes = summarize_scenes(chapter_text)
    print(f"[DEBUG] Got {len(scenes)} scenes")

    image_paths = []
    scene_locations = []

    for i, scene in enumerate(scenes):
        print(f"[DEBUG] ===== Processing Scene {i+1}/{len(scenes)} ======")
        scene_num = scene["scene_number"]
        scene_summary = scene["summary"]
        scene_location = scene.get("location_percent", 33 * (scene_num - 1))
        scene_locations.append(scene_location)

        print(f"[DEBUG] Scene {i+1} summary: {scene_summary[:100]}...")
        print(f"[DEBUG] Scene {i+1} location: {scene_location}%")

        # Create image prompt
        print(f"[DEBUG] Step 2: Creating image prompt for scene {i+1}...")
        prompt = create_image_prompt(scene_summary, book_title)

        # Generate image
        print(f"[DEBUG] Step 3: Generating image for scene {i+1}...")
        image_bytes = generate_image(prompt)
        print(f"[DEBUG] Generated image: {len(image_bytes)} bytes")

        # Save image
        print(f"[DEBUG] Step 4: Saving image for scene {i+1}...")
        img_path = save_image(image_bytes, book_id, chapter_index, scene_num, chapter_title)
        print(f"[DEBUG] Saved image to: {img_path}")
        image_paths.append(img_path)

    # Save metadata with scene locations
    print(f"[DEBUG] Step 5: Saving metadata...")
    save_image_metadata(book_id, chapter_index, image_paths, scene_locations)
    print(f"[DEBUG] ===== Generation complete! ======")
    print(f"[DEBUG] Generated {len(image_paths)} images: {image_paths}")

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

