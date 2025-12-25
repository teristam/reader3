# Testing Guide for Image Generation Pipeline

Complete guide for testing the illustration generation system.

## Quick Start

### 1. Run All Mock Tests (Fast, No API Costs)
```bash
uv run pytest tests/ -v
```
**Result:** 46 tests in ~0.5 seconds ✅

### 2. Generate a Test Image (Requires API Key)
```bash
uv run pytest tests/test_save_real_images.py::test_generate_single_image_for_inspection -v -s -m requires_api
```
**Result:** 1 image saved to `tests/output/images/` in ~10 seconds

### 3. View Generated Images
```bash
open tests/output/images/
```

---

## Test Files Overview

### Mock Tests (No API Costs)

| File | Tests | Purpose | Speed |
|------|-------|---------|-------|
| [test_illustration_generator.py](tests/test_illustration_generator.py) | 40 | Comprehensive unit/integration tests | Fast (~0.4s) |
| [test_example_usage.py](tests/test_example_usage.py) | 6 | Debugging examples and edge cases | Fast (~0.4s) |

### Real API Tests (Uses API Credits)

| File | Tests | Purpose | Speed |
|------|-------|---------|-------|
| [test_real_api.py](tests/test_real_api.py) | 4 | Validates live API integration | Slow (~30s total) |
| [test_save_real_images.py](tests/test_save_real_images.py) | 2 | Generates images for manual inspection | Slow (~10-30s) |

---

## Running Specific Tests

### By Test File
```bash
# Run specific test file
uv run pytest tests/test_illustration_generator.py -v

# Run with output visible
uv run pytest tests/test_illustration_generator.py -v -s
```

### By Test Class
```bash
# Run all scene analysis tests
uv run pytest tests/test_illustration_generator.py::TestSummarizeScenes -v

# Run all caching tests
uv run pytest tests/test_illustration_generator.py::TestCaching -v
```

### By Individual Test
```bash
# Run one specific test
uv run pytest tests/test_illustration_generator.py::TestSummarizeScenes::test_successful_scene_analysis -v
```

### By Marker
```bash
# Run only real API tests (requires GEMINI_API_KEY)
uv run pytest -m requires_api -v -s

# Run all tests EXCEPT real API tests
uv run pytest -m "not requires_api" -v
```

---

## Generating Test Images

### Option 1: Single Image (Fast - ~10 seconds)

```bash
uv run pytest tests/test_save_real_images.py::test_generate_single_image_for_inspection -v -s -m requires_api
```

**Generates:**
- 1 cyberpunk detective scene
- Saved to: `tests/output/images/generated_ch99_Single_Test_Image_scene1.png`
- Size: ~1.7 MB

### Option 2: Full Chapter (Slow - ~30 seconds)

```bash
uv run pytest tests/test_save_real_images.py::test_save_images_to_inspect -v -s -m requires_api
```

**Generates:**
- 3 scenes from a Tokyo arcade mystery
- Saved to: `tests/output/images/generated_ch0_The_Arcade_Mystery_scene*.png`
- Size: ~1-2 MB each

### Viewing Generated Images

```bash
# Open folder
open tests/output/images/

# View specific image
open tests/output/images/generated_ch99_Single_Test_Image_scene1.png
```

**Full path:** `/Users/teristam/Documents/code/reader3/tests/output/images/`

---

## Test Coverage

### What's Tested

✅ **String Processing** (6 tests)
- Filename sanitization
- Special character handling
- Length truncation

✅ **API Client** (3 tests)
- API key validation
- Client initialization
- Error handling

✅ **Scene Analysis** (6 tests)
- JSON parsing
- Markdown wrapper handling
- Scene padding (< 3 scenes)
- Error handling

✅ **Image Generation** (3 tests)
- Image data extraction
- Size validation
- Multi-part response handling

✅ **File Operations** (5 tests)
- PNG validation
- Directory creation
- Filename generation

✅ **Caching** (6 tests)
- Metadata storage
- Cache retrieval
- Backward compatibility

✅ **HTML Injection** (4 tests)
- Paragraph detection
- Image positioning
- Edge cases

✅ **Full Pipeline** (4 mock + 3 real tests)
- End-to-end workflow
- Cache utilization
- Force regeneration

---

## Debugging Failed Tests

### View Detailed Error Output

```bash
# Show full error messages
uv run pytest tests/test_illustration_generator.py -v --tb=long

# Show local variables at failure point
uv run pytest tests/test_illustration_generator.py -v --tb=long --showlocals
```

### Debug Specific Functionality

```bash
# Test scene analysis with debug prints
uv run pytest tests/test_example_usage.py::TestDebuggingExamples::test_debug_scene_response_format -v -s

# Test image generation with debug prints
uv run pytest tests/test_example_usage.py::TestDebuggingExamples::test_debug_image_response_structure -v -s

# Test filename sanitization
uv run pytest tests/test_example_usage.py::TestDebuggingExamples::test_debug_filename_sanitization -v -s
```

