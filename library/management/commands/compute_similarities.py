# # library/management/commands/compute_similarities.py
#
# from django.core.management.base import BaseCommand
# from library.models import Book, BookSimilarity
#
#
# class Command(BaseCommand):
#     help = 'Compute and store book similarities'
#
#     def compute_book_similarity(self, book1, book2):
#         # Weights for authors and shelves
#         author_weight = 0.7
#         shelf_weight = 0.3
#
#         # Author similarity (1 if they share an author, else 0)
#         authors1 = set(book1.authors.all())
#         authors2 = set(book2.authors.all())
#         author_similarity = 1 if authors1 & authors2 else 0
#
#         # Shelf similarity (Jaccard similarity)
#         shelves1 = set(book1.shelves.all())
#         shelves2 = set(book2.shelves.all())
#         if shelves1 | shelves2:
#             shelf_similarity = len(shelves1 & shelves2) / len(shelves1 | shelves2)
#         else:
#             shelf_similarity = 0
#
#         # Combined similarity
#         similarity = (author_weight * author_similarity) + (shelf_weight * shelf_similarity)
#         return similarity
#
#     def handle(self, *args, **options):
#         books = Book.objects.all()
#         total_books = books.count()
#         self.stdout.write(f'Total books: {total_books}')
#
#         # Clear existing similarities
#         BookSimilarity.objects.all().delete()
#
#         # Limit the number of similar books per book to improve performance
#         MAX_SIMILARS = 50  # Adjust as necessary
#
#         for book in books:
#             similar_books = []
#             # Get books that share at least one shelf or author
#             candidates = Book.objects.filter(
#                 shelves__in=book.shelves.all()
#             ).exclude(id=book.id).distinct()
#
#             for candidate in candidates:
#                 similarity = self.compute_book_similarity(book, candidate)
#                 if similarity > 0:
#                     similar_books.append((candidate, similarity))
#
#             # Sort and keep top N similar books
#             similar_books.sort(key=lambda x: x[1], reverse=True)
#             top_similars = similar_books[:MAX_SIMILARS]
#
#             # Bulk create similarities
#             similarities = [
#                 BookSimilarity(book1=book, book2=sim[0], similarity=sim[1])
#                 for sim in top_similars
#             ]
#             BookSimilarity.objects.bulk_create(similarities)
#
#             self.stdout.write(f'Processed book ID {book.id}')
#
#         self.stdout.write(self.style.SUCCESS('Successfully computed book similarities.'))
# library/management/commands/compute_similarities.py

from django.core.management.base import BaseCommand
from library.models import Book, BookSimilarity
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from django.db import transaction

class Command(BaseCommand):
    help = 'Compute and store book similarities using vectorization'

    def handle(self, *args, **options):
        self.stdout.write('Fetching book data...')
        books = Book.objects.all()
        total_books = books.count()
        self.stdout.write(f'Total books: {total_books}')

        # Clear existing similarities
        BookSimilarity.objects.all().delete()

        # Prepare data for vectorization
        self.stdout.write('Preparing data for vectorization...')
        book_ids = []
        documents = []  # Each document represents a book's features

        for book in books:
            book_ids.append(book.id)
            authors = ' '.join([f'{author.first_name}_{author.last_name}' for author in book.authors.all()])
            shelves = ' '.join([shelf.name.replace(' ', '_') for shelf in book.shelves.all()])
            # Combine features
            document = f'{authors} {shelves}'
            documents.append(document)

        self.stdout.write('Vectorizing documents...')
        # Use TF-IDF Vectorizer
        vectorizer = TfidfVectorizer()
        tfidf_matrix = vectorizer.fit_transform(documents)

        self.stdout.write('Computing cosine similarity matrix...')
        # Compute cosine similarity matrix
        cosine_sim = cosine_similarity(tfidf_matrix)

        # For each book, find top N similar books
        MAX_SIMILARS = 50  # Adjust as necessary

        self.stdout.write('Storing similarities...')
        similarities_to_create = []
        for idx, book_id in enumerate(book_ids):
            # Get similarity scores for the current book
            sim_scores = cosine_sim[idx]
            # Get indices of the top similar books (excluding itself)
            similar_indices = sim_scores.argsort()[::-1][1:MAX_SIMILARS+1]
            for sim_idx in similar_indices:
                similar_book_id = book_ids[sim_idx]
                similarity = sim_scores[sim_idx]
                if similarity > 0:
                    similarities_to_create.append(
                        BookSimilarity(
                            book1_id=book_id,
                            book2_id=similar_book_id,
                            similarity=similarity
                        )
                    )
            if idx % 100 == 0:
                self.stdout.write(f'Processed {idx} books...')

        # Bulk create all similarities
        self.stdout.write('Bulk creating similarities...')
        with transaction.atomic():
            BookSimilarity.objects.bulk_create(similarities_to_create, batch_size=10000)

        self.stdout.write(self.style.SUCCESS('Successfully computed and stored book similarities.'))
