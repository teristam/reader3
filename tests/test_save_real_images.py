"""
Test that saves real generated images to a permanent location for inspection.
Run this when you want to actually see the generated images.
"""

import os
import pytest
import illustration_generator as ig


@pytest.mark.requires_api
def test_save_images_to_inspect():
    """
    Generate images and save them to a permanent location for manual inspection.

    Run with: pytest tests/test_save_real_images.py::test_save_images_to_inspect -v -s -m requires_api

    Images will be saved to: tests/output/
    """
    if not os.getenv("GEMINI_API_KEY"):
        pytest.skip("GEMINI_API_KEY not set - skipping real API test")

    # Create permanent output directory
    output_dir = os.path.join(os.path.dirname(__file__), "output")
    os.makedirs(output_dir, exist_ok=True)

    chapter_text = """
    In the heart of Tokyo's neon-lit streets, Detective Yuki stood before the abandoned
    arcade. The holographic sign flickered: "Game Over." But for her, the investigation
    was just beginning.

    Inside, rows of vintage arcade machines hummed with electricity, their screens
    displaying impossible patterns. Someone—or something—had been using these old
    machines to send encrypted messages across the city's quantum network.

    As Yuki approached the central cabinet, it suddenly blazed to life. Code scrolled
    across the screen: "PLAYER 2 HAS ENTERED THE GAME." She wasn't alone anymore.
    """

    print("\n" + "=" * 70)
    print("GENERATING IMAGES FOR INSPECTION")
    print("=" * 70)
    print(f"Output directory: {output_dir}")
    print(f"Chapter length: {len(chapter_text)} characters")
    print("\nThis will generate 3 images (may take 20-30 seconds)...")
    print("=" * 70 + "\n")

    try:
        result = ig.generate_illustrations_for_chapter(
            output_dir,
            chapter_index=0,
            chapter_text=chapter_text,
            book_title="Neon Dreams",
            chapter_title="The_Arcade_Mystery",
            force_regenerate=True  # Always regenerate for inspection
        )

        print("\n" + "=" * 70)
        print("✅ GENERATION COMPLETE!")
        print("=" * 70)
        print(f"\nGenerated {len(result)} images:\n")

        for i, path in enumerate(result):
            full_path = os.path.join(output_dir, path)
            size = os.path.getsize(full_path)
            size_mb = size / (1024 * 1024)
            print(f"{i+1}. {path}")
            print(f"   Location: {full_path}")
            print(f"   Size: {size:,} bytes ({size_mb:.2f} MB)\n")

        print("=" * 70)
        print("📂 TO VIEW IMAGES:")
        print(f"   open {output_dir}/images/")
        print("=" * 70)

        # Also print the scene analysis
        print("\n" + "=" * 70)
        print("SCENE ANALYSIS")
        print("=" * 70)

        import json
        metadata_file = os.path.join(output_dir, "generated_images.json")
        if os.path.exists(metadata_file):
            with open(metadata_file) as f:
                metadata = json.load(f)

            if "0" in metadata and "scene_locations" in metadata["0"]:
                locations = metadata["0"]["scene_locations"]
                print(f"\nScene locations: {locations}\n")

        assert len(result) == 3

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        raise


@pytest.mark.requires_api
def test_generate_single_image_for_inspection():
    """
    Generate just ONE image to save time during debugging.

    Run with: pytest tests/test_save_real_images.py::test_generate_single_image_for_inspection -v -s -m requires_api
    """
    if not os.getenv("GEMINI_API_KEY"):
        pytest.skip("GEMINI_API_KEY not set - skipping real API test")

    output_dir = os.path.join(os.path.dirname(__file__), "output")
    os.makedirs(output_dir, exist_ok=True)

    print("\n" + "=" * 70)
    print("GENERATING SINGLE IMAGE FOR QUICK INSPECTION")
    print("=" * 70)

    # Simple scene description
    scene_summary = "A cyberpunk detective standing in a neon-lit alley with holographic advertisements floating in the rain"

    print(f"\nScene: {scene_summary}")
    print("\nGenerating image (this takes ~7-10 seconds)...\n")

    prompt = ig.create_image_prompt(scene_summary, "Cyberpunk Detective")
    image_bytes = ig.generate_image(prompt)

    # Save directly
    image_path = ig.save_image(image_bytes, output_dir, 99, 1, "Single_Test_Image")

    full_path = os.path.join(output_dir, image_path)
    size = os.path.getsize(full_path)
    size_mb = size / (1024 * 1024)

    print("=" * 70)
    print("✅ IMAGE GENERATED!")
    print("=" * 70)
    print(f"\nLocation: {full_path}")
    print(f"Size: {size:,} bytes ({size_mb:.2f} MB)")
    print("\n" + "=" * 70)
    print("📂 TO VIEW IMAGE:")
    print(f"   open {full_path}")
    print("=" * 70)

    assert os.path.exists(full_path)
