#!/usr/bin/env python3
import pickle
from reader3 import Book

with open('book_data/book.pkl', 'rb') as f:
    book = pickle.load(f)

print('Book has cover_image attr?', hasattr(book, 'cover_image'))
print('\nAll Book attributes:', [a for a in dir(book) if not a.startswith('_')])
print(f'\nTotal images: {len(book.images)}')
print('\nLooking for 00_mb:')
for k, v in book.images.items():
    if '00_mb' in k.lower():
        print(f'  "{k}" -> "{v}"')
