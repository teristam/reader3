"""
Module for generating text-to-speech audio for EPUB paragraphs using Gemini API.
"""

import os
import json
import hashlib
import wave
import base64
import io
from datetime import datetime
from typing import Optional, Dict

try:
    from google import genai
except ImportError:
    genai = None


def get_gemini_client():
    """Initialize and return Gemini client."""
    if genai is None:
        raise ImportError("google-genai package not installed. Run: uv pip install google-genai")

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable not set")

    return genai.Client(api_key=api_key)


def generate_paragraph_hash(paragraph_text: str) -> str:
    """
    Generate unique hash for paragraph text.

    Args:
        paragraph_text: The paragraph text to hash

    Returns:
        First 16 characters of MD5 hash
    """
    return hashlib.md5(paragraph_text.encode('utf-8')).hexdigest()[:16]


def generate_tts_audio(text: str, voice_name: str = "Kore") -> bytes:
    """
    Call Gemini API to generate text-to-speech audio.

    Args:
        text: The text to convert to speech
        voice_name: Voice to use (default: "Kore")

    Returns:
        Raw PCM audio bytes (24kHz, 16-bit, mono)
    """
    print(f"[TTS DEBUG] Generating TTS for text (length: {len(text)} chars)")
    print(f"[TTS DEBUG] Using voice: {voice_name}")
    print(f"[TTS DEBUG] Model: gemini-2.5-flash-preview-tts")

    client = get_gemini_client()

    try:
        # Generate audio using Gemini TTS API
        response = client.models.generate_content(
            model="gemini-2.5-flash-preview-tts",
            contents=text,
            config={
                "response_modalities": ["AUDIO"],
                "speech_config": {
                    "voice_config": {
                        "prebuilt_voice_config": {
                            "voice_name": voice_name
                        }
                    }
                }
            }
        )

        print(f"[TTS DEBUG] Response received from Gemini")
        print(f"[TTS DEBUG] Response parts count: {len(response.parts) if hasattr(response, 'parts') else 'N/A'}")

        # Extract audio data from response
        for i, part in enumerate(response.parts):
            print(f"[TTS DEBUG] Processing part {i}: type={type(part)}")

            # Try inline_data first (most reliable for Gemini audio responses)
            if hasattr(part, 'inline_data') and part.inline_data:
                print(f"[TTS DEBUG] Part {i} has inline_data attribute")
                try:
                    data = part.inline_data.data
                    print(f"[TTS DEBUG] inline_data.data type: {type(data)}")

                    if isinstance(data, bytes):
                        # Already bytes, use directly
                        print(f"[TTS DEBUG] Data is bytes, length: {len(data)} bytes")
                        return data
                    elif isinstance(data, str):
                        # Base64 encoded, decode it
                        print(f"[TTS DEBUG] Data is string (length: {len(data)}), decoding as base64...")
                        audio_bytes = base64.b64decode(data)
                        print(f"[TTS DEBUG] Decoded to {len(audio_bytes)} bytes")
                        return audio_bytes
                    else:
                        print(f"[TTS DEBUG] Unexpected data type: {type(data)}")
                except Exception as e:
                    print(f"[TTS DEBUG] Error processing inline_data: {type(e).__name__}: {e}")

            # Fallback: try text field (might be base64 encoded)
            if hasattr(part, 'text') and part.text:
                print(f"[TTS DEBUG] Part {i} has text field, trying as base64...")
                try:
                    audio_bytes = base64.b64decode(part.text)
                    print(f"[TTS DEBUG] Successfully decoded text as base64: {len(audio_bytes)} bytes")
                    return audio_bytes
                except Exception as e:
                    print(f"[TTS DEBUG] Text field is not base64 audio data: {type(e).__name__}")

        print(f"[TTS ERROR] No audio data found in response")
        raise ValueError("No audio data found in response")

    except Exception as e:
        print(f"[TTS ERROR] Exception in generate_tts_audio: {type(e).__name__}: {e}")
        import traceback
        print(f"[TTS ERROR] Traceback:\n{traceback.format_exc()}")
        raise


def convert_pcm_to_wav(pcm_data: bytes) -> bytes:
    """
    Convert raw PCM data to WAV format.

    Args:
        pcm_data: Raw PCM audio bytes

    Returns:
        WAV file bytes
    """
    print(f"[TTS DEBUG] Converting PCM to WAV (input: {len(pcm_data)} bytes)")

    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as wf:
        wf.setnchannels(1)      # Mono
        wf.setsampwidth(2)      # 16-bit
        wf.setframerate(24000)  # 24kHz
        wf.writeframes(pcm_data)

    wav_bytes = buffer.getvalue()
    print(f"[TTS DEBUG] Converted to WAV (output: {len(wav_bytes)} bytes)")
    return wav_bytes


def save_audio_file(audio_bytes: bytes, book_id: str, para_hash: str) -> str:
    """
    Save audio file to disk.

    Args:
        audio_bytes: WAV audio data
        book_id: Book directory name
        para_hash: Paragraph hash

    Returns:
        Relative path to saved audio file
    """
    # Ensure audio directory exists
    audio_dir = os.path.join(book_id, "audio")
    os.makedirs(audio_dir, exist_ok=True)

    # Create filename
    filename = f"tts_{para_hash}.wav"
    filepath = os.path.join(audio_dir, filename)

    # Save audio
    with open(filepath, "wb") as f:
        f.write(audio_bytes)

    print(f"[TTS DEBUG] Saved audio to: {filepath}")

    # Return relative path
    return f"audio/{filename}"


def get_cached_audio(book_id: str, para_hash: str) -> Optional[str]:
    """
    Check if audio is cached for a paragraph.

    Args:
        book_id: Book directory name
        para_hash: Paragraph hash

    Returns:
        Audio path if cached, None otherwise
    """
    metadata_file = os.path.join(book_id, "tts_metadata.json")

    if not os.path.exists(metadata_file):
        return None

    try:
        with open(metadata_file, "r") as f:
            metadata = json.load(f)

        if para_hash in metadata:
            audio_path = metadata[para_hash]["audio_path"]

            # Verify file actually exists
            full_path = os.path.join(book_id, audio_path)
            if os.path.exists(full_path):
                print(f"[TTS DEBUG] Found cached audio: {audio_path}")
                return audio_path
            else:
                print(f"[TTS DEBUG] Metadata exists but file missing: {full_path}")
                return None

        return None
    except Exception as e:
        print(f"[TTS ERROR] Error reading cache metadata: {e}")
        return None


def save_tts_metadata(book_id: str, para_hash: str, audio_path: str, text_preview: str, text_length: int, voice: str = "Kore"):
    """
    Save metadata about generated TTS audio.

    Args:
        book_id: Book directory name
        para_hash: Paragraph hash
        audio_path: Relative path to audio file
        text_preview: First 100 chars of paragraph
        text_length: Full length of paragraph text
        voice: Voice used for generation
    """
    metadata_file = os.path.join(book_id, "tts_metadata.json")

    # Load existing metadata
    metadata = {}
    if os.path.exists(metadata_file):
        try:
            with open(metadata_file, "r") as f:
                metadata = json.load(f)
        except:
            metadata = {}

    # Add new entry
    metadata[para_hash] = {
        "audio_path": audio_path,
        "text_preview": text_preview,
        "created_at": datetime.now().isoformat(),
        "voice": voice,
        "text_length": text_length
    }

    # Save back
    with open(metadata_file, "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"[TTS DEBUG] Saved metadata for hash: {para_hash}")


def generate_tts_for_paragraph(book_id: str, para_text: str, voice: str = "Kore") -> Dict:
    """
    Main function to generate TTS audio for a paragraph.

    Args:
        book_id: Book directory name
        para_text: Paragraph text
        voice: Voice to use (default: "Kore")

    Returns:
        Dictionary with status, audio_path, and para_hash
    """
    print(f"[TTS DEBUG] ===== generate_tts_for_paragraph =====")
    print(f"[TTS DEBUG] Book ID: {book_id}")
    print(f"[TTS DEBUG] Text length: {len(para_text)} chars")
    print(f"[TTS DEBUG] Voice: {voice}")

    # Generate hash
    para_hash = generate_paragraph_hash(para_text)
    print(f"[TTS DEBUG] Paragraph hash: {para_hash}")

    # Check cache (double-check to handle race conditions)
    cached = get_cached_audio(book_id, para_hash)
    if cached:
        print(f"[TTS DEBUG] Found in cache: {cached}")
        return {
            "status": "success",
            "audio_path": cached,
            "para_hash": para_hash
        }

    # Validate text length
    MAX_LENGTH = 5000
    if len(para_text) > MAX_LENGTH:
        print(f"[TTS ERROR] Text too long: {len(para_text)} > {MAX_LENGTH}")
        raise ValueError(f"Text too long (max {MAX_LENGTH} characters)")

    try:
        # Generate TTS audio
        print(f"[TTS DEBUG] Step 1: Calling Gemini TTS API...")
        pcm_audio = generate_tts_audio(para_text, voice)

        # Convert to WAV
        print(f"[TTS DEBUG] Step 2: Converting to WAV...")
        wav_audio = convert_pcm_to_wav(pcm_audio)

        # Save audio file
        print(f"[TTS DEBUG] Step 3: Saving audio file...")
        audio_path = save_audio_file(wav_audio, book_id, para_hash)

        # Save metadata
        print(f"[TTS DEBUG] Step 4: Saving metadata...")
        text_preview = para_text[:100] + "..." if len(para_text) > 100 else para_text
        save_tts_metadata(book_id, para_hash, audio_path, text_preview, len(para_text), voice)

        print(f"[TTS DEBUG] ===== Generation complete! =====")
        print(f"[TTS DEBUG] Audio path: {audio_path}")

        return {
            "status": "success",
            "audio_path": audio_path,
            "para_hash": para_hash
        }

    except Exception as e:
        print(f"[TTS ERROR] Failed to generate TTS: {type(e).__name__}: {e}")
        raise
