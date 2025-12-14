import { apiClient } from "./client";
import { cachePDF, getCachedPDF, getCachedPDFUrl, isCached } from "../utils/pdfCache";
import type { 
  Book, 
  BookCoverBatchRequest, 
  CoverInfo,
  UploadInitialResponse,
  AnalyzeBookResponse,
  StartIngestionRequest,
  StartIngestionResponse,
  IngestionStatusResponse,
} from "../types/api";

/**
 * Fetch all books from the database
 * Backend returns an array of books directly
 */
export const fetchAllBooks = async (): Promise<Book[]> => {
  const response = await apiClient.get<Book[]>("/books");
  return response.data;
};

/**
 * Get the cover image URL for a specific book
 */
export const getBookCoverUrl = (bookId: string): string => {
  const baseUrl = apiClient.defaults.baseURL || "";
  return `${baseUrl}/books/${bookId}/cover`;
};

/**
 * Batch fetch cover URLs for multiple books
 * Backend returns an array of CoverInfo objects
 */
export const fetchBookCovers = async (bookIds: string[]): Promise<CoverInfo[]> => {
  const request: BookCoverBatchRequest = { book_ids: bookIds };
  const response = await apiClient.post<CoverInfo[]>("/books/covers", request);
  return response.data;
};

/**
 * Delete a book from the database
 * TODO: Implement backend endpoint
 */
export const deleteBook = async (bookId: string): Promise<void> => {
  await apiClient.delete(`/books/${bookId}`);
};

/**
 * Smart Book Upload - Phase 1: Get pre-signed S3 URL for direct upload
 * Returns upload URL and book_id - frontend uploads directly to S3
 */
export const uploadInitial = async (): Promise<UploadInitialResponse> => {
  const response = await apiClient.post<UploadInitialResponse>("/books/upload-initial", {});
  return response.data;
};

/**
 * Upload file directly to S3 using pre-signed POST
 */
export const uploadToS3 = async (
  file: File,
  uploadUrl: string,
  uploadFields: Record<string, string>
): Promise<void> => {
  const formData = new FormData();
  
  // Add all fields from pre-signed POST (must be in order)
  // Note: The 'key' field in uploadFields contains the S3 key, not the file field name
  Object.entries(uploadFields).forEach(([key, value]) => {
    formData.append(key, value);
  });
  
  // Add the file - S3 pre-signed POST expects the file field to match the 'key' field value
  // But actually, we just append it as 'file' - S3 will handle it based on the key in uploadFields
  formData.append("file", file);
  
  // Upload directly to S3 (not through API Gateway)
  const response = await fetch(uploadUrl, {
    method: "POST",
    body: formData,
  });
  
  if (!response.ok) {
    throw new Error(`S3 upload failed: ${response.statusText}`);
  }
};

/**
 * Analyze book from S3 - extracts cover and metadata
 */
export const analyzeBook = async (bookId: string): Promise<AnalyzeBookResponse> => {
  const response = await apiClient.post<AnalyzeBookResponse>(`/books/${bookId}/analyze`, {});
  return response.data;
};

/**
 * Smart Book Upload - Phase 2: Start background ingestion
 * Launches the full ingestion pipeline in the background
 */
export const startIngestion = async (
  bookId: string, 
  metadata: StartIngestionRequest
): Promise<StartIngestionResponse> => {
  const response = await apiClient.post<StartIngestionResponse>(
    `/books/${bookId}/start-ingestion`,
    metadata
  );
  
  return response.data;
};

/**
 * Get real-time ingestion status for a book
 * Poll this endpoint every 2-3 seconds while status is 'processing'
 */
export const getIngestionStatus = async (bookId: string): Promise<IngestionStatusResponse> => {
  const response = await apiClient.get<IngestionStatusResponse>(
    `/books/${bookId}/ingestion-status`
  );
  
  return response.data;
};

/**
 * Fetch PDF for a book, with caching support
 */
export const fetchBookPDF = async (bookId: string): Promise<{ url: string; blob?: Blob; cached: boolean }> => {
  // Check if cached
  const cached = await isCached(bookId);
  if (cached) {
    const cachedBlob = await getCachedPDF(bookId);
    if (cachedBlob) {
      const cachedUrl = URL.createObjectURL(cachedBlob);
      return { url: cachedUrl, blob: cachedBlob, cached: true };
    }
  }

  try {
    // Fetch from API
    const response = await apiClient.get(`/books/${bookId}/pdf`, {
      responseType: "blob",
    });

    // Verify it's actually a PDF
    if (!(response.data instanceof Blob)) {
      throw new Error("Response is not a Blob");
    }

    const pdfBlob = response.data;
    // Ensure correct MIME type
    if (!pdfBlob.type || pdfBlob.type !== "application/pdf") {
      // Create a new blob with correct type
      const correctedBlob = new Blob([pdfBlob], { type: "application/pdf" });
      const apiUrl = `/api/books/${bookId}/pdf`;
      await cachePDF(bookId, correctedBlob, apiUrl);
      const url = URL.createObjectURL(correctedBlob);
      return { url, blob: correctedBlob, cached: false };
    }

    const apiUrl = `/api/books/${bookId}/pdf`;

    // Cache the PDF
    await cachePDF(bookId, pdfBlob, apiUrl);

    // Return object URL and blob
    const url = URL.createObjectURL(pdfBlob);
    return { url, blob: pdfBlob, cached: false };
  } catch (error: any) {
    console.error("[fetchBookPDF] Error fetching PDF:", error);
    if (error.response) {
      // Try to parse error response
      const errorText = await error.response.data?.text?.() || "Unknown error";
      console.error("[fetchBookPDF] Error response:", errorText);
    }
    throw error;
  }
};

