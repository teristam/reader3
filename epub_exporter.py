"""
EPUB export functionality for reader3.
Exports single chapters or full books with AI-generated illustrations.
"""

import os
import io
import re
from typing import List, Tuple, Dict, Optional
from bs4 import BeautifulSoup
from loguru import logger

from ebooklib import epub
from reader3 import Book, BookMetadata, ChapterContent, TOCEntry


# Constants
EPUB_IMAGES_DIR = "Images"  # Standard EPUB structure


def sanitize_filename(name: str, max_length: int = 100) -> str:
    """Make filename safe for filesystem."""
    # Remove/replace characters unsafe for filenames
    safe = re.sub(r'[<>:"/\\|?*]', '_', name)
    # Replace multiple spaces with single underscore
    safe = re.sub(r'\s+', '_', safe)
    # Limit length
    return safe[:max_length]


def create_epub_book(metadata: BookMetadata) -> epub.EpubBook:
    """Create and configure EpubBook with metadata."""
    book = epub.EpubBook()

    # Set identifier (use first if available, otherwise generate)
    if metadata.identifiers:
        book.set_identifier(metadata.identifiers[0])
    else:
        book.set_identifier(f'reader3-{metadata.title}')

    # Set title
    book.set_title(metadata.title)

    # Set language
    book.set_language(metadata.language or 'en')

    # Add authors
    for author in metadata.authors:
        book.add_author(author)

    # Add metadata
    if metadata.publisher:
        book.add_metadata('DC', 'publisher', metadata.publisher)

    if metadata.date:
        book.add_metadata('DC', 'date', metadata.date)

    if metadata.description:
        book.add_metadata('DC', 'description', metadata.description)

    for subject in metadata.subjects:
        book.add_metadata('DC', 'subject', subject)

    return book


def wrap_html_content(content: str, title: str, language: str = "en") -> str:
    """Wrap body content in complete HTML document."""
    return f'''<?xml version='1.0' encoding='utf-8'?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="{language}" lang="{language}">
<head>
    <meta charset="utf-8"/>
    <title>{title}</title>
</head>
<body>
{content}
</body>
</html>'''


def collect_images_from_html(html_content: str, book_id: str) -> List[Tuple[str, bytes, str]]:
    """
    Extract and load all images referenced in HTML.

    Returns:
        List of (src_path, image_bytes, mime_type) tuples
    """
    images = []
    soup = BeautifulSoup(html_content, 'html.parser')

    # Track seen images to avoid duplicates
    seen_images = set()

    for img in soup.find_all('img'):
        src = img.get('src', '')
        if not src or src in seen_images:
            continue

        seen_images.add(src)

        # Convert relative path to absolute
        img_path = os.path.join(book_id, src)

        if not os.path.exists(img_path):
            logger.warning(f"Image not found: {img_path}")
            continue

        try:
            with open(img_path, 'rb') as f:
                img_bytes = f.read()

            # Determine MIME type from extension
            ext = os.path.splitext(src)[1].lower()
            if ext in ['.jpg', '.jpeg']:
                mime_type = 'image/jpeg'
            elif ext == '.png':
                mime_type = 'image/png'
            elif ext == '.gif':
                mime_type = 'image/gif'
            elif ext == '.svg':
                mime_type = 'image/svg+xml'
            else:
                mime_type = 'image/png'  # Default fallback

            images.append((src, img_bytes, mime_type))
            logger.debug(f"Collected image: {src} ({mime_type})")
        except Exception as e:
            logger.error(f"Error reading image {img_path}: {e}")
            continue

    return images


def add_images_to_epub(epub_book: epub.EpubBook, images: List[Tuple[str, bytes, str]]) -> Dict[str, str]:
    """
    Add images to EPUB and return path mapping.

    Returns:
        Dict mapping original paths to EPUB internal paths
        e.g., {"images/foo.png": "Images/foo.png"}
    """
    path_mapping = {}

    for src_path, img_bytes, mime_type in images:
        # Extract just the filename
        filename = os.path.basename(src_path)

        # EPUB internal path
        epub_path = f"{EPUB_IMAGES_DIR}/{filename}"

        # Create EpubImage item
        img_item = epub.EpubItem(
            uid=f"image_{filename}",
            file_name=epub_path,
            media_type=mime_type,
            content=img_bytes
        )

        epub_book.add_item(img_item)
        path_mapping[src_path] = epub_path
        logger.debug(f"Added image to EPUB: {src_path} -> {epub_path}")

    return path_mapping


def rewrite_image_paths_for_epub(html: str, image_mapping: Dict[str, str]) -> str:
    """Update image src attributes to EPUB internal paths."""
    soup = BeautifulSoup(html, 'html.parser')

    for img in soup.find_all('img'):
        src = img.get('src', '')
        if src in image_mapping:
            img['src'] = image_mapping[src]
            logger.debug(f"Rewrote image path: {src} -> {image_mapping[src]}")

    return str(soup)


def rebuild_toc_for_epub(toc_entries: List[TOCEntry], href_to_item: Dict[str, epub.EpubHtml]) -> list:
    """
    Convert TOCEntry structure to ebooklib TOC format.

    Returns:
        List compatible with epub.toc assignment:
        - epub.Link for simple entries
        - (epub.Section, [children]) for nested entries
    """
    result = []

    for entry in toc_entries:
        # Get the corresponding EPUB item
        item = href_to_item.get(entry.file_href)
        if not item:
            logger.warning(f"TOC entry not found in spine: {entry.file_href}")
            continue

        # Build href with anchor if present
        href = entry.file_href
        if entry.anchor:
            href = f"{entry.file_href}#{entry.anchor}"

        if entry.children:
            # Nested section
            section = epub.Section(entry.title)
            children_toc = rebuild_toc_for_epub(entry.children, href_to_item)
            result.append((section, children_toc))
        else:
            # Simple link
            link = epub.Link(href, entry.title, entry.title)
            result.append(link)

    return result


def export_single_chapter(book: Book, chapter_index: int, book_id: str) -> bytes:
    """
    Export single chapter as EPUB file.

    Args:
        book: The Book object
        chapter_index: Index in the spine
        book_id: Book directory ID for loading images

    Returns:
        EPUB file as bytes
    """
    logger.info(f"Exporting single chapter {chapter_index} from {book_id}")

    # Validate chapter index
    if chapter_index < 0 or chapter_index >= len(book.spine):
        raise ValueError(f"Invalid chapter index: {chapter_index}")

    # Get the chapter
    chapter = book.spine[chapter_index]

    # Import here to avoid circular dependency
    from server import get_chapter_with_images

    # Get chapter HTML with injected AI images
    chapter_html = get_chapter_with_images(book_id, chapter_index, chapter.content)

    # Create modified metadata
    modified_metadata = BookMetadata(
        title=f"{book.metadata.title} - Chapter {chapter_index + 1}",
        authors=book.metadata.authors,
        language=book.metadata.language,
        description=f"Chapter {chapter_index + 1} from {book.metadata.title}",
        publisher=book.metadata.publisher,
        date=book.metadata.date,
        identifiers=book.metadata.identifiers,
        subjects=book.metadata.subjects
    )

    # Create EPUB book
    epub_book = create_epub_book(modified_metadata)

    # Collect images from chapter HTML
    images = collect_images_from_html(chapter_html, book_id)
    logger.info(f"Collected {len(images)} images for chapter")

    # Add images to EPUB and get path mapping
    image_mapping = add_images_to_epub(epub_book, images)

    # Rewrite image paths in HTML
    chapter_html = rewrite_image_paths_for_epub(chapter_html, image_mapping)

    # Wrap in complete HTML document
    full_html = wrap_html_content(chapter_html, chapter.title, book.metadata.language)

    # Create chapter item
    chapter_item = epub.EpubHtml(
        title=chapter.title,
        file_name='chapter.xhtml',
        lang=book.metadata.language
    )
    chapter_item.set_content(full_html.encode('utf-8'))

    # Add chapter to book
    epub_book.add_item(chapter_item)

    # Set spine (reading order)
    epub_book.spine = ['nav', chapter_item]

    # Set TOC (simple, just the chapter)
    epub_book.toc = [epub.Link('chapter.xhtml', chapter.title, 'chapter')]

    # Add navigation files
    epub_book.add_item(epub.EpubNcx())
    epub_book.add_item(epub.EpubNav())

    # Write to bytes
    output = io.BytesIO()
    epub.write_epub(output, epub_book)
    epub_bytes = output.getvalue()

    logger.info(f"Generated EPUB: {len(epub_bytes)} bytes")
    return epub_bytes


