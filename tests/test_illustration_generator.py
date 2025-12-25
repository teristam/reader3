"""
Comprehensive tests for the illustration_generator module.

Tests cover:
- Scene analysis with Gemini API
- Image generation with Gemini Image API
- Image saving and validation
- Caching mechanisms
- HTML injection
- Error handling
"""

import os
import json
import pytest
from unittest.mock import MagicMock, patch, mock_open
from io import BytesIO

import illustration_generator as ig


class TestSanitizeChapterTitle:
    """Tests for sanitize_chapter_title function."""

    def test_basic_alphanumeric(self):
        """Test that basic alphanumeric titles are preserved."""
        assert ig.sanitize_chapter_title("Chapter 1") == "Chapter_1"
        assert ig.sanitize_chapter_title("The Beginning") == "The_Beginning"

    def test_special_characters_removed(self):
        """Test that special characters are removed or replaced."""
        assert ig.sanitize_chapter_title("Chapter: The End?") == "Chapter_The_End"
        assert ig.sanitize_chapter_title("It's a test!") == "Its_a_test"

    def test_multiple_spaces_collapsed(self):
        """Test that multiple spaces are collapsed to single underscore."""
        assert ig.sanitize_chapter_title("Too   Many    Spaces") == "Too_Many_Spaces"

    def test_max_length_truncation(self):
        """Test that long titles are truncated."""
        long_title = "A" * 100
        result = ig.sanitize_chapter_title(long_title, max_length=50)
        assert len(result) == 50
        assert result == "A" * 50

    def test_empty_string_fallback(self):
        """Test that empty strings get default 'chapter' name."""
        assert ig.sanitize_chapter_title("") == "chapter"
        assert ig.sanitize_chapter_title("!!!") == "chapter"

    def test_leading_trailing_underscores_removed(self):
        """Test that leading/trailing underscores are removed."""
        assert ig.sanitize_chapter_title("__test__") == "test"
        assert ig.sanitize_chapter_title("...test...") == "test"


class TestGetGeminiClient:
    """Tests for get_gemini_client function."""

    def test_missing_api_key(self, monkeypatch):
        """Test that ValueError is raised when API key is missing."""
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        with pytest.raises(ValueError, match="GEMINI_API_KEY environment variable not set"):
            ig.get_gemini_client()

    @patch('illustration_generator.genai')
    def test_client_creation_with_api_key(self, mock_genai, mock_env_with_api_key):
        """Test that client is created successfully with API key."""
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client

        client = ig.get_gemini_client()

        mock_genai.Client.assert_called_once_with(api_key="test_api_key_12345")
        assert client == mock_client

    def test_genai_not_installed(self, monkeypatch):
        """Test error when google-genai package is not installed."""
        monkeypatch.setattr('illustration_generator.genai', None)
        with pytest.raises(ImportError, match="google-genai package not installed"):
            ig.get_gemini_client()


class TestSummarizeScenes:
    """Tests for summarize_scenes function."""

    @patch('illustration_generator.get_gemini_client')
    def test_successful_scene_analysis(self, mock_get_client, sample_chapter_text,
                                      mock_gemini_client, mock_scene_response, sample_scenes):
        """Test successful scene analysis with proper JSON response."""
        mock_get_client.return_value = mock_gemini_client
        mock_gemini_client.models.generate_content.return_value = mock_scene_response

        result = ig.summarize_scenes(sample_chapter_text)

        assert len(result) == 3
        assert result == sample_scenes
        assert result[0]["scene_number"] == 1
        assert result[0]["location_percent"] == 20
        assert "letter" in result[0]["summary"].lower()

    @patch('illustration_generator.get_gemini_client')
    def test_scene_analysis_with_code_block_wrapper(self, mock_get_client, sample_chapter_text,
                                                    mock_gemini_client, sample_scenes):
        """Test that JSON wrapped in markdown code blocks is handled correctly."""
        mock_get_client.return_value = mock_gemini_client

        # Wrap JSON in code block (common Gemini behavior)
        response = MagicMock()
        response.parts = [MagicMock()]
        response.parts[0].text = f"```json\n{json.dumps({'scenes': sample_scenes})}\n```"

        mock_gemini_client.models.generate_content.return_value = response

        result = ig.summarize_scenes(sample_chapter_text)

        assert len(result) == 3
        assert result[0]["scene_number"] == 1

    @patch('illustration_generator.get_gemini_client')
    def test_scene_analysis_json_parse_error(self, mock_get_client, sample_chapter_text,
                                            mock_gemini_client):
        """Test fallback to generic scenes when JSON parsing fails."""
        mock_get_client.return_value = mock_gemini_client

        response = MagicMock()
        response.parts = [MagicMock()]
        response.parts[0].text = "This is not valid JSON"

        mock_gemini_client.models.generate_content.return_value = response

        result = ig.summarize_scenes(sample_chapter_text)

        # Should return fallback scenes
        assert len(result) == 3
        assert result[0]["location_percent"] == 25
        assert result[1]["location_percent"] == 50
        assert result[2]["location_percent"] == 75

    @patch('illustration_generator.get_gemini_client')
    def test_scene_analysis_empty_text(self, mock_get_client):
        """Test that empty chapter text returns empty list."""
        mock_get_client.return_value = MagicMock()

        result = ig.summarize_scenes("")
        assert result == []

        result = ig.summarize_scenes("   ")
        assert result == []

    @patch('illustration_generator.get_gemini_client')
    def test_scene_analysis_fewer_than_3_scenes(self, mock_get_client, sample_chapter_text,
                                                mock_gemini_client):
        """Test that fewer than 3 scenes are padded to 3."""
        mock_get_client.return_value = mock_gemini_client

        # Response with only 1 scene
        response = MagicMock()
        response.parts = [MagicMock()]
        response.parts[0].text = json.dumps({
            "scenes": [
                {"scene_number": 1, "summary": "Only one scene", "location_percent": 50}
            ]
        })

        mock_gemini_client.models.generate_content.return_value = response

        result = ig.summarize_scenes(sample_chapter_text)

        # Should be padded to 3 scenes
        assert len(result) == 3
        assert result[0]["summary"] == "Only one scene"
        assert result[1]["summary"] == "A scene from the chapter"

    @patch('illustration_generator.get_gemini_client')
    def test_scene_analysis_api_error(self, mock_get_client, sample_chapter_text,
                                     mock_gemini_client):
        """Test that API errors are propagated."""
        mock_get_client.return_value = mock_gemini_client
        mock_gemini_client.models.generate_content.side_effect = Exception("API Error")

        with pytest.raises(Exception, match="API Error"):
            ig.summarize_scenes(sample_chapter_text)


class TestCreateImagePrompt:
    """Tests for create_image_prompt function."""

    def test_basic_prompt_creation(self):
        """Test basic image prompt creation."""
        summary = "A knight fighting a dragon in a medieval castle."
        prompt = ig.create_image_prompt(summary)

        assert summary in prompt
        assert "illustration" in prompt.lower()
        assert "cinematic" in prompt.lower()

    def test_prompt_with_book_title(self):
        """Test that book title is included in prompt context."""
        summary = "A space battle scene."
        book_title = "The Galactic Wars"

        prompt = ig.create_image_prompt(summary, book_title)

        assert summary in prompt
        assert book_title in prompt
        assert "consistent with the themes" in prompt

    def test_prompt_without_book_title(self):
        """Test prompt creation without book title."""
        summary = "A quiet forest scene."
        prompt = ig.create_image_prompt(summary)

        assert summary in prompt
        assert "from a book" in prompt


class TestGenerateImage:
    """Tests for generate_image function."""

    @patch('illustration_generator.get_gemini_client')
    def test_successful_image_generation(self, mock_get_client, mock_gemini_client,
                                        mock_image_response):
        """Test successful image generation."""
        mock_get_client.return_value = mock_gemini_client
        mock_gemini_client.models.generate_content.return_value = mock_image_response

        prompt = "Generate a beautiful landscape"
        result = ig.generate_image(prompt)

        assert isinstance(result, bytes)
        assert len(result) > 100  # Should be a real PNG
        assert result.startswith(b'\x89PNG')  # PNG header

    @patch('illustration_generator.get_gemini_client')
    def test_image_generation_no_image_in_response(self, mock_get_client, mock_gemini_client):
        """Test error handling when response contains no image."""
        mock_get_client.return_value = mock_gemini_client

        response = MagicMock()
        response.parts = [MagicMock()]
        response.parts[0].text = "Sorry, I cannot generate that image."
        response.parts[0].inline_data = None

        mock_gemini_client.models.generate_content.return_value = response

        with pytest.raises(ValueError, match="No image data found in response"):
            ig.generate_image("test prompt")

    @patch('illustration_generator.get_gemini_client')
    def test_image_generation_too_small(self, mock_get_client, mock_gemini_client):
        """Test validation of suspiciously small images."""
        mock_get_client.return_value = mock_gemini_client

        # Mock a tiny image response
        response = MagicMock()
        response.parts = [MagicMock()]
        response.parts[0].text = None
        response.parts[0].inline_data = MagicMock()

        tiny_bytes = b'\x89PNG\r\n\x1a\n' + b'x' * 100  # Less than 1000 bytes
        mock_pil_image = MagicMock()
        mock_pil_image.save = lambda buf, format: buf.write(tiny_bytes)

        mock_image = MagicMock()
        mock_image._pil_image = mock_pil_image
        response.parts[0].as_image.return_value = mock_image

        mock_gemini_client.models.generate_content.return_value = response

        with pytest.raises(ValueError, match="Image too small"):
            ig.generate_image("test prompt")


