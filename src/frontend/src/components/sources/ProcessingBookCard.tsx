import React, { useEffect, useState, useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import { Loader2, CheckCircle2, AlertCircle } from "lucide-react";
import { getIngestionStatus } from "../../api/books";
import { apiClient } from "../../api/client";
import type { Book } from "../../types/api";

interface ProcessingBookCardProps {
  book: Book;
  onComplete?: (bookId: string) => void;
}

/**
 * ProcessingBookCard - Shows real-time ingestion progress
 * 
 * Polls /api/books/{id}/ingestion-status every 2 seconds while processing.
 * Displays:
 * - Book cover (faded)
 * - Progress bar (0-100%)
 * - Current step & message
 * - Estimated time remaining (optional)
 */
export const ProcessingBookCard: React.FC<ProcessingBookCardProps> = ({ book, onComplete }) => {
  const [lastProgress, setLastProgress] = useState(0);
  const [coverBlobUrl, setCoverBlobUrl] = useState<string | null>(null);
  const blobUrlRef = useRef<string | null>(null);

  // Poll ingestion status every 2 seconds while processing
  const { data: status, isError } = useQuery({
    queryKey: ["ingestion-status", book.book_id],
    queryFn: () => getIngestionStatus(book.book_id),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      // Stop polling if complete or error
      if (status === "complete" || status === "error") {
        return false;
      }
      return 2000; // Poll every 2 seconds
    },
    refetchIntervalInBackground: true,
    staleTime: 0, // Always consider stale so it refetches
  });

  // Fetch cover image as blob with auth headers
  useEffect(() => {
    let isMounted = true;
    
    const fetchCover = async () => {
      try {
        // Get just the path, not the full URL (apiClient already has baseURL)
        if (!book?.book_id) return;
        
        const coverPath = `/books/${book.book_id}/cover`;
        const response = await apiClient.get(coverPath, {
          responseType: 'blob'
        });
        
        // Only update state if component is still mounted
        if (!isMounted) return;
        
        // response.data is already a Blob when responseType is 'blob'
        if (response.data instanceof Blob && response.data.size > 0) {
          const blobUrl = URL.createObjectURL(response.data);
          
          if (blobUrlRef.current) {
            URL.revokeObjectURL(blobUrlRef.current);
          }
          blobUrlRef.current = blobUrl;
          setCoverBlobUrl(blobUrl);
        }
      } catch (error: any) {
        // Silently handle errors - just don't show image
        console.warn('Failed to load cover image for book', book?.book_id, ':', error?.message || error);
      }
    };

    if (book?.book_id) {
      fetchCover();
    }

    return () => {
      isMounted = false;
      if (blobUrlRef.current) {
        URL.revokeObjectURL(blobUrlRef.current);
        blobUrlRef.current = null;
      }
    };
  }, [book?.book_id]);

  // Smooth progress animation
  useEffect(() => {
    if (status?.progress?.progress !== undefined) {
      setLastProgress(status.progress.progress);
    }
  }, [status?.progress?.progress]);

  // Call onComplete when ingestion finishes
  useEffect(() => {
    if (status?.status === "complete" && onComplete) {
      // Delay slightly to show 100% before refreshing
      const timer = setTimeout(() => onComplete(book.book_id), 1000);
      return () => clearTimeout(timer);
    }
  }, [status?.status, onComplete, book.book_id]);

  const progress = status?.progress?.progress || 0;
  const currentStatus = status?.status || book.ingestion_status || "pending";

  return (
    <div className="relative overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
      {/* Cover Image - Faded */}
      <div className="relative h-64 w-full bg-slate-100">
        {coverBlobUrl && (
          <img
            src={coverBlobUrl}
            alt={book.title}
            className="h-full w-full object-cover opacity-40"
          />
        )}
        {/* Status Overlay */}
        <div className="absolute inset-0 flex items-center justify-center bg-white/60 backdrop-blur-sm">
          {currentStatus === "processing" && (
            <Loader2 className="h-12 w-12 animate-spin text-blue-500" />
          )}
          {currentStatus === "complete" && (
            <CheckCircle2 className="h-12 w-12 text-green-500" />
          )}
          {currentStatus === "error" && (
            <AlertCircle className="h-12 w-12 text-red-500" />
          )}
        </div>
      </div>

      {/* Book Info */}
      <div className="p-4">
        <h3 className="font-semibold text-slate-900 line-clamp-2">
          {book.title}
        </h3>
        {book.author && (
          <p className="mt-1 text-sm text-slate-600">{book.author}</p>
        )}

        {/* Progress Bar */}
        {currentStatus === "processing" && (
          <div className="mt-4">
            <div className="flex items-center justify-between text-xs text-slate-600 mb-2">
              <span>{status?.progress?.message || "Processing..."}</span>
              <span className="font-medium">{progress}%</span>
            </div>
            <div className="h-2 w-full rounded-full bg-slate-200 overflow-hidden">
              <div
                className="h-full bg-blue-500 transition-all duration-500 ease-out"
                style={{ width: `${progress}%` }}
              />
            </div>
            {/* Step Info */}
            {status?.progress?.current_step && (
              <p className="mt-2 text-xs text-slate-500">
                Step: {status.progress.current_step.replace(/_/g, " ")}
              </p>
            )}
          </div>
        )}

        {/* Complete Status */}
        {currentStatus === "complete" && (
          <div className="mt-4 rounded-md bg-green-50 p-3">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="h-5 w-5 text-green-600" />
              <p className="text-sm font-medium text-green-800">
                Ingestion complete!
              </p>
            </div>
          </div>
        )}

        {/* Error Status */}
        {(currentStatus === "error" || isError) && (
          <div className="mt-4 rounded-md bg-red-50 p-3">
            <div className="flex items-start gap-2">
              <AlertCircle className="h-5 w-5 text-red-600 flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-sm font-medium text-red-800">
                  Ingestion failed
                </p>
                {status?.error && (
                  <p className="mt-1 text-xs text-red-700">{status.error}</p>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Pending Status */}
        {currentStatus === "pending" && (
          <div className="mt-4 rounded-md bg-blue-50 p-3">
            <div className="flex items-center gap-2">
              <Loader2 className="h-5 w-5 text-blue-600 animate-spin" />
              <p className="text-sm text-blue-800">
                Waiting to start...
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