def export_full_book(book: Book, book_id: str) -> bytes:
    """
    Export full book with all chapters and AI images as EPUB.

    Args:
        book: The Book object
        book_id: Book directory ID for loading images

    Returns:
        EPUB file as bytes
    """
    logger.info(f"Exporting full book from {book_id}")

    # Create EPUB book with original metadata
    epub_book = create_epub_book(book.metadata)

    # Import here to avoid circular dependency
    from server import get_chapter_with_images

    # Process all chapters
    chapter_items = []
    all_images = []

    for idx, chapter in enumerate(book.spine):
        logger.info(f"Processing chapter {idx}: {chapter.title}")

        # Get chapter HTML with injected AI images
        chapter_html = get_chapter_with_images(book_id, idx, chapter.content)

        # Collect images from this chapter
        chapter_images = collect_images_from_html(chapter_html, book_id)
        all_images.extend(chapter_images)

        # Store chapter info for later processing
        chapter_items.append((chapter, chapter_html))

    # Deduplicate images by source path
    unique_images = {}
    for src_path, img_bytes, mime_type in all_images:
        if src_path not in unique_images:
            unique_images[src_path] = (src_path, img_bytes, mime_type)

    images_list = list(unique_images.values())
    logger.info(f"Collected {len(images_list)} unique images across all chapters")

    # Add images to EPUB and get path mapping
    image_mapping = add_images_to_epub(epub_book, images_list)

    # Create EPUB chapter items
    epub_chapters = []
    href_to_item = {}

    for idx, (chapter, chapter_html) in enumerate(chapter_items):
        # Rewrite image paths
        chapter_html = rewrite_image_paths_for_epub(chapter_html, image_mapping)

        # Wrap in complete HTML document
        full_html = wrap_html_content(chapter_html, chapter.title, book.metadata.language)

        # Create filename
        filename = f'chapter_{idx:04d}.xhtml'

        # Create chapter item
        chapter_item = epub.EpubHtml(
            title=chapter.title,
            file_name=filename,
            lang=book.metadata.language
        )
        chapter_item.set_content(full_html.encode('utf-8'))

        # Add to book
        epub_book.add_item(chapter_item)
        epub_chapters.append(chapter_item)

        # Map original href to EPUB item (for TOC building)
        href_to_item[chapter.href] = chapter_item
        href_to_item[filename] = chapter_item

    # Set spine (reading order)
    epub_book.spine = ['nav'] + epub_chapters

    # Rebuild TOC from original book structure
    if book.toc:
        try:
            epub_book.toc = rebuild_toc_for_epub(book.toc, href_to_item)
            logger.info("Rebuilt TOC from original structure")
        except Exception as e:
            logger.error(f"Error rebuilding TOC: {e}")
            # Fallback to flat TOC
            epub_book.toc = [
                epub.Link(f'chapter_{idx:04d}.xhtml', ch.title, f'ch{idx}')
                for idx, ch in enumerate(book.spine)
            ]
    else:
        # Create simple flat TOC
        epub_book.toc = [
            epub.Link(f'chapter_{idx:04d}.xhtml', ch.title, f'ch{idx}')
            for idx, ch in enumerate(book.spine)
        ]

    # Add navigation files
    epub_book.add_item(epub.EpubNcx())
    epub_book.add_item(epub.EpubNav())

    # Write to bytes
    output = io.BytesIO()
    epub.write_epub(output, epub_book)
    epub_bytes = output.getvalue()

    logger.info(f"Generated EPUB: {len(epub_bytes)} bytes, {len(epub_chapters)} chapters")
    return epub_bytes
