"""
Example test showing how to debug specific issues in the image generation pipeline.

This file demonstrates how to write focused tests to isolate and debug problems.
"""

import pytest
from unittest.mock import patch, MagicMock
import illustration_generator as ig


class TestDebuggingExamples:
    """
    Examples of how to write tests to debug specific issues.
    """

    @patch('illustration_generator.get_gemini_client')
    def test_debug_scene_response_format(self, mock_get_client):
        """
        Use this test to debug what the actual scene analysis response looks like.

        To debug with real API:
        1. Comment out the mock
        2. Set GEMINI_API_KEY environment variable
        3. Run: pytest tests/test_example_usage.py::TestDebuggingExamples::test_debug_scene_response_format -v -s
        """
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        # Simulate what a real response might look like
        response = MagicMock()
        response.parts = [MagicMock()]
        response.parts[0].text = """```json
{
    "scenes": [
        {
            "scene_number": 1,
            "summary": "A dramatic opening",
            "location_percent": 10
        },
        {
            "scene_number": 2,
            "summary": "The middle conflict",
            "location_percent": 50
        },
        {
            "scene_number": 3,
            "summary": "The resolution",
            "location_percent": 90
        }
    ]
}
```"""

        mock_client.models.generate_content.return_value = response

        chapter_text = "Once upon a time, there was a bug in the code..."
        scenes = ig.summarize_scenes(chapter_text)

        # Print for debugging
        print("\n=== Scene Analysis Results ===")
        for i, scene in enumerate(scenes):
            print(f"Scene {i+1}:")
            print(f"  Number: {scene['scene_number']}")
            print(f"  Location: {scene['location_percent']}%")
            print(f"  Summary: {scene['summary']}")

        assert len(scenes) == 3

    @patch('illustration_generator.get_gemini_client')
    def test_debug_image_response_structure(self, mock_get_client):
        """
        Use this test to understand the image response structure.

        This helps debug issues where images aren't being extracted correctly.
        """
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        # Create a proper mock response with image data
        response = MagicMock()
        response.parts = [MagicMock()]
        response.parts[0].text = None
        response.parts[0].inline_data = MagicMock()

        # Mock the image bytes
        test_png = b'\x89PNG\r\n\x1a\n' + b'x' * 1500

        mock_pil_image = MagicMock()
        mock_pil_image.save = lambda buf, format: buf.write(test_png)

        mock_image = MagicMock()
        mock_image._pil_image = mock_pil_image
        response.parts[0].as_image.return_value = mock_image

        mock_client.models.generate_content.return_value = response

        result = ig.generate_image("test prompt")

        print(f"\n=== Image Generation Results ===")
        print(f"Image size: {len(result)} bytes")
        png_header = b'\x89PNG'
        print(f"Is PNG: {result.startswith(png_header)}")
        print(f"Valid size: {len(result) >= 1000}")

        assert len(result) >= 1000
        assert result.startswith(b'\x89PNG')

    def test_debug_filename_sanitization(self):
        """
        Test specific edge cases in filename sanitization.

        Add your own test cases here when you encounter weird chapter titles.
        """
        test_cases = [
            ("Chapter 1: The Beginning!", "Chapter_1_The_Beginning"),
            ("It's a test... really?", "Its_a_test_really"),
            ("    Spaces    everywhere    ", "Spaces_everywhere"),
            ("特殊字符 Special", "特殊字符_Special"),  # Non-ASCII characters are preserved
            ("!!!???", "chapter"),  # All punctuation
        ]

        print("\n=== Filename Sanitization Tests ===")
        for input_title, expected in test_cases:
            result = ig.sanitize_chapter_title(input_title)
            print(f"'{input_title}' → '{result}'")
            assert result == expected, f"Expected '{expected}', got '{result}'"

    @patch('illustration_generator.get_gemini_client')
    def test_debug_full_pipeline_with_prints(self, mock_get_client, tmp_path):
        """
        Full pipeline test with debug prints to see what's happening at each stage.

        Run with: pytest tests/test_example_usage.py::TestDebuggingExamples::test_debug_full_pipeline_with_prints -v -s
        """
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        # Mock scene analysis response
        scene_response = MagicMock()
        scene_response.parts = [MagicMock()]
        scene_response.parts[0].text = """{
            "scenes": [
                {"scene_number": 1, "summary": "Scene 1", "location_percent": 25},
                {"scene_number": 2, "summary": "Scene 2", "location_percent": 50},
                {"scene_number": 3, "summary": "Scene 3", "location_percent": 75}
            ]
        }"""

        # Mock image response
        png_bytes = b'\x89PNG\r\n\x1a\n' + b'x' * 1500
        image_response = MagicMock()
        image_response.parts = [MagicMock()]
        image_response.parts[0].text = None
        image_response.parts[0].inline_data = MagicMock()

        mock_pil_image = MagicMock()
        mock_pil_image.save = lambda buf, format: buf.write(png_bytes)
        mock_image = MagicMock()
        mock_image._pil_image = mock_pil_image
        image_response.parts[0].as_image.return_value = mock_image

        # First call returns scenes, next 3 calls return images
        mock_client.models.generate_content.side_effect = [
            scene_response,
            image_response,
            image_response,
            image_response
        ]

        book_dir = str(tmp_path)
        chapter_text = "Test chapter with some content."

        print("\n=== Full Pipeline Debug ===")
        print(f"Book directory: {book_dir}")
        print(f"Chapter text length: {len(chapter_text)}")

        result = ig.generate_illustrations_for_chapter(
            book_dir, 0, chapter_text, "Test Book", "Chapter 1"
        )

        print(f"\n=== Results ===")
        print(f"Generated {len(result)} images:")
        for i, path in enumerate(result):
            print(f"  {i+1}. {path}")

        assert len(result) == 3


# Example of a test you might write when investigating a specific bug
class TestSpecificBugInvestigation:
    """
    When you encounter a bug, create a focused test here to reproduce it.
    """

    def test_investigate_empty_scene_summary(self):
        """
        Investigating: What happens if Gemini returns empty scene summaries?
        """
        # This test would help you understand and fix edge cases
        pass

    def test_investigate_malformed_json_response(self):
        """
        Investigating: What if the JSON has unexpected structure?
        """
        pass
