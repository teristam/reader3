"""
Pytest configuration and shared fixtures for testing.
"""

import os
import tempfile
import json
import pytest
from unittest.mock import MagicMock, Mock


@pytest.fixture
def temp_book_dir():
    """Create a temporary directory for test book data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create images subdirectory
        images_dir = os.path.join(tmpdir, "images")
        os.makedirs(images_dir, exist_ok=True)
        yield tmpdir


@pytest.fixture
def sample_chapter_text():
    """Sample chapter text for testing scene analysis."""
    return """
    Chapter 1: The Beginning

    It was a dark and stormy night. John sat by the fireplace, contemplating his next move.
    The letter from his estranged father had arrived that morning, and it changed everything.

    He picked up the letter again, reading the words that had been burned into his memory:
    "Come to the old mansion on Willow Street. Time is running out."

    By midnight, John had made his decision. He grabbed his coat and headed out into the storm.
    The rain pelted against his face as he walked through the empty streets.

    When he finally reached the mansion, he found the door slightly ajar. A faint light
    flickered from within. Taking a deep breath, John pushed the door open and stepped inside.

    The interior was dusty and abandoned, but there, in the center of the grand hall,
    stood his father. "You came," the old man said, tears streaming down his face.
    "I wasn't sure you would."
    """


@pytest.fixture
def sample_scenes():
    """Sample scene analysis response from Gemini."""
    return [
        {
            "scene_number": 1,
            "summary": "John receives a mysterious letter from his estranged father, sitting by the fireplace on a stormy night.",
            "location_percent": 20
        },
        {
            "scene_number": 2,
            "summary": "John walks through the storm at midnight, making his way to the old mansion on Willow Street.",
            "location_percent": 50
        },
        {
            "scene_number": 3,
            "summary": "John enters the abandoned mansion and reunites with his father in the grand hall.",
            "location_percent": 85
        }
    ]


@pytest.fixture
def mock_gemini_client():
    """Mock Gemini API client."""
    client = MagicMock()

    # Mock the models.generate_content method
    client.models = MagicMock()

    return client


@pytest.fixture
def mock_scene_response(sample_scenes):
    """Mock response from Gemini scene analysis API."""
    response = MagicMock()
    response.parts = [MagicMock()]
    response.parts[0].text = json.dumps({
        "scenes": sample_scenes
    })
    return response


@pytest.fixture
def mock_image_response():
    """Mock response from Gemini image generation API."""
    # Create a minimal valid PNG (1x1 transparent pixel)
    # Make it larger than 1000 bytes to pass validation
    png_header = b'\x89PNG\r\n\x1a\n'  # PNG signature
    ihdr_chunk = (
        b'\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
        b'\x08\x06\x00\x00\x00\x1f\x15\xc4\x89'  # IHDR chunk
    )
    idat_chunk = b'\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4'
    iend_chunk = b'\x00\x00\x00\x00IEND\xaeB`\x82'  # IEND chunk

    # Pad with extra data to make it > 1000 bytes
    png_bytes = png_header + ihdr_chunk + idat_chunk + (b'\x00' * 1000) + iend_chunk

    response = MagicMock()
    response.parts = [MagicMock()]

    # Mock the inline_data and as_image() method
    response.parts[0].text = None
    response.parts[0].inline_data = MagicMock()

    # Mock PIL Image
    mock_pil_image = MagicMock()
    mock_pil_image.save = lambda buf, format: buf.write(png_bytes)

    mock_image = MagicMock()
    mock_image._pil_image = mock_pil_image
    response.parts[0].as_image.return_value = mock_image

    return response


@pytest.fixture
def mock_env_with_api_key(monkeypatch):
    """Set up environment with Gemini API key."""
    monkeypatch.setenv("GEMINI_API_KEY", "test_api_key_12345")


@pytest.fixture
def sample_html_content():
    """Sample HTML content for image injection testing."""
    return """
    <div class="chapter">
        <h1>Chapter Title</h1>
        <p>First paragraph of the chapter.</p>
        <p>Second paragraph with some content.</p>
        <p>Third paragraph in the middle.</p>
        <p>Fourth paragraph continues the story.</p>
        <p>Fifth paragraph near the end.</p>
        <p>Sixth and final paragraph.</p>
    </div>
    """