class TestSaveImage:
    """Tests for save_image function."""

    def test_save_valid_image(self, temp_book_dir):
        """Test saving a valid PNG image."""
        # Create a minimal valid PNG larger than 1000 bytes
        png_header = b'\x89PNG\r\n\x1a\n'
        png_data = (
            b'\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
            b'\x08\x06\x00\x00\x00\x1f\x15\xc4\x89'
            b'\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01'
            b'\r\n-\xb4'
            b'\x00\x00\x00\x00IEND\xaeB`\x82'
        )
        # Pad to make it > 1000 bytes
        png_bytes = png_header + png_data + (b'\x00' * 1000)

        result_path = ig.save_image(png_bytes, temp_book_dir, 0, 1)

        assert result_path == "images/generated_ch0_scene1.png"
        full_path = os.path.join(temp_book_dir, result_path)
        assert os.path.exists(full_path)

        # Verify content
        with open(full_path, 'rb') as f:
            saved_data = f.read()
        assert saved_data == png_bytes

    def test_save_image_with_chapter_title(self, temp_book_dir):
        """Test saving image with chapter title in filename."""
        png_bytes = (b'\x89PNG\r\n\x1a\n' + b'x' * 1000)

        result_path = ig.save_image(png_bytes, temp_book_dir, 5, 2, "The Final Battle")

        assert "The_Final_Battle" in result_path
        assert result_path == "images/generated_ch5_The_Final_Battle_scene2.png"

    def test_save_image_too_small(self, temp_book_dir):
        """Test that images that are too small are rejected."""
        tiny_png = b'\x89PNG\r\n\x1a\n' + b'x' * 100

        with pytest.raises(ValueError, match="Invalid image data"):
            ig.save_image(tiny_png, temp_book_dir, 0, 1)

    def test_save_image_invalid_header(self, temp_book_dir):
        """Test that images without PNG header are rejected."""
        invalid_data = b'NOTAPNG' + b'x' * 1000

        with pytest.raises(ValueError, match="not a valid PNG"):
            ig.save_image(invalid_data, temp_book_dir, 0, 1)

    def test_save_image_creates_directory(self):
        """Test that images directory is created if it doesn't exist."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            book_dir = os.path.join(tmpdir, "new_book")
            os.makedirs(book_dir)

            png_bytes = b'\x89PNG\r\n\x1a\n' + b'x' * 1000

            result_path = ig.save_image(png_bytes, book_dir, 0, 1)

            images_dir = os.path.join(book_dir, "images")
            assert os.path.exists(images_dir)
            assert os.path.exists(os.path.join(book_dir, result_path))


class TestCaching:
    """Tests for image caching mechanisms."""

    def test_get_cached_images_no_metadata(self, temp_book_dir):
        """Test that None is returned when no metadata file exists."""
        result = ig.get_cached_images(temp_book_dir, 0)
        assert result is None

    def test_get_cached_images_success(self, temp_book_dir):
        """Test retrieving cached images when all exist."""
        # Create metadata file
        metadata = {
            "0": {
                "images": [
                    "images/generated_ch0_scene1.png",
                    "images/generated_ch0_scene2.png",
                    "images/generated_ch0_scene3.png"
                ],
                "scene_locations": [25, 50, 75]
            }
        }

        metadata_path = os.path.join(temp_book_dir, "generated_images.json")
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f)

        # Create the actual image files
        images_dir = os.path.join(temp_book_dir, "images")
        for img in metadata["0"]["images"]:
            img_path = os.path.join(temp_book_dir, img)
            with open(img_path, 'wb') as f:
                f.write(b'\x89PNG\r\n\x1a\n' + b'x' * 1000)

        result = ig.get_cached_images(temp_book_dir, 0)

        assert result == metadata["0"]["images"]

    def test_get_cached_images_old_format(self, temp_book_dir):
        """Test handling of old metadata format (list instead of dict)."""
        # Old format: chapter key maps to list directly
        metadata = {
            "0": [
                "images/generated_ch0_scene1.png",
                "images/generated_ch0_scene2.png",
                "images/generated_ch0_scene3.png"
            ]
        }

        metadata_path = os.path.join(temp_book_dir, "generated_images.json")
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f)

        # Create the actual image files
        images_dir = os.path.join(temp_book_dir, "images")
        for img in metadata["0"]:
            img_path = os.path.join(temp_book_dir, img)
            with open(img_path, 'wb') as f:
                f.write(b'\x89PNG\r\n\x1a\n' + b'x' * 1000)

        result = ig.get_cached_images(temp_book_dir, 0)

        assert result == metadata["0"]

    def test_get_cached_images_missing_files(self, temp_book_dir):
        """Test that None is returned when cached files don't exist."""
        metadata = {
            "0": {
                "images": [
                    "images/nonexistent1.png",
                    "images/nonexistent2.png",
                    "images/nonexistent3.png"
                ]
            }
        }

        metadata_path = os.path.join(temp_book_dir, "generated_images.json")
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f)

        result = ig.get_cached_images(temp_book_dir, 0)

        assert result is None

    def test_save_image_metadata_new_file(self, temp_book_dir):
        """Test saving metadata when no file exists."""
        image_paths = ["images/ch0_s1.png", "images/ch0_s2.png", "images/ch0_s3.png"]
        scene_locations = [25, 50, 75]

        ig.save_image_metadata(temp_book_dir, 0, image_paths, scene_locations)

        metadata_path = os.path.join(temp_book_dir, "generated_images.json")
        assert os.path.exists(metadata_path)

        with open(metadata_path, 'r') as f:
            metadata = json.load(f)

        assert "0" in metadata
        assert metadata["0"]["images"] == image_paths
        assert metadata["0"]["scene_locations"] == scene_locations

    def test_save_image_metadata_append(self, temp_book_dir):
        """Test appending metadata to existing file."""
        # Create initial metadata
        initial_metadata = {
            "0": {"images": ["img1.png", "img2.png", "img3.png"]}
        }

        metadata_path = os.path.join(temp_book_dir, "generated_images.json")
        with open(metadata_path, 'w') as f:
            json.dump(initial_metadata, f)

        # Add metadata for chapter 1
        image_paths = ["images/ch1_s1.png", "images/ch1_s2.png", "images/ch1_s3.png"]
        ig.save_image_metadata(temp_book_dir, 1, image_paths)

        with open(metadata_path, 'r') as f:
            metadata = json.load(f)

        assert "0" in metadata  # Old data preserved
        assert "1" in metadata  # New data added
        assert metadata["1"]["images"] == image_paths


class TestInjectImagesIntoHtml:
    """Tests for inject_images_into_html function."""

    def test_inject_images_into_paragraphs(self, sample_html_content):
        """Test injecting images at calculated paragraph positions."""
        image_paths = [
            "images/scene1.png",
            "images/scene2.png",
            "images/scene3.png"
        ]
        scene_locations = [20, 50, 80]

        result = ig.inject_images_into_html(sample_html_content, image_paths, scene_locations)

        assert "images/scene1.png" in result
        assert "images/scene2.png" in result
        assert "images/scene3.png" in result
        assert 'alt="Generated illustration for scene"' in result
        assert 'style="max-width: 100%' in result

    def test_inject_images_no_paragraphs(self):
        """Test injecting images when no paragraphs exist."""
        html_content = "<div><span>No paragraphs here</span></div>"
        image_paths = ["images/scene1.png"]
        scene_locations = [50]

        result = ig.inject_images_into_html(html_content, image_paths, scene_locations)

        # Images should still be appended
        assert "images/scene1.png" in result

    def test_inject_images_empty_list(self, sample_html_content):
        """Test that empty image list returns unchanged HTML."""
        result = ig.inject_images_into_html(sample_html_content, [], [])

        assert result == sample_html_content

    def test_inject_images_location_boundaries(self):
        """Test image injection at boundary locations (0% and 100%)."""
        html_content = "<p>Para 1</p><p>Para 2</p><p>Para 3</p><p>Para 4</p>"
        image_paths = ["images/s1.png", "images/s2.png"]
        scene_locations = [0, 100]

        result = ig.inject_images_into_html(html_content, image_paths, scene_locations)

        assert "images/s1.png" in result
        assert "images/s2.png" in result


