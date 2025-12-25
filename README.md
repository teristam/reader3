# reader 3

![reader3](reader3.png)

A lightweight, self-hosted EPUB reader that lets you read through EPUB books one chapter at a time. This makes it very easy to copy paste the contents of a chapter to an LLM, to read along. Basically - get epub books (e.g. [Project Gutenberg](https://www.gutenberg.org/) has many), open them up in this reader, copy paste text around to your favorite LLM, and read together and along.

This project was 90% vibe coded just to illustrate how one can very easily [read books together with LLMs](https://x.com/karpathy/status/1990577951671509438). I'm not going to support it in any way, it's provided here as is for other people's inspiration and I don't intend to improve it. Code is ephemeral now and libraries are over, ask your LLM to change it in whatever way you like.

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

## AI Illustration Generation

The reader includes an optional feature to automatically generate illustrations for chapters using Google's Gemini API (Nano Banana for image generation).

### Setup

1. Get a Gemini API key from [Google AI Studio](https://aistudio.google.com/app/apikey)

2. Set the API key as an environment variable:
   ```bash
   export GEMINI_API_KEY=your_api_key_here
   ```

3. When you open a chapter, illustrations will be automatically generated in the background. You can also manually trigger generation using the "Generate Illustrations" button.

The generated images are cached locally in the book's `images/` directory, so they won't be regenerated unless you click "Regenerate Illustrations".

## License

MIT