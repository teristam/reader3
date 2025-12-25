"""
Tests that can optionally run against the real Gemini API.

These tests are marked with @pytest.mark.requires_api and will be skipped
unless you explicitly run them with: pytest -m requires_api

IMPORTANT: These tests will consume API credits!
Set GEMINI_API_KEY environment variable before running.
"""

import os
import pytest
import illustration_generator as ig


@pytest.mark.requires_api
class TestRealGeminiAPI:
    """Tests that hit the real Gemini API - use sparingly!"""

    def test_real_scene_analysis(self):
        """
        Test scene analysis with real Gemini API.

        Run with: pytest tests/test_real_api.py::TestRealGeminiAPI::test_real_scene_analysis -v -s -m requires_api

        Make sure GEMINI_API_KEY is set!
        """
        if not os.getenv("GEMINI_API_KEY"):
            pytest.skip("GEMINI_API_KEY not set - skipping real API test")

        # Use a short sample to minimize API costs
        chapter_text = """
        The old mansion stood at the end of Willow Street, its windows dark and foreboding.
        Sarah hesitated at the gate, remembering her grandmother's warnings about this place.

        Inside, dust motes danced in the pale moonlight streaming through broken shutters.
        She heard a creak from upstairs - someone, or something, was moving in the darkness.

        Taking a deep breath, Sarah climbed the ancient staircase. At the top, she found
        an old photograph lying on the floor. It showed her grandmother as a young woman,
        standing in front of this very house. But she wasn't alone in the picture.
        """

        print("\n" + "=" * 60)
        print("TESTING REAL SCENE ANALYSIS API")
        print("=" * 60)
        print(f"Chapter text length: {len(chapter_text)} chars")

        try:
            scenes = ig.summarize_scenes(chapter_text)

            print(f"\n✅ SUCCESS! Got {len(scenes)} scenes\n")

            for i, scene in enumerate(scenes):
                print(f"Scene {i+1}:")
                print(f"  Number: {scene.get('scene_number')}")
                print(f"  Location: {scene.get('location_percent')}%")
                print(f"  Summary: {scene.get('summary')}")
                print()

            # Assertions
            assert len(scenes) == 3, f"Expected 3 scenes, got {len(scenes)}"
            assert all('scene_number' in s for s in scenes), "Missing scene_number"
            assert all('summary' in s for s in scenes), "Missing summary"
            assert all('location_percent' in s for s in scenes), "Missing location_percent"

            # Verify locations are reasonable (0-100)
            for scene in scenes:
                loc = scene['location_percent']
                assert 0 <= loc <= 100, f"Invalid location: {loc}"

            print("=" * 60)
            print("✅ ALL SCENE ANALYSIS ASSERTIONS PASSED")
            print("=" * 60)

        except Exception as e:
            print(f"\n❌ ERROR: {type(e).__name__}: {e}")
            raise

    def test_real_image_generation(self, tmp_path):
        """
        Test image generation with real Gemini API.

        Run with: pytest tests/test_real_api.py::TestRealGeminiAPI::test_real_image_generation -v -s -m requires_api

        WARNING: This test generates a real image and will consume more API credits!
        """
        if not os.getenv("GEMINI_API_KEY"):
            pytest.skip("GEMINI_API_KEY not set - skipping real API test")

        print("\n" + "=" * 60)
        print("TESTING REAL IMAGE GENERATION API")
        print("=" * 60)
        print("⚠️  WARNING: This will consume API credits!")
        print("=" * 60)

        # Create a simple prompt
        prompt = ig.create_image_prompt(
            "A mysterious old mansion at night with moonlight streaming through broken windows",
            "Test Book"
        )

        print(f"\nPrompt length: {len(prompt)} chars")
        print(f"Prompt preview: {prompt[:200]}...")

        try:
            print("\n🎨 Generating image... (this may take 10-30 seconds)")
            image_bytes = ig.generate_image(prompt)

            print(f"\n✅ SUCCESS! Generated image")
            print(f"Image size: {len(image_bytes)} bytes")
            png_header = b'\x89PNG'
            is_png = image_bytes.startswith(png_header)
            print(f"Image format: {'PNG' if is_png else 'Unknown'}")

            # Assertions
            assert len(image_bytes) >= 1000, f"Image too small: {len(image_bytes)} bytes"
            assert image_bytes.startswith(b'\x89PNG'), "Not a valid PNG"

            # Try to save it
            book_dir = str(tmp_path)
            saved_path = ig.save_image(image_bytes, book_dir, 0, 1, "Test Chapter")

            print(f"\n💾 Image saved to: {saved_path}")

            full_path = os.path.join(book_dir, saved_path)
            assert os.path.exists(full_path), "Image file not created"

            # Check file size
            file_size = os.path.getsize(full_path)
            print(f"File size on disk: {file_size} bytes")

            print("\n" + "=" * 60)
            print("✅ ALL IMAGE GENERATION ASSERTIONS PASSED")
            print("=" * 60)
            print(f"\n💡 TIP: Check the generated image at: {full_path}")

        except Exception as e:
            print(f"\n❌ ERROR: {type(e).__name__}: {e}")
            raise

    def test_real_full_pipeline(self, tmp_path):
        """
        Test the complete pipeline with real Gemini API.

        Run with: pytest tests/test_real_api.py::TestRealGeminiAPI::test_real_full_pipeline -v -s -m requires_api

        WARNING: This is the most expensive test! It generates 3 images.
        """
        if not os.getenv("GEMINI_API_KEY"):
            pytest.skip("GEMINI_API_KEY not set - skipping real API test")

        print("\n" + "=" * 60)
        print("TESTING COMPLETE PIPELINE WITH REAL API")
        print("=" * 60)
        print("⚠️  WARNING: This will generate 3 images and consume significant API credits!")
        print("=" * 60)

        # Short chapter to minimize cost
        chapter_text = """
        The spaceship's alarms blared as Captain Rodriguez stared at the radar screen.
        Three unknown vessels were approaching fast, their intentions unclear.

        "All hands to battle stations!" she commanded, her voice steady despite the fear
        gripping her heart. This was it - first contact with an alien civilization.

        As the ships drew closer, a transmission crackled through: "Greetings, humans.
        We come in peace." Rodriguez let out a breath she didn't know she'd been holding.
        Perhaps humanity's future among the stars would be brighter than she'd feared.
        """

        book_dir = str(tmp_path)

        print(f"\nBook directory: {book_dir}")
        print(f"Chapter text length: {len(chapter_text)} chars")
        print("\n🚀 Starting full pipeline...")

        try:
            result = ig.generate_illustrations_for_chapter(
                book_dir,
                chapter_index=0,
                chapter_text=chapter_text,
                book_title="The First Contact",
                chapter_title="Encounter"
            )

            print(f"\n✅ SUCCESS! Pipeline completed")
            print(f"Generated {len(result)} images:")

            for i, path in enumerate(result):
                full_path = os.path.join(book_dir, path)
                size = os.path.getsize(full_path)
                print(f"  {i+1}. {path} ({size:,} bytes)")

            # Assertions
            assert len(result) == 3, f"Expected 3 images, got {len(result)}"

            # Verify all images exist and are valid
            png_header = b'\x89PNG'
            for path in result:
                full_path = os.path.join(book_dir, path)
                assert os.path.exists(full_path), f"Image not found: {path}"

                # Check it's a valid PNG
                with open(full_path, 'rb') as f:
                    data = f.read()
                    assert data.startswith(png_header), f"Not a PNG: {path}"
                    assert len(data) >= 1000, f"Image too small: {path}"

            # Check metadata was saved
            metadata_file = os.path.join(book_dir, "generated_images.json")
            assert os.path.exists(metadata_file), "Metadata file not created"

            import json
            with open(metadata_file) as f:
                metadata = json.load(f)

            assert "0" in metadata, "Chapter 0 not in metadata"
            assert "images" in metadata["0"], "Images list not in metadata"
            assert len(metadata["0"]["images"]) == 3, "Wrong number of images in metadata"

            print("\n" + "=" * 60)
            print("✅ ALL PIPELINE ASSERTIONS PASSED")
            print("=" * 60)
            print(f"\n💡 TIP: Check generated images in: {book_dir}/images/")

            # Test caching
            print("\n🔄 Testing cache retrieval...")
            cached = ig.get_cached_images(book_dir, 0)
            assert cached == result, "Cached images don't match generated images"
            print("✅ Cache working correctly!")

        except Exception as e:
            print(f"\n❌ ERROR: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            raise


@pytest.mark.requires_api
class TestAPIErrorHandling:
    """Test how the code handles real API errors."""

    def test_invalid_api_key(self, monkeypatch):
        """Test behavior with invalid API key."""
        monkeypatch.setenv("GEMINI_API_KEY", "invalid_key_12345")

        print("\n" + "=" * 60)
        print("TESTING INVALID API KEY HANDLING")
        print("=" * 60)

        chapter_text = "This is a test chapter."

        try:
            scenes = ig.summarize_scenes(chapter_text)
            print(f"❌ Expected an error, but got: {scenes}")
            pytest.fail("Should have raised an exception with invalid API key")
        except Exception as e:
            print(f"✅ Got expected error: {type(e).__name__}")
            print(f"Error message: {str(e)[:200]}")
            # This is expected behavior
            assert True
