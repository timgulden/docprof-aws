import { useState, useRef, useEffect } from "react";
import { X, Upload, Loader2, AlertCircle, CheckCircle, BookOpen, Sparkles } from "lucide-react";
import { uploadInitial, uploadToS3, analyzeBook, startIngestion } from "../../api/books";
import { apiClient } from "../../api/client";
import type { ExtractedMetadata } from "../../types/api";

interface UploadBookModalProps {
  isOpen: boolean;
  onClose: () => void;
  onUploadSuccess: () => void;
}

type UploadPhase = "select" | "analyzing" | "review" | "starting" | "success" | "error";

export const UploadBookModal = ({ isOpen, onClose, onUploadSuccess }: UploadBookModalProps) => {
  const [phase, setPhase] = useState<UploadPhase>("select");
  const [file, setFile] = useState<File | null>(null);
  const [bookId, setBookId] = useState<string>("");
  const [coverUrl, setCoverUrl] = useState<string>("");
  const [extractedMetadata, setExtractedMetadata] = useState<ExtractedMetadata | null>(null);
  
  // Editable metadata fields
  const [title, setTitle] = useState("");
  const [author, setAuthor] = useState("");
  const [edition, setEdition] = useState("");
  const [isbn, setIsbn] = useState("");
  
  const [errorMessage, setErrorMessage] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Auto-open file picker when modal opens
  useEffect(() => {
    if (isOpen && phase === "select") {
      // Small delay to ensure modal is fully rendered
      const timer = setTimeout(() => {
        fileInputRef.current?.click();
      }, 100);
      return () => clearTimeout(timer);
    }
  }, [isOpen, phase]);

  // Cleanup blob URLs when component unmounts or coverUrl changes
  useEffect(() => {
    return () => {
      // Cleanup: revoke any blob URLs when component unmounts
      if (coverUrl && coverUrl.startsWith("blob:")) {
        URL.revokeObjectURL(coverUrl);
      }
    };
  }, [coverUrl]);

  if (!isOpen) return null;

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (selectedFile) {
      if (selectedFile.type !== "application/pdf") {
        setErrorMessage("Please select a PDF file");
        setFile(null);
        return;
      }
      setFile(selectedFile);
      setErrorMessage("");
      
      // Automatically start analysis
      await handleAnalyze(selectedFile);
    }
  };

  const handleAnalyze = async (fileToAnalyze: File) => {
    if (!fileToAnalyze) return;

    setPhase("analyzing");
    setErrorMessage("");

    try {
      // Step 1: Get pre-signed S3 URL
      const uploadInfo = await uploadInitial();
      setBookId(uploadInfo.book_id);
      
      // Step 2: Upload file directly to S3
      await uploadToS3(fileToAnalyze, uploadInfo.upload_url, uploadInfo.upload_fields);
      
      // Step 3: Analyze book from S3 (extract cover and metadata)
      const result = await analyzeBook(uploadInfo.book_id);
      
      // Cover URL is now a data URL (data:image/jpeg;base64,...) from the backend
      // Convert data URL to blob URL for more reliable browser handling
      if (result.cover_url) {
        const url = result.cover_url.trim();
        if (url.startsWith("data:")) {
          // Convert data URL to blob URL for better browser compatibility
          try {
            // Parse data URL: data:image/jpeg;base64,<base64_data>
            const matches = url.match(/^data:image\/(\w+);base64,(.+)$/);
            if (matches) {
              const [, mimeType, base64Data] = matches;
              // Convert base64 to binary
              const binaryString = atob(base64Data);
              const bytes = new Uint8Array(binaryString.length);
              for (let i = 0; i < binaryString.length; i++) {
                bytes[i] = binaryString.charCodeAt(i);
              }
              // Create blob and object URL
              const blob = new Blob([bytes], { type: `image/${mimeType}` });
              const blobUrl = URL.createObjectURL(blob);
              setCoverUrl(blobUrl);
              console.debug(`Converted data URL to blob URL: ${blobUrl.substring(0, 50)}...`);
            } else {
              // If parsing fails, try using data URL directly
              console.warn("Failed to parse data URL, using as-is");
              setCoverUrl(url);
            }
          } catch (error) {
            console.error("Error converting data URL to blob:", error);
            // Fallback to data URL
            setCoverUrl(url);
          }
        } else if (url.startsWith("http://") || url.startsWith("https://")) {
          // Absolute URL - use as-is
          setCoverUrl(url);
          console.debug(`Set cover URL (absolute): ${url}`);
        } else {
          // Relative URL - construct absolute URL (legacy support)
          const baseUrl = apiClient.defaults.baseURL || "";
          const cleanUrl = url.startsWith("/") ? url : `/${url}`;
          setCoverUrl(`${baseUrl}${cleanUrl}`);
          console.debug(`Set cover URL (relative, constructed): ${baseUrl}${cleanUrl}`);
        }
      } else {
        console.warn("No cover URL in response from analyze endpoint");
        setCoverUrl("");
      }
      
      // Debug: log the full result to see what we're getting
      console.log("Analyze result:", result);
      
      if (!result.metadata) {
        console.error("No metadata in response:", result);
        setErrorMessage("Failed to extract metadata from PDF. Please fill in the fields manually.");
        setExtractedMetadata({
          title: 'Unknown',
          author: undefined,
          edition: undefined,
          isbn: undefined
        });
        setTitle('Unknown');
        setAuthor("");
        setEdition("");
        setIsbn("");
      } else {
        setExtractedMetadata(result.metadata);
        
        // Pre-fill editable fields with extracted metadata
        setTitle(result.metadata.title || "");
        setAuthor(result.metadata.author || "");
        setEdition(result.metadata.edition || "");
        setIsbn(result.metadata.isbn || "");
      }
      
      setPhase("review");
    } catch (error: any) {
      console.error("Error analyzing book:", error);
      setPhase("error");
      setErrorMessage(
        error.response?.data?.detail || 
        error.message ||
        "Failed to analyze PDF. Please try again."
      );
    }
  };

  const handleStartIngestion = async () => {
    if (!bookId) return;

    setPhase("starting");
    setErrorMessage("");

    try {
      // Phase 2: Start background ingestion
      await startIngestion(bookId, {
        title,
        author: author || undefined,
        edition: edition || undefined,
        isbn: isbn || undefined,
      });
      
      setPhase("success");
      
      // Close modal and refresh book list after a short delay
      setTimeout(() => {
        onUploadSuccess();
        handleClose();
      }, 1500);
    } catch (error: any) {
      console.error("Error starting ingestion:", error);
      setPhase("error");
      setErrorMessage(
        error.response?.data?.detail || 
        "Failed to start ingestion. Please try again."
      );
    }
  };

  const handleClose = () => {
    if (phase === "analyzing" || phase === "starting") {
      // Don't close while processing
      return;
    }
    
    // Revoke blob URL if it exists
    if (coverUrl && coverUrl.startsWith("blob:")) {
      URL.revokeObjectURL(coverUrl);
    }
    
    // Reset all state
    setPhase("select");
    setFile(null);
    setBookId("");
    setCoverUrl("");
    setExtractedMetadata(null);
    setTitle("");
    setAuthor("");
    setEdition("");
    setIsbn("");
    setErrorMessage("");
    onClose();
  };

  const getConfidenceColor = (confidence?: number) => {
    if (!confidence) return "text-slate-400";
    if (confidence >= 0.9) return "text-green-600";
    if (confidence >= 0.7) return "text-yellow-600";
    return "text-orange-600";
  };

  const getConfidenceLabel = (confidence?: number) => {
    if (!confidence) return "Unknown";
    if (confidence >= 0.9) return "High";
    if (confidence >= 0.7) return "Medium";
    return "Low";
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50 p-4">
      <div className="w-full max-w-2xl rounded-lg bg-white shadow-xl max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="sticky top-0 z-10 bg-white flex items-center justify-between border-b p-4">
          <h2 className="text-lg font-semibold text-slate-900">Upload New Book</h2>
          <button
            onClick={handleClose}
            disabled={phase === "analyzing" || phase === "starting"}
            className="rounded-md p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600 disabled:opacity-50"
          >
            <X size={20} />
          </button>
        </div>

        {/* Body */}
        <div className="p-6">
          {/* Hidden file input (auto-opens on modal open) */}
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,application/pdf"
            onChange={handleFileChange}
            className="hidden"
          />

          {/* Phase 1: File Selection (brief - just shows cancel button) */}
          {phase === "select" && (
            <div className="text-center py-8">
              <Upload className="h-16 w-16 text-slate-400 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-slate-900 mb-2">
                Select a PDF file
              </h3>
              <p className="text-sm text-slate-600 mb-4">
                Choose a textbook to upload and analyze
              </p>
              
              {errorMessage && (
                <div className="mb-4 flex items-start justify-center space-x-2 rounded-md bg-red-50 p-3 text-sm text-red-700 max-w-md mx-auto">
                  <AlertCircle className="h-5 w-5 flex-shrink-0" />
                  <span>{errorMessage}</span>
                </div>
              )}

              <div className="flex justify-center space-x-2">
                <button
                  type="button"
                  onClick={handleClose}
                  className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  onClick={() => fileInputRef.current?.click()}
                  className="flex items-center space-x-2 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
                >
                  <Upload className="h-4 w-4" />
                  <span>Choose File</span>
                </button>
              </div>
            </div>
          )}

          {/* Phase 2: Analyzing */}
          {phase === "analyzing" && (
            <div className="text-center py-8">
              <Loader2 className="h-16 w-16 animate-spin text-blue-500 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-slate-900 mb-2">
                Analyzing your book...
              </h3>
              <p className="text-sm text-slate-600 mb-4">
                Extracting cover image and metadata with Claude AI
              </p>
              <div className="space-y-2 text-xs text-slate-500">
                <p>✓ Getting upload URL</p>
                <p>✓ Uploading PDF to S3</p>
                <p>✓ Extracting cover image</p>
                <p className="animate-pulse">⋯ Analyzing first pages with AI</p>
              </div>
              <p className="text-xs text-slate-400 mt-4">
                This usually takes 10-20 seconds
              </p>
            </div>
          )}

          {/* Phase 3: Review & Edit Metadata */}
          {phase === "review" && extractedMetadata && (
            <div>
              <div className="mb-6 rounded-lg bg-blue-50 p-4 border border-blue-200">
                <div className="flex items-start gap-3">
                  <Sparkles className="h-5 w-5 text-blue-600 flex-shrink-0 mt-0.5" />
                  <div>
                    <h3 className="font-medium text-blue-900 mb-1">
                      Metadata Extracted
                    </h3>
                    <p className="text-sm text-blue-700">
                      Review and edit the information below before starting ingestion.
                    </p>
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-6 mb-6">
                {/* Cover Preview */}
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-2">
                    Cover Image
                  </label>
                  <div className="border rounded-lg overflow-hidden bg-slate-50 h-64 flex items-center justify-center">
                    {coverUrl ? (
                      <img
                        src={coverUrl}
                        alt="Book cover"
                        className="w-full h-full object-contain"
                        onError={(e) => {
                          console.error("Failed to load cover image. coverUrl:", coverUrl.substring(0, 100));
                          console.error("coverUrl type:", typeof coverUrl);
                          console.error("coverUrl starts with data:", coverUrl.startsWith("data:"));
                          console.error("Image src attribute value:", e.currentTarget.src);
                          // Hide the image on error and show a placeholder
                          e.currentTarget.style.display = "none";
                        }}
                      />
                    ) : (
                      <div className="text-center text-slate-400">
                        <BookOpen className="h-16 w-16 mx-auto mb-2" />
                        <p className="text-sm">No cover available</p>
                      </div>
                    )}
                  </div>
                </div>

                {/* Metadata Fields */}
                <div className="space-y-4">
                  {/* Title */}
                  <div>
                    <div className="flex items-center justify-between mb-1">
                      <label className="block text-sm font-medium text-slate-700">
                        Title *
                      </label>
                      <span className={`text-xs ${getConfidenceColor(extractedMetadata.confidence?.title)}`}>
                        {getConfidenceLabel(extractedMetadata.confidence?.title)} confidence
                      </span>
                    </div>
                    <input
                      type="text"
                      value={title}
                      onChange={(e) => setTitle(e.target.value)}
                      className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                    />
                  </div>

                  {/* Author */}
                  <div>
                    <div className="flex items-center justify-between mb-1">
                      <label className="block text-sm font-medium text-slate-700">
                        Author
                      </label>
                      {extractedMetadata.confidence?.author && (
                        <span className={`text-xs ${getConfidenceColor(extractedMetadata.confidence.author)}`}>
                          {getConfidenceLabel(extractedMetadata.confidence.author)} confidence
                        </span>
                      )}
                    </div>
                    <input
                      type="text"
                      value={author}
                      onChange={(e) => setAuthor(e.target.value)}
                      placeholder="Unknown"
                      className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                    />
                  </div>

                  {/* Edition */}
                  <div>
                    <div className="flex items-center justify-between mb-1">
                      <label className="block text-sm font-medium text-slate-700">
                        Edition
                      </label>
                      {extractedMetadata.confidence?.edition && (
                        <span className={`text-xs ${getConfidenceColor(extractedMetadata.confidence.edition)}`}>
                          {getConfidenceLabel(extractedMetadata.confidence.edition)} confidence
                        </span>
                      )}
                    </div>
                    <input
                      type="text"
                      value={edition}
                      onChange={(e) => setEdition(e.target.value)}
                      placeholder="Unknown"
                      className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                    />
                  </div>

                  {/* ISBN */}
                  <div>
                    <div className="flex items-center justify-between mb-1">
                      <label className="block text-sm font-medium text-slate-700">
                        ISBN
                      </label>
                      {extractedMetadata.confidence?.isbn && (
                        <span className={`text-xs ${getConfidenceColor(extractedMetadata.confidence.isbn)}`}>
                          {getConfidenceLabel(extractedMetadata.confidence.isbn)} confidence
                        </span>
                      )}
                    </div>
                    <input
                      type="text"
                      value={isbn}
                      onChange={(e) => setIsbn(e.target.value)}
                      placeholder="Unknown"
                      className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                    />
                  </div>
                </div>
              </div>

              {errorMessage && (
                <div className="mb-4 flex items-start space-x-2 rounded-md bg-red-50 p-3 text-sm text-red-700">
                  <AlertCircle className="h-5 w-5 flex-shrink-0" />
                  <span>{errorMessage}</span>
                </div>
              )}

              <div className="flex justify-end space-x-2">
                <button
                  type="button"
                  onClick={handleClose}
                  className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  onClick={handleStartIngestion}
                  disabled={!title.trim()}
                  className="flex items-center space-x-2 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <BookOpen className="h-4 w-4" />
                  <span>Start Ingestion</span>
                </button>
              </div>
            </div>
          )}

          {/* Phase 4: Starting Ingestion */}
          {phase === "starting" && (
            <div className="text-center py-8">
              <Loader2 className="h-16 w-16 animate-spin text-blue-500 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-slate-900 mb-2">
                Starting ingestion...
              </h3>
              <p className="text-sm text-slate-600">
                Your book will appear on the Sources page with live progress
              </p>
            </div>
          )}

          {/* Phase 5: Success */}
          {phase === "success" && (
            <div className="text-center py-8">
              <CheckCircle className="h-16 w-16 text-green-500 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-slate-900 mb-2">
                Book added successfully!
              </h3>
              <p className="text-sm text-slate-600">
                Ingestion has started. You can track progress on the Sources page.
              </p>
            </div>
          )}

          {/* Phase 6: Error */}
          {phase === "error" && (
            <div>
              <div className="text-center py-8">
                <AlertCircle className="h-16 w-16 text-red-500 mx-auto mb-4" />
                <h3 className="text-lg font-medium text-slate-900 mb-2">
                  Something went wrong
                </h3>
                {errorMessage && (
                  <p className="text-sm text-red-600 mb-4">{errorMessage}</p>
                )}
              </div>

              <div className="flex justify-end space-x-2">
                <button
                  onClick={handleClose}
                  className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
                >
                  Close
                </button>
                <button
                  onClick={() => setPhase("select")}
                  className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
                >
                  Try Again
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
