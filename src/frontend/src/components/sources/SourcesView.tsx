import { useQuery } from "@tanstack/react-query";
import { Plus, Loader2, BookOpen } from "lucide-react";
import { useState, useEffect, useRef } from "react";

import { fetchAllBooks } from "../../api/books";
import { useBooksStore } from "../../store/booksStore";
import { BookCard } from "./BookCard";
import { ProcessingBookCard } from "./ProcessingBookCard";
import { UploadBookModal } from "./UploadBookModal";
import { PDFViewer } from "../pdf/PDFViewer";
import type { Book } from "../../types/api";

export const SourcesView = () => {
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
  const [viewerBook, setViewerBook] = useState<Book | null>(null);
  const selectedBookIds = useBooksStore((state) => state.selectedBookIds);
  const selectAllBooks = useBooksStore((state) => state.selectAllBooks);
  const toggleBookSelection = useBooksStore((state) => state.toggleBookSelection);
  const hasInitialized = useRef(false);

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["books"],
    queryFn: fetchAllBooks,
  });

  const books = data ?? [];

  // Separate books by ingestion status (calculate before early returns)
  const processingBooks = books.filter(
    (book) => book.ingestion_status && book.ingestion_status !== "complete"
  );
  const completedBooks = books.filter(
    (book) => !book.ingestion_status || book.ingestion_status === "complete"
  );

  // Initialize selection ONCE on first load - select only COMPLETED books by default
  // Exclude processing books from initial selection
  // Only runs if no books are currently selected AND we haven't initialized yet
  useEffect(() => {
    if (books.length > 0 && selectedBookIds.length === 0 && !hasInitialized.current) {
      // Only select books that are completed (not processing)
      const completedBookIds = books
        .filter((book) => !book.ingestion_status || book.ingestion_status === "complete")
        .map((book) => book.book_id);
      if (completedBookIds.length > 0) {
        selectAllBooks(completedBookIds);
      }
      hasInitialized.current = true;
    }
  }, [books, selectedBookIds.length, selectAllBooks]);
  
  // Deselect any books that are now processing (they were selected before processing started)
  // This ensures processing books are never selected
  useEffect(() => {
    const processingBookIds = new Set(processingBooks.map(b => b.book_id));
    selectedBookIds.forEach((bookId) => {
      if (processingBookIds.has(bookId)) {
        // Book is processing but still selected - deselect it
        toggleBookSelection(bookId);
      }
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [processingBooks.length, books.map(b => `${b.book_id}:${b.ingestion_status}`).join(',')]);

  // Early returns AFTER all hooks
  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="flex items-center space-x-2 text-slate-600">
          <Loader2 className="h-6 w-6 animate-spin" />
          <span>Loading books...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="text-center">
          <p className="text-lg font-semibold text-red-600">Error loading books</p>
          <p className="mt-2 text-sm text-slate-600">{(error as Error).message}</p>
          <button
            onClick={() => refetch()}
            className="mt-4 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
          >
            Try Again
          </button>
        </div>
      </div>
    );
  }

  // Only count selected books that actually exist in completedBooks
  // This prevents counting deleted books or books that are still processing
  const completedBookIds = new Set(completedBooks.map((book) => book.book_id));
  const selectedCount = selectedBookIds.filter((id) => completedBookIds.has(id)).length;
  const totalCount = completedBooks.length; // Only count completed books

  return (
    <div className="space-y-6 h-full flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-slate-900">Knowledge Sources</h1>
          <p className="mt-2 text-sm text-slate-600">
            {selectedCount} of {totalCount} {totalCount === 1 ? "book" : "books"} selected for use in your sessions
            {processingBooks.length > 0 && (
              <span className="ml-2 text-blue-600">
                · {processingBooks.length} {processingBooks.length === 1 ? "book" : "books"} processing
              </span>
            )}
          </p>
        </div>
        <button
          onClick={() => setIsUploadModalOpen(true)}
          className="flex items-center space-x-2 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          <Plus size={18} />
          <span>Add Book</span>
        </button>
      </div>

      {/* Main content: left = sources grid, right = PDF viewer */}
      <div className="flex-1 flex gap-6 min-h-0">
        {/* Left side: sources lists */}
        <div className="flex-1 space-y-8 overflow-y-auto pr-1">
          {/* Empty state */}
          {books.length === 0 ? (
            <div className="flex flex-col items-center justify-center rounded-lg border-2 border-dashed border-slate-300 bg-slate-50 py-12">
              <BookOpen className="mb-4 h-12 w-12 text-slate-400" />
              <h2 className="text-lg font-semibold text-slate-900">No books yet</h2>
              <p className="mt-2 text-sm text-slate-600">Upload your first book to get started</p>
              <button
                onClick={() => setIsUploadModalOpen(true)}
                className="mt-4 flex items-center space-x-2 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
              >
                <Plus size={18} />
                <span>Add Book</span>
              </button>
            </div>
          ) : (
            <>
              {/* Processing Books Section */}
              {processingBooks.length > 0 && (
                <div>
                  <h2 className="mb-4 text-lg font-semibold text-slate-900">
                    Processing ({processingBooks.length})
                  </h2>
                  <div className={`grid gap-6 ${
                    viewerBook
                      ? "grid-cols-1 sm:grid-cols-2 lg:grid-cols-2 xl:grid-cols-2"
                      : "grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4"
                  }`}>
                    {processingBooks.map((book) => (
                      <ProcessingBookCard
                        key={book.book_id}
                        book={book}
                        onComplete={(bookId) => {
                          // Auto-select the newly completed book when it finishes processing
                          if (!selectedBookIds.includes(bookId)) {
                            toggleBookSelection(bookId);
                          }
                          // Refetch to get updated status (book will move to completedBooks)
                          refetch();
                        }}
                      />
                    ))}
                  </div>
                </div>
              )}

              {/* Completed Books Section */}
              {completedBooks.length > 0 && (
                <div>
                  {processingBooks.length > 0 && (
                    <h2 className="mb-4 text-lg font-semibold text-slate-900">
                      Available ({completedBooks.length})
                    </h2>
                  )}
                  <div className={`grid gap-6 ${
                    viewerBook
                      ? "grid-cols-1 sm:grid-cols-2 lg:grid-cols-2 xl:grid-cols-2"
                      : "grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4"
                  }`}>
                    {completedBooks.map((book) => {
                      const isSelected = selectedBookIds.includes(book.book_id);
                      const isLastSelected = isSelected && selectedBookIds.length === 1;
                      return (
                        <BookCard
                          key={book.book_id}
                          book={book}
                          isSelected={isSelected}
                          isLastSelected={isLastSelected}
                          onRefetch={refetch}
                          onOpenPdf={(b) => {
                            setViewerBook(b);
                          }}
                        />
                      );
                    })}
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        {/* Right side: PDF viewer panel */}
        {viewerBook && (
          <div className="w-1/2 min-w-[320px] bg-white border border-slate-300 rounded-lg flex flex-col max-h-full overflow-y-auto">
            <PDFViewer
              bookId={viewerBook.book_id}
              initialPage={1}
              bookTitle={viewerBook.title}
              onClose={() => setViewerBook(null)}
            />
          </div>
        )}
      </div>

      {/* Upload Modal */}
      <UploadBookModal
        isOpen={isUploadModalOpen}
        onClose={() => setIsUploadModalOpen(false)}
        onUploadSuccess={() => {
          refetch();
          setIsUploadModalOpen(false);
        }}
      />
    </div>
  );
};