### Run Tests in Verbose Mode

```bash
# Maximum verbosity
uv run pytest tests/ -vvv

# Show print statements
uv run pytest tests/ -v -s

# Stop on first failure
uv run pytest tests/ -v -x
```

---

## Environment Setup

### Required for All Tests

```bash
# Install dependencies
uv sync
```

### Required for Real API Tests

```bash
# Set API key
export GEMINI_API_KEY=your_api_key_here

# Verify it's set
echo $GEMINI_API_KEY
```

### Optional: Add to Shell Profile

```bash
# Add to ~/.zshrc or ~/.bashrc
echo 'export GEMINI_API_KEY=your_api_key_here' >> ~/.zshrc
source ~/.zshrc
```

---

## Test Results Summary

### Mock Tests
- **Total:** 46 tests
- **Status:** ✅ All passing
- **Time:** ~0.5 seconds
- **Cost:** $0 (no API calls)

### Real API Tests (Latest Run: 2025-12-25)
- **Total:** 4 tests
- **Status:** ✅ All passing
- **Time:** ~32 seconds
- **Cost:** ~4 API calls (1 scene analysis + 3 image generations)

**Performance Metrics:**
- Scene analysis: ~2 seconds
- Image generation: ~7-8 seconds per image
- Full pipeline (3 images): ~23 seconds
- Image sizes: 1-2 MB each (high quality)

---

## Continuous Integration (CI)

### Recommended CI Configuration

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      - name: Install dependencies
        run: pip install uv && uv sync
      - name: Run mock tests only
        run: uv run pytest tests/ -v -m "not requires_api"
```

**Note:** Real API tests should only run manually due to API costs.

---

## Troubleshooting

### Issue: Tests fail with "GEMINI_API_KEY not set"

**Solution:**
```bash
export GEMINI_API_KEY=your_api_key_here
# Then re-run the test
```

### Issue: Image validation fails with "Image too small"

**Cause:** Mock PNG data is incorrectly sized
**Fix:** Check that test fixtures create images > 1000 bytes

### Issue: JSON parsing fails

**Cause:** Gemini wrapped JSON in markdown code blocks
**Status:** ✅ Already handled by the code (extracts from ```json blocks)

### Issue: Can't find generated images

**Location:** `/Users/teristam/Documents/code/reader3/tests/output/images/`

**Check:**
```bash
ls -lah tests/output/images/
```

---

## Best Practices

### During Development
1. ✅ Run mock tests frequently (fast, free)
2. ✅ Use debugging tests with `-s` flag to see print output
3. ⚠️ Run real API tests sparingly (slow, costs money)
4. ✅ Generate test images only when you need to verify visual output

### Before Committing
```bash
# Run all mock tests
uv run pytest tests/ -v -m "not requires_api"
```

### Before Releasing
```bash
# Run full test suite including real API
uv run pytest tests/ -v -m requires_api
```

### For Debugging Visual Issues
```bash
# Generate and view test images
uv run pytest tests/test_save_real_images.py::test_generate_single_image_for_inspection -v -s -m requires_api
open tests/output/images/
```

---

## Files Reference

```
tests/
├── __init__.py                          # Package marker
├── conftest.py                          # Shared fixtures
├── test_illustration_generator.py       # Main test suite (40 tests)
├── test_example_usage.py                # Debugging examples (6 tests)
├── test_real_api.py                     # Real API integration (4 tests)
├── test_save_real_images.py             # Image generation for inspection (2 tests)
├── README.md                            # Test documentation
├── REAL_API_TEST_RESULTS.md             # Latest API test results
└── output/                              # Generated test images
    ├── README.md                        # Output directory guide
    └── images/                          # PNG files saved here
        └── *.png

pytest.ini                               # Pytest configuration
.gitignore                               # Excludes tests/output/
```

---

## Next Steps

1. **Run mock tests** to verify everything works:
   ```bash
   uv run pytest tests/ -v
   ```

2. **Generate a test image** to see the quality:
   ```bash
   uv run pytest tests/test_save_real_images.py::test_generate_single_image_for_inspection -v -s -m requires_api
   open tests/output/images/
   ```

3. **Review test coverage** in [tests/README.md](tests/README.md)

4. **Check latest API results** in [tests/REAL_API_TEST_RESULTS.md](tests/REAL_API_TEST_RESULTS.md)

---

## Support

For issues or questions:
1. Check test output with `-v -s` flags
2. Review [tests/README.md](tests/README.md) for detailed test documentation
3. Examine [tests/REAL_API_TEST_RESULTS.md](tests/REAL_API_TEST_RESULTS.md) for expected behavior
4. Use debugging tests in [test_example_usage.py](tests/test_example_usage.py)