class TestGenerateIllustrationsForChapter:
    """Integration tests for the main generate_illustrations_for_chapter function."""

    @patch('illustration_generator.get_gemini_client')
    def test_full_generation_pipeline(self, mock_get_client, temp_book_dir,
                                     sample_chapter_text, mock_gemini_client,
                                     mock_scene_response, mock_image_response):
        """Test the complete image generation pipeline."""
        mock_get_client.return_value = mock_gemini_client

        # First call returns scene analysis, subsequent calls return images
        mock_gemini_client.models.generate_content.side_effect = [
            mock_scene_response,
            mock_image_response,
            mock_image_response,
            mock_image_response
        ]

        result = ig.generate_illustrations_for_chapter(
            temp_book_dir, 0, sample_chapter_text, "Test Book", "Chapter 1"
        )

        # Should return 3 image paths
        assert len(result) == 3
        assert all("images/generated_ch0" in path for path in result)

        # Verify images were saved
        for path in result:
            full_path = os.path.join(temp_book_dir, path)
            assert os.path.exists(full_path)

        # Verify metadata was saved
        metadata_path = os.path.join(temp_book_dir, "generated_images.json")
        assert os.path.exists(metadata_path)

    @patch('illustration_generator.get_gemini_client')
    def test_generation_uses_cache(self, mock_get_client, temp_book_dir,
                                   sample_chapter_text):
        """Test that cached images are returned without regeneration."""
        # Set up cache
        metadata = {
            "0": {
                "images": [
                    "images/cached1.png",
                    "images/cached2.png",
                    "images/cached3.png"
                ]
            }
        }

        metadata_path = os.path.join(temp_book_dir, "generated_images.json")
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f)

        # Create cached files
        for img in metadata["0"]["images"]:
            img_path = os.path.join(temp_book_dir, img)
            with open(img_path, 'wb') as f:
                f.write(b'\x89PNG\r\n\x1a\n' + b'x' * 1000)

        result = ig.generate_illustrations_for_chapter(
            temp_book_dir, 0, sample_chapter_text
        )

        # Should return cached paths
        assert result == metadata["0"]["images"]

        # API should not be called
        mock_get_client.assert_not_called()

    @patch('illustration_generator.get_gemini_client')
    def test_generation_force_regenerate(self, mock_get_client, temp_book_dir,
                                        sample_chapter_text, mock_gemini_client,
                                        mock_scene_response, mock_image_response):
        """Test force regeneration bypasses cache."""
        mock_get_client.return_value = mock_gemini_client

        # Set up cache
        metadata = {
            "0": {
                "images": [
                    "images/old1.png",
                    "images/old2.png",
                    "images/old3.png"
                ]
            }
        }

        metadata_path = os.path.join(temp_book_dir, "generated_images.json")
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f)

        # Create old cached files
        for img in metadata["0"]["images"]:
            img_path = os.path.join(temp_book_dir, img)
            with open(img_path, 'wb') as f:
                f.write(b'\x89PNG\r\n\x1a\n' + b'x' * 1000)

        # Mock API responses
        mock_gemini_client.models.generate_content.side_effect = [
            mock_scene_response,
            mock_image_response,
            mock_image_response,
            mock_image_response
        ]

        result = ig.generate_illustrations_for_chapter(
            temp_book_dir, 0, sample_chapter_text, force_regenerate=True
        )

        # Should generate new images
        assert len(result) == 3

        # Old cached files should be deleted
        for img in metadata["0"]["images"]:
            img_path = os.path.join(temp_book_dir, img)
            assert not os.path.exists(img_path)

    @patch('illustration_generator.get_gemini_client')
    def test_generation_error_handling(self, mock_get_client, temp_book_dir,
                                      sample_chapter_text, mock_gemini_client):
        """Test that errors during generation are properly handled."""
        mock_get_client.return_value = mock_gemini_client

        # Scene analysis succeeds but image generation fails
        scene_response = MagicMock()
        scene_response.parts = [MagicMock()]
        scene_response.parts[0].text = json.dumps({
            "scenes": [
                {"scene_number": 1, "summary": "test", "location_percent": 25},
                {"scene_number": 2, "summary": "test", "location_percent": 50},
                {"scene_number": 3, "summary": "test", "location_percent": 75}
            ]
        })

        mock_gemini_client.models.generate_content.side_effect = [
            scene_response,
            Exception("Image generation failed")
        ]

        with pytest.raises(Exception, match="Failed to generate image for scene 1"):
            ig.generate_illustrations_for_chapter(
                temp_book_dir, 0, sample_chapter_text
            )
