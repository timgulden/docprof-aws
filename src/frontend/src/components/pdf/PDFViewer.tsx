import { useState, useEffect, useCallback, useRef } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import { X, ChevronLeft, ChevronRight, Download, ZoomIn, ZoomOut, RotateCw } from "lucide-react";

import { fetchBookPDF } from "../../api/books";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";

// Configure PDF.js worker - must be set before any PDF operations
// Using unpkg CDN for reliability
if (typeof window !== "undefined") {
  const pdfjsVersion = pdfjs.version || "5.4.394";
  pdfjs.GlobalWorkerOptions.workerSrc = `https://unpkg.com/pdfjs-dist@${pdfjsVersion}/build/pdf.worker.min.mjs`;
}

interface PDFViewerProps {
  bookId: string;
  initialPage?: number;
  onClose: () => void;
  bookTitle?: string;
}

export const PDFViewer = ({ bookId, initialPage = 1, onClose, bookTitle }: PDFViewerProps) => {
  console.log('[PDFViewer] Component initialized with bookId:', bookId, 'bookTitle:', bookTitle);
  
  const [numPages, setNumPages] = useState<number | null>(null);
  const [pageNumber, setPageNumber] = useState(initialPage);
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [pdfBlob, setPdfBlob] = useState<Blob | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pageWidth, setPageWidth] = useState(600);
  const containerRef = useRef<HTMLDivElement>(null);
  
  // Zoom and pan state
  const [zoom, setZoom] = useState(1.0);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isPanning, setIsPanning] = useState(false);
  const [panStart, setPanStart] = useState({ x: 0, y: 0 });
  const pageContainerRef = useRef<HTMLDivElement>(null);

  // In-document text search state
  const [searchInput, setSearchInput] = useState("");
  const [matches, setMatches] = useState<HTMLElement[]>([]);
  const [currentMatchIndex, setCurrentMatchIndex] = useState<number | null>(null);
  // Use ref to track matches to avoid circular dependencies in callbacks
  const matchesRef = useRef<HTMLElement[]>([]);
  // Bump this when the page's text layer re-renders so search runs after DOM is ready
  const [renderVersion, setRenderVersion] = useState(0);
  
  // Verify worker is configured
  useEffect(() => {
    if (!pdfjs.GlobalWorkerOptions.workerSrc) {
      const pdfjsVersion = pdfjs.version || "5.4.394";
      pdfjs.GlobalWorkerOptions.workerSrc = `https://unpkg.com/pdfjs-dist@${pdfjsVersion}/build/pdf.worker.min.mjs`;
      console.warn("[PDFViewer] Worker was not configured, setting it now");
    }
  }, []);

  useEffect(() => {
    const loadPDF = async () => {
      try {
        setLoading(true);
        setError(null);
        const result = await fetchBookPDF(bookId);
        const { url } = result;
        setPdfUrl(url);
        setPdfBlob(result.blob || null);
        setLoading(false);
      } catch (err) {
        console.error("[PDFViewer] Failed to load PDF:", err);
        const errorMessage = err instanceof Error ? err.message : "Failed to load PDF";
        setError(errorMessage);
        setLoading(false);
      }
    };

    loadPDF();

    return () => {
      // Cleanup object URL when component unmounts
      if (pdfUrl) {
        URL.revokeObjectURL(pdfUrl);
      }
    };
  }, [bookId]);

  useEffect(() => {
    setPageNumber(initialPage);
  }, [initialPage]);

  // Reset pan when page changes
  useEffect(() => {
    setPan({ x: 0, y: 0 });
  }, [pageNumber]);

  const onDocumentLoadSuccess = useCallback(({ numPages: pages }: { numPages: number }) => {
    setNumPages(pages);
    setLoading(false);
    setError(null);
    if (pageNumber > pages) {
      setPageNumber(pages);
    }
  }, [pageNumber]);
  
  const onDocumentLoadError = useCallback((error: Error) => {
    console.error("[PDFViewer] Failed to load PDF document:", error);
    const errorMessage = error.message || "Unknown error";
    setError(`Failed to load PDF document: ${errorMessage}`);
    setLoading(false);
  }, []);

  const goToPrevPage = () => {
    setPageNumber((prev) => Math.max(1, prev - 1));
  };

  const goToNextPage = () => {
    setPageNumber((prev) => Math.min(numPages || 1, prev + 1));
  };

  const handleDownload = async () => {
    if (!pdfUrl) return;
    const link = document.createElement("a");
    link.href = pdfUrl;
    link.download = `${bookTitle || "book"}.pdf`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  // Zoom controls
  const handleZoomIn = () => {
    setZoom((prev) => Math.min(prev + 0.25, 3.0));
  };

  const handleZoomOut = () => {
    setZoom((prev) => Math.max(prev - 0.25, 0.5));
  };

  const handleZoomReset = () => {
    setZoom(1.0);
    setPan({ x: 0, y: 0 });
  };

  // Pan handlers
  const handleMouseDown = (e: React.MouseEvent) => {
    if (e.button !== 0 || zoom <= 1.0) return; // Only left mouse button, and only when zoomed
    e.preventDefault();
    e.stopPropagation();
    setIsPanning(true);
    setPanStart({ x: e.clientX, y: e.clientY });
  };

  const handleMouseMove = useCallback((e: MouseEvent) => {
    if (!isPanning) return;
    e.preventDefault();
    e.stopPropagation();
    
    const deltaX = e.clientX - panStart.x;
    const deltaY = e.clientY - panStart.y;
    
    // Calculate new pan position (in screen coordinates)
    setPan((prevPan) => {
      const newPan = {
        x: prevPan.x + deltaX,
        y: prevPan.y + deltaY,
      };
      
      // Apply constraints to allow full access to all edges when zoomed
      const container = pageContainerRef.current;
      if (container && zoom > 1.0) {
        const containerWidth = container.offsetWidth;
        const containerHeight = container.offsetHeight;
        const scaledWidth = pageWidth * zoom;
        // Get actual page height from the rendered page if possible, otherwise estimate
        const scaledHeight = (pageWidth * 1.414) * zoom; // Approximate page height (A4 ratio)
        
        // Calculate how much the scaled content extends beyond the container
        // This determines how far we can pan to see all edges
        const excessWidth = scaledWidth - containerWidth;
        const excessHeight = scaledHeight - containerHeight;
        
        // Allow panning to see all edges - pan can move by half the excess in each direction
        const maxPanX = excessWidth > 0 ? excessWidth / 2 : 0;
        const maxPanY = excessHeight > 0 ? excessHeight / 2 : 0;
        
        // Clamp pan values to allow full edge access
        return {
          x: Math.max(-maxPanX, Math.min(maxPanX, newPan.x)),
          y: Math.max(-maxPanY, Math.min(maxPanY, newPan.y)),
        };
      }
      // When not zoomed, reset pan
      return { x: 0, y: 0 };
    });
    
    // Update pan start for next move
    setPanStart({ x: e.clientX, y: e.clientY });
  }, [isPanning, panStart, pageWidth, zoom]);

  const handleMouseUp = useCallback(() => {
    setIsPanning(false);
  }, []);

  // Attach global mouse event listeners for panning
  useEffect(() => {
    if (isPanning) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = 'grabbing';
      document.body.style.userSelect = 'none';
      return () => {
        document.removeEventListener('mousemove', handleMouseMove);
        document.removeEventListener('mouseup', handleMouseUp);
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
      };
    }
  }, [isPanning, handleMouseMove, handleMouseUp]);

  // Handle wheel zoom
  const handleWheel = (e: React.WheelEvent) => {
    if (e.ctrlKey || e.metaKey) {
      e.preventDefault();
      const delta = e.deltaY > 0 ? -0.1 : 0.1;
      setZoom((prev) => Math.max(0.5, Math.min(3.0, prev + delta)));
    }
  };

  // Update page width based on actual container width
  useEffect(() => {
    const updateWidth = () => {
      if (containerRef.current) {
        // Use actual container width minus padding (80px total: 40px each side)
        const containerWidth = containerRef.current.offsetWidth - 80;
        // Keep page width reasonable (between 400 and container width)
        setPageWidth(Math.max(400, Math.min(containerWidth, 800)));
      }
    };

    updateWidth();
    window.addEventListener("resize", updateWidth);
    
    // Use ResizeObserver for container size changes
    const resizeObserver = new ResizeObserver(updateWidth);
    if (containerRef.current) {
      resizeObserver.observe(containerRef.current);
    }
    
    return () => {
      window.removeEventListener("resize", updateWidth);
      resizeObserver.disconnect();
    };
  }, []);

  // Clear all existing search highlights
  const clearSearchHighlights = useCallback(() => {
    // Use ref to avoid circular dependency
    matchesRef.current.forEach((el) => {
      try {
        el.style.backgroundColor = "";
        el.style.outline = "";
        el.style.outlineOffset = "";
      } catch {
        // Ignore DOM errors on stale elements
      }
    });
    matchesRef.current = [];
  }, []);

  // Perform search on the current page's text layer
  const performSearch = useCallback(() => {
    const term = searchInput.trim().toLowerCase();

    // Clear previous highlights
    clearSearchHighlights();
    setMatches([]);
    setCurrentMatchIndex(null);

    if (!term) {
      return;
    }

    const container = pageContainerRef.current;
    if (!container) return;

    // react-pdf renders text in spans inside the text layer
    const spanNodes = container.querySelectorAll<HTMLElement>(
      ".react-pdf__Page__textContent span"
    );
    const newMatches: HTMLElement[] = [];

    spanNodes.forEach((node) => {
      const text = (node.textContent || "").toLowerCase();
      if (text.includes(term)) {
        try {
          // Base highlight style
          node.style.backgroundColor = "rgba(250, 204, 21, 0.5)"; // tailwind yellow-300-ish
        } catch {
          // Ignore style errors
        }
        newMatches.push(node);
      }
    });

    if (newMatches.length === 0) {
      setMatches([]);
      matchesRef.current = [];
      setCurrentMatchIndex(null);
      return;
    }

    setMatches(newMatches);
    matchesRef.current = newMatches;
    // Focus first match by default
    setCurrentMatchIndex(0);

    try {
      const el = newMatches[0];
      // Emphasize active match
      el.style.outline = "2px solid #facc15"; // yellow-400
      el.style.outlineOffset = "2px";

      // Ensure the first match is visible within the scrollable container
      const container = pageContainerRef.current;
      if (container) {
        el.scrollIntoView({
          behavior: "smooth",
          block: "center",
          inline: "nearest",
        });
      }
    } catch {
      // Ignore scroll/style errors
    }
  }, [clearSearchHighlights, searchInput]);

  // Re-run search when search term or page changes
  useEffect(() => {
    if (!searchInput.trim()) {
      clearSearchHighlights();
      setMatches([]);
      matchesRef.current = [];
      setCurrentMatchIndex(null);
      return;
    }
    // Run search after the current page render completes
    // Use setTimeout to ensure text layer is rendered
    const timeoutId = setTimeout(() => {
      performSearch();
    }, 100);
    return () => clearTimeout(timeoutId);
  }, [searchInput, pageNumber, renderVersion, performSearch, clearSearchHighlights]);

  const focusMatchAtIndex = useCallback(
    (index: number) => {
      // Use ref to avoid dependency on matches state
      const currentMatches = matchesRef.current;
      if (!currentMatches.length) return;
      const safeIndex = ((index % currentMatches.length) + currentMatches.length) % currentMatches.length;
      const el = currentMatches[safeIndex];
      if (!el) return;
      try {
        // Clear previous active outlines
        currentMatches.forEach((m) => {
          m.style.outline = "";
          m.style.outlineOffset = "";
        });
        el.style.outline = "2px solid #facc15";
        el.style.outlineOffset = "2px";

        // Scroll the active match into view within the scrollable container
        const container = pageContainerRef.current;
        if (container) {
          el.scrollIntoView({
            behavior: "smooth",
            block: "center",
            inline: "nearest",
          });
        }

        setCurrentMatchIndex(safeIndex);
      } catch {
        // Ignore DOM errors
      }
    },
    []
  );

  const handleNextMatch = () => {
    if (!matches.length) return;
    const nextIndex =
      currentMatchIndex === null ? 0 : (currentMatchIndex + 1) % matches.length;
    focusMatchAtIndex(nextIndex);
  };

  const handlePrevMatch = () => {
    if (!matches.length) return;
    const prevIndex =
      currentMatchIndex === null
        ? matches.length - 1
        : (currentMatchIndex - 1 + matches.length) % matches.length;
    focusMatchAtIndex(prevIndex);
  };

  // Debug: Log render state
  console.log('[PDFViewer] Render check - loading:', loading, 'error:', error, 'pdfUrl:', !!pdfUrl, 'zoom:', zoom);

  if (loading) {
    console.log('[PDFViewer] Returning loading state');
    return (
      <div className="flex h-full w-full items-center justify-center bg-slate-50">
        <div className="text-slate-600">Loading PDF...</div>
      </div>
    );
  }

  if (error || !pdfUrl) {
    console.log('[PDFViewer] Returning error state');
    return (
      <div className="flex h-full w-full flex-col items-center justify-center bg-slate-50 p-4">
        <div className="mb-4 text-red-600 text-center">
          {error || "PDF not available"}
        </div>
        <div className="mb-2 text-xs text-slate-500 text-center">
          Book ID: {bookId}
        </div>
        <button
          onClick={onClose}
          className="rounded-md bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700"
        >
          Close
        </button>
      </div>
    );
  }

  console.log('[PDFViewer] Rendering main view with zoom controls');

  return (
    <div ref={containerRef} className="flex w-full flex-col bg-slate-50 overflow-hidden">
      {/* Header with Zoom Controls - Always visible */}
      <div className="flex items-center justify-between border-b bg-white px-4 py-2 shadow-sm flex-shrink-0 z-20" style={{ minHeight: '48px' }}>
        <div className="flex items-center space-x-4 flex-1 min-w-0">
          <h2 className="text-sm font-semibold text-slate-900 truncate">
            {bookTitle || "PDF Viewer"}
          </h2>
          {numPages && (
            <span className="text-xs text-slate-600 whitespace-nowrap">
              Page {pageNumber} of {numPages}
            </span>
          )}
        </div>
        <div className="flex items-center space-x-2" style={{ visibility: 'visible', display: 'flex' }}>
          {/* Zoom controls - matching figure viewer style */}
          <div className="flex items-center space-x-1 border-r border-slate-300 pr-2 mr-2">
            <button
              onClick={() => { console.log('Zoom Out clicked'); handleZoomOut(); }}
              disabled={zoom <= 0.5}
              className="flex items-center rounded px-1.5 py-0.5 text-xs text-slate-600 hover:bg-slate-200 disabled:opacity-50 disabled:cursor-not-allowed"
              title="Zoom Out (Ctrl/Cmd + Scroll)"
            >
              <ZoomOut size={14} />
            </button>
            <span className="text-xs text-slate-600 min-w-[2.5rem] text-center font-medium">
              {Math.round(zoom * 100)}%
            </span>
            <button
              onClick={() => { console.log('Zoom In clicked'); handleZoomIn(); }}
              disabled={zoom >= 3.0}
              className="flex items-center rounded px-1.5 py-0.5 text-xs text-slate-600 hover:bg-slate-200 disabled:opacity-50 disabled:cursor-not-allowed"
              title="Zoom In (Ctrl/Cmd + Scroll)"
            >
              <ZoomIn size={14} />
            </button>
            <button
              onClick={() => { console.log('Reset clicked'); handleZoomReset(); }}
              className="flex items-center rounded px-1.5 py-0.5 text-xs text-slate-600 hover:bg-slate-200"
              title="Reset Zoom"
            >
              <RotateCw size={12} />
            </button>
          </div>
          <button
            onClick={handleDownload}
            className="flex items-center space-x-1 rounded-md px-2 py-1 text-xs text-slate-600 hover:bg-slate-100"
            title="Download PDF"
          >
            <Download size={16} />
          </button>
          <button
            onClick={onClose}
            className="flex items-center space-x-1 rounded-md px-2 py-1 text-xs text-slate-600 hover:bg-slate-100"
            title="Close PDF Viewer"
          >
            <X size={16} />
          </button>
        </div>
      </div>

      {/* Navigation + Search */}
      <div className="flex items-center justify-between border-b bg-white px-3 py-1.5 flex-shrink-0 z-10 gap-2">
        {/* Left: Prev */}
        <div className="flex items-center">
          <button
            onClick={goToPrevPage}
            disabled={pageNumber <= 1}
            className="flex items-center space-x-1 rounded-md px-2 py-1 text-xs text-slate-600 transition-colors hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <ChevronLeft size={16} />
            <span>Prev</span>
          </button>
        </div>

        {/* Center: Search controls */}
        <div className="flex items-center space-x-1 flex-1 justify-center">
          <input
            type="text"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            placeholder="Search"
            className="w-40 rounded-md border border-slate-300 px-2 py-0.5 text-xs text-slate-700 focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
          />
          <button
            onClick={handlePrevMatch}
            disabled={!matches.length}
            className="rounded px-1.5 py-0.5 text-xs text-slate-600 hover:bg-slate-100 disabled:opacity-40 disabled:cursor-not-allowed"
            title="Previous match"
          >
            Prev
          </button>
          <button
            onClick={handleNextMatch}
            disabled={!matches.length}
            className="rounded px-1.5 py-0.5 text-xs text-slate-600 hover:bg-slate-100 disabled:opacity-40 disabled:cursor-not-allowed"
            title="Next match"
          >
            Next
          </button>
          <span className="text-xs text-slate-500 min-w-[3rem] text-right">
            {matches.length
              ? `${(currentMatchIndex ?? 0) + 1}/${matches.length}`
              : "0/0"}
          </span>
        </div>

        {/* Right: Page selector + Next */}
        <div className="flex items-center space-x-2">
          <input
            type="number"
            min={1}
            max={numPages || 1}
            value={pageNumber}
            onChange={(e) => {
              const page = parseInt(e.target.value, 10);
              if (page >= 1 && page <= (numPages || 1)) {
                setPageNumber(page);
              }
            }}
            className="w-14 rounded-md border border-slate-300 px-1 py-0.5 text-center text-xs"
          />
          <span className="text-xs text-slate-600">of {numPages || "?"}</span>
          <button
            onClick={goToNextPage}
            disabled={pageNumber >= (numPages || 1)}
            className="flex items-center space-x-1 rounded-md px-2 py-1 text-xs text-slate-600 transition-colors hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <span>Next</span>
            <ChevronRight size={16} />
          </button>
        </div>
      </div>

      {/* PDF Document */}
      <div
        className="flex-1 relative"
        onWheel={handleWheel}
        style={{ overflow: "hidden", touchAction: "none" }}
      >
        <div
          ref={pageContainerRef}
          className="h-full w-full overflow-auto flex justify-center"
          style={{
            cursor: isPanning ? "grabbing" : zoom > 1.0 ? "grab" : "default",
            userSelect: "none",
          }}
          onMouseDown={handleMouseDown}
          onDragStart={(e) => e.preventDefault()}
        >
          <div
            style={{
              transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
              transformOrigin: "top center",
              width: `${pageWidth}px`,
            }}
          >
            {error ? (
              <div className="text-red-600 p-4">
                <p className="font-medium">Failed to load PDF document</p>
                <p className="text-xs mt-2">{error}</p>
              </div>
            ) : pdfUrl ? (
              <Document 
                key={`doc-${bookId}-${pdfUrl}`}
                file={pdfUrl}
                onLoadSuccess={onDocumentLoadSuccess}
                onLoadError={(error) => {
                  onDocumentLoadError(error || new Error("Unknown PDF loading error"));
                }}
                onSourceError={(error) => {
                  console.error("[PDFViewer] Failed to load PDF source:", error);
                  setError(`Failed to load PDF source: ${error?.message || "Unknown error"}`);
                  setLoading(false);
                }}
                loading={<div className="text-slate-600">Loading PDF document...</div>}
                error={
                  <div className="text-red-600 p-4">
                    <p className="font-medium">Failed to load PDF document</p>
                    <p className="text-xs mt-2">Please check the console for details</p>
                    {error && <p className="text-xs mt-1">{error}</p>}
                  </div>
                }
              >
                <Page
                  pageNumber={pageNumber}
                  width={pageWidth}
                  renderTextLayer
                  renderAnnotationLayer
                  onLoadError={(error) => {
                    console.error("[PDFViewer] Failed to load page:", error);
                    setError(`Failed to load page ${pageNumber}: ${error.message || "Unknown error"}`);
                  }}
                  onRenderSuccess={() => {
                    // Text layer is ready; allow searches to see spans
                    setRenderVersion((v) => v + 1);
                  }}
                  loading={<div className="text-slate-600">Loading page {pageNumber}...</div>}
                  error={
                    <div className="text-red-600 p-4">
                      Failed to load page {pageNumber}. Please try again.
                    </div>
                  }
                />
              </Document>
            ) : loading ? (
              <div className="text-slate-600">Loading PDF...</div>
            ) : null}
          </div>
        </div>
        {/* Panning hint */}
        {zoom > 1.0 && (
          <div className="absolute bottom-4 left-1/2 transform -translate-x-1/2 bg-black/70 text-white text-xs px-3 py-1.5 rounded-md flex items-center gap-2 pointer-events-none">
            <span>Click and drag to pan</span>
          </div>
        )}
      </div>
    </div>
  );
};

