# Tests for reader3

This directory contains pytest tests for the reader3 EPUB reader application.

## Running Tests

### Run all tests
```bash
uv run pytest
```

### Run specific test file
```bash
uv run pytest tests/test_illustration_generator.py
```

### Run with verbose output
```bash
uv run pytest -v
```

### Run specific test class or function
```bash
uv run pytest tests/test_illustration_generator.py::TestSummarizeScenes
uv run pytest tests/test_illustration_generator.py::TestSummarizeScenes::test_successful_scene_analysis
```

## Test Structure

### `conftest.py`
Contains shared pytest fixtures used across test files:
- `temp_book_dir`: Temporary directory for test book data
- `sample_chapter_text`: Sample chapter content for testing
- `sample_scenes`: Mock scene analysis data
- `mock_gemini_client`: Mock Gemini API client
- `mock_scene_response`: Mock scene analysis API response
- `mock_image_response`: Mock image generation API response
- `mock_env_with_api_key`: Environment setup with API key
- `sample_html_content`: Sample HTML for injection testing

### `test_illustration_generator.py`
Comprehensive tests for the illustration generator module covering:

#### `TestSanitizeChapterTitle` (6 tests)
- Basic alphanumeric preservation
- Special character removal
- Multiple space collapsing
- Length truncation
- Empty string fallback
- Leading/trailing underscore removal

#### `TestGetGeminiClient` (3 tests)
- Missing API key error handling
- Client creation with valid API key
- Error when google-genai package not installed

#### `TestSummarizeScenes` (6 tests)
- Successful scene analysis with JSON response
- Handling JSON wrapped in markdown code blocks
- Fallback behavior on JSON parse errors
- Empty text handling
- Padding when fewer than 3 scenes returned
- API error propagation

#### `TestCreateImagePrompt` (3 tests)
- Basic prompt creation
- Prompt creation with book title context
- Prompt creation without book title

#### `TestGenerateImage` (3 tests)
- Successful image generation
- Error handling when no image in response
- Validation of suspiciously small images

#### `TestSaveImage` (5 tests)
- Saving valid PNG images
- Including chapter title in filename
- Rejecting images that are too small
- Rejecting images with invalid PNG headers
- Directory creation if it doesn't exist

#### `TestCaching` (6 tests)
- Returning None when no metadata exists
- Successfully retrieving cached images
- Handling old metadata format (backward compatibility)
- Returning None when cached files are missing
- Saving new metadata file
- Appending to existing metadata file

#### `TestInjectImagesIntoHtml` (4 tests)
- Injecting images at calculated paragraph positions
- Handling HTML without paragraphs
- Handling empty image lists
- Handling boundary locations (0% and 100%)

#### `TestGenerateIllustrationsForChapter` (4 integration tests)
- Full generation pipeline (scene analysis → image generation → saving)
- Cache usage when images already exist
- Force regeneration bypassing cache
- Error handling during generation

## Test Coverage

The test suite provides comprehensive coverage of:
1. **String sanitization** for filesystem-safe filenames
2. **API client initialization** and error handling
3. **Scene analysis** with Gemini Flash model
4. **Image generation** with Gemini Image model
5. **Image validation** (PNG format, minimum size)
6. **File I/O operations** (saving images, metadata)
7. **Caching mechanisms** (metadata storage, retrieval)
8. **HTML manipulation** (injecting images into content)
9. **Integration flows** (complete illustration pipeline)
10. **Error handling** at each stage of the pipeline

## Mock Strategy

Tests use mocks to avoid:
- Actual API calls to Gemini (costly and slow)
- Real file system operations in temporary directories (isolated)
- Network dependencies (reliable offline testing)

All mocks simulate real API responses and file formats to ensure tests are realistic.

## Adding New Tests

When adding new tests:
1. Place shared fixtures in `conftest.py`
2. Group related tests in classes (e.g., `TestFunctionName`)
3. Use descriptive test names (e.g., `test_function_handles_edge_case`)
4. Add docstrings explaining what each test validates
5. Use appropriate markers if needed (see `pytest.ini`)
