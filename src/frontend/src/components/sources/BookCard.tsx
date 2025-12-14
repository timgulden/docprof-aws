import { useState, useEffect, useRef } from "react";
import { Check, Trash2, BookOpen, AlertCircle } from "lucide-react";
import type { Book } from "../../types/api";
import { deleteBook } from "../../api/books";
import { useBooksStore } from "../../store/booksStore";
import { apiClient } from "../../api/client";

interface BookCardProps {
  book: Book;
  isSelected: boolean;
  isLastSelected: boolean;
  onRefetch: () => void;
  onOpenPdf?: (book: Book) => void;
}

export const BookCard = ({ book, isSelected, isLastSelected, onRefetch, onOpenPdf }: BookCardProps) => {
  const [isDeleting, setIsDeleting] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [imageError, setImageError] = useState(false);
  const [coverBlobUrl, setCoverBlobUrl] = useState<string | null>(null);
  const blobUrlRef = useRef<string | null>(null);
  const toggleBookSelection = useBooksStore((state) => state.toggleBookSelection);

  // Fetch cover image as blob with auth headers, then create blob URL
  useEffect(() => {
    let isMounted = true;
    
    const fetchCover = async () => {
      try {
        // Get just the path, not the full URL (apiClient already has baseURL)
        const coverPath = `/books/${book.book_id}/cover`;
        // Use axios to fetch with auth headers, responseType blob for images
        // Explicitly set Accept header to image/jpeg to help API Gateway handle binary correctly
        const response = await apiClient.get(coverPath, {
          responseType: 'blob',
          headers: {
            'Accept': 'image/jpeg, image/*, */*'
          }
        });
        
        // Only update state if component is still mounted
        if (!isMounted) return;
        
        // Debug logging
        console.log('Cover response for', book.book_id, ':', {
          status: response.status,
          contentType: response.headers['content-type'],
          blobType: response.data?.type,
          blobSize: response.data?.size,
          isBlob: response.data instanceof Blob
        });
        
        // response.data is already a Blob when responseType is 'blob'
        if (response.data instanceof Blob && response.data.size > 0) {
          // Ensure the blob has the correct MIME type
          const blob = response.data.type?.startsWith('image/') 
            ? response.data 
            : new Blob([response.data], { type: response.headers['content-type'] || 'image/jpeg' });
          
          const blobUrl = URL.createObjectURL(blob);
          
          // Clean up previous blob URL if it exists
          if (blobUrlRef.current) {
            URL.revokeObjectURL(blobUrlRef.current);
          }
          
          blobUrlRef.current = blobUrl;
          setCoverBlobUrl(blobUrl);
          setImageError(false);
          
          console.log('Created blob URL for', book.book_id, ':', blobUrl.substring(0, 50) + '...');
        } else {
          // Invalid blob response
          console.warn('Invalid blob response for', book.book_id, ':', response.data);
          setImageError(true);
          setCoverBlobUrl(null);
        }
      } catch (error: any) {
        // Only update state if component is still mounted
        if (!isMounted) return;
        
        // Log errors for debugging
        console.error('Failed to load cover image for book', book.book_id, ':', error?.message || error);
        setImageError(true);
        setCoverBlobUrl(null);
      }
    };

    // Only fetch if we have a valid book_id
    if (book?.book_id) {
      fetchCover();
    }

    // Cleanup: revoke blob URL when component unmounts or book changes
    return () => {
      isMounted = false;
      if (blobUrlRef.current) {
        URL.revokeObjectURL(blobUrlRef.current);
        blobUrlRef.current = null;
      }
    };
  }, [book.book_id]);

  const handleDelete = async () => {
    setIsDeleting(true);
    try {
      await deleteBook(book.book_id);
      onRefetch();
    } catch (error) {
      console.error("Error deleting book:", error);
      alert("Failed to delete book. Please try again.");
    } finally {
      setIsDeleting(false);
      setShowDeleteConfirm(false);
    }
  };

  const handleToggleSelection = () => {
    toggleBookSelection(book.book_id);
  };

  const handleCardClick = () => {
    if (onOpenPdf) {
      onOpenPdf(book);
    }
  };

  return (
    <div
      className={`group relative overflow-hidden rounded-lg border-2 bg-white shadow-sm transition-all hover:shadow-md ${
        isSelected ? "border-blue-600 opacity-100" : "border-slate-200 opacity-20 hover:opacity-60"
      }`}
      onClick={handleCardClick}
    >
      {/* Selection indicator */}
      {isSelected && (
        <div className="absolute right-2 top-2 z-10 rounded-full bg-blue-600 p-1 shadow-md">
          <Check className="h-4 w-4 text-white" />
        </div>
      )}

      {/* Cover image */}
      <div className="relative h-64 w-full overflow-hidden bg-slate-100">
        {!imageError && coverBlobUrl ? (
          <img
            src={coverBlobUrl}
            alt={`Cover of ${book.title}`}
            className="h-full w-full object-cover"
            onError={(e) => {
              console.error('Image load error for', book.book_id, ':', e);
              setImageError(true);
            }}
            onLoad={() => {
              console.log('Image loaded successfully for', book.book_id);
            }}
          />
        ) : imageError ? (
          <div className="flex h-full w-full flex-col items-center justify-center text-slate-400">
            <BookOpen className="h-16 w-16" />
            <p className="mt-2 text-sm">No cover available</p>
          </div>
        ) : (
          <div className="flex h-full w-full flex-col items-center justify-center text-slate-300">
            <BookOpen className="h-16 w-16 animate-pulse" />
            <p className="mt-2 text-sm">Loading cover...</p>
          </div>
        )}
      </div>

      {/* Book info */}
      <div className="p-4">
        <h3 className="line-clamp-2 font-semibold text-slate-900">{book.title}</h3>
        {book.author && (
          <p className="mt-1 line-clamp-1 text-sm text-slate-600">{book.author}</p>
        )}
        
        {/* Metadata */}
        <div className="mt-3 flex flex-wrap gap-2 text-xs text-slate-500">
          {book.edition && (
            <span className="rounded-full bg-slate-100 px-2 py-1">{book.edition}</span>
          )}
          {book.total_pages && (
            <span className="rounded-full bg-slate-100 px-2 py-1">
              {book.total_pages} pages
            </span>
          )}
        </div>

        {/* Action buttons */}
        <div className="mt-4 flex gap-2">
          <button
            onClick={(e) => {
              e.stopPropagation();
              handleToggleSelection();
            }}
            disabled={isSelected && isLastSelected}
            className={`flex-1 rounded-md px-3 py-2 text-sm font-medium transition-colors ${
              isSelected
                ? isLastSelected
                  ? "bg-slate-100 text-slate-400 cursor-not-allowed"
                  : "bg-slate-100 text-slate-700 hover:bg-slate-200"
                : "bg-blue-600 text-white hover:bg-blue-700"
            }`}
            title={isSelected && isLastSelected ? "At least one book must be selected" : ""}
          >
            {isSelected ? "Deselect" : "Select"}
          </button>
          
          {!showDeleteConfirm ? (
            <button
              onClick={(e) => {
                e.stopPropagation();
                setShowDeleteConfirm(true);
              }}
              className="rounded-md border border-slate-300 p-2 text-slate-600 transition-colors hover:border-red-300 hover:bg-red-50 hover:text-red-600"
              title="Delete book"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          ) : (
            <button
              onClick={(e) => {
                e.stopPropagation();
                handleDelete();
              }}
              disabled={isDeleting}
              className="flex items-center gap-1 rounded-md border border-red-300 bg-red-50 px-3 py-2 text-xs font-medium text-red-600 hover:bg-red-100 disabled:opacity-50"
            >
              <AlertCircle className="h-3 w-3" />
              {isDeleting ? "Deleting..." : "Confirm"}
            </button>
          )}
        </div>
        
        {showDeleteConfirm && !isDeleting && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              setShowDeleteConfirm(false);
            }}
            className="mt-2 w-full text-xs text-slate-500 hover:text-slate-700"
          >
            Cancel
          </button>
        )}
      </div>
    </div>
  );
};

