# reader 3

![reader3](reader3.png)

A lightweight, self-hosted EPUB reader designed for reading books alongside LLMs. Read through EPUB books chapter-by-chapter, with optional AI-generated illustrations, text-to-speech narration, and easy export for LLM analysis.

**Key Features:**
- 📖 Clean, distraction-free reading interface
- 🎨 AI-generated contextual illustrations (Gemini)
- 🔊 Natural text-to-speech narration
- 📤 One-click chapter/book export
- 💾 Local-first with smart caching

It is a heavily modified version from Karpathy's reader 3 repo to provide a better experience when reading fictions.

## Usage

The project uses [uv](https://docs.astral.sh/uv/). So for example, download [Dracula EPUB3](https://www.gutenberg.org/ebooks/345) to this directory as `dracula.epub`, then:

```bash
uv run reader3.py dracula.epub
```

This creates the directory `dracula_data`, which registers the book to your local library. We can then run the server:

```bash
uv run server.py
```

And visit [localhost:8123](http://localhost:8123/) to see your current Library. You can easily add more books, or delete them from your library by deleting the folder. It's not supposed to be complicated or complex.

## Features

### AI Illustration Generation

Generate contextual illustrations for your books using Google's Gemini API. The system intelligently places images at meaningful points in the narrative using sentence-based anchoring.

**Setup:**

1. Get a Gemini API key from [Google AI Studio](https://aistudio.google.com/app/apikey)
2. Create a `.env` file in the project root:
   ```bash
   GEMINI_API_KEY=your_api_key_here
   ```

   Alternatively, set the environment variable:
   ```bash
   export GEMINI_API_KEY=your_api_key_here
   ```

**Usage:**

- **Single Chapter**: Click the floating action button (lower right) → "Generate Illustrations" to generate 3 illustrations for the current chapter
- **Entire Book**: Click the book menu icon next to the book title → "Generate All Illustrations" to batch process all chapters
  - Generates for chapters with 1000+ words
  - Processes 3 chapters in parallel
  - Shows real-time progress that persists across page refreshes
  - Intelligently skips short chapters (TOC, acknowledgments, etc.)

**How it works:**

1. Gemini analyzes the chapter and identifies 3 key scenes
2. For each scene, it selects the exact sentence where the illustration should appear (before key action to set the scene)
3. Images are generated using `gemini-2.5-flash-image` model
4. Smart text matching finds the paragraph containing the anchor sentence (with fuzzy matching fallback)
5. Images are inserted immediately after the matched paragraph

Generated images are cached in the book's `images/` directory and won't regenerate unless you explicitly click "Regenerate Illustrations". The TOC shows visual indicators (blue image icons) next to chapters with illustrations.

### Text-to-Speech (TTS)

Listen to paragraphs read aloud using Gemini's natural-sounding TTS voices.

**Setup:**

Requires the same `GEMINI_API_KEY` as illustration generation.

**Usage:**

1. Click on any paragraph in the reader
2. A speaker icon appears in the paragraph controls
3. Click the speaker icon to generate and play audio
4. Audio is cached locally for instant replay

**Features:**

- Natural-sounding voice (default: "Kore")
- Automatic caching - generated audio is saved to `audio/` directory
- Handles paragraphs up to 5000 characters
- 24kHz, 16-bit mono WAV format

### Chapter Export

Export individual chapters or entire books for offline reading or LLM analysis.

**Usage:**

- **Single Chapter**: Click "Export Chapter" button in the chapter view
- **Full Book**: Click book menu → "Export Book"

Exported files include all text content and can be easily copy-pasted into LLMs for analysis or discussion.

## File Structure

After processing an EPUB, the following structure is created:

```
books/
├── book_name.epub                    # Original EPUB file
└── book_name_data/
    ├── book.pkl                      # Serialized book data
    ├── images/                       # Images directory
    │   ├── *.jpg, *.png              # Original EPUB images
    │   └── generated_ch*_scene*.png  # AI-generated illustrations (optional)
    ├── audio/                        # TTS audio files (optional)
    │   └── tts_*.wav                 # Generated paragraph audio
    ├── generated_images.json         # Illustration metadata (optional)
    └── tts_metadata.json             # TTS metadata (optional)
```

You can delete any book by removing its directory, or archive books by moving them out of the `books/` folder.

## License

MIT