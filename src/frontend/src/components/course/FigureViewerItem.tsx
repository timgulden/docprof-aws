import { useState, useEffect, useRef, useCallback } from "react";
import { ZoomIn, ZoomOut, RotateCw } from "lucide-react";

// Component for individual figure viewer item with zoom
interface FigureViewerItemProps {
  figure: {
    figure_id: string;
    chunk_id: string;
    caption: string;
    description: string;
    page: number;
    book_id: string;
    chapter_number?: number;
    similarity: number;
    explanation?: string;
  };
  imageUrl: string;
}

export const FigureViewerItem = ({ figure, imageUrl }: FigureViewerItemProps) => {
  const [zoom, setZoom] = useState(1.0);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isPanning, setIsPanning] = useState(false);
  const [panStart, setPanStart] = useState({ x: 0, y: 0 });
  const [imageLoaded, setImageLoaded] = useState(false);
  const [imageError, setImageError] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const imageRef = useRef<HTMLImageElement>(null);
  
  // Preload image when component mounts
  useEffect(() => {
    if (!imageLoaded && !imageError) {
      const img = new Image();
      img.onload = () => {
        setImageLoaded(true);
      };
      img.onerror = () => {
        setImageError(true);
      };
      img.src = imageUrl;
    }
  }, [imageUrl, imageLoaded, imageError]);
  
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
    if (e.button !== 0 || zoom <= 1.0) return;
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
    
    setPan((prevPan) => {
      const newPan = {
        x: prevPan.x + deltaX,
        y: prevPan.y + deltaY,
      };
      
      // Apply constraints
      const container = containerRef.current;
      const img = imageRef.current;
      if (container && img && zoom > 1.0) {
        const containerWidth = container.offsetWidth;
        const containerHeight = container.offsetHeight;
        const scaledWidth = img.naturalWidth * zoom;
        const scaledHeight = img.naturalHeight * zoom;
        
        const excessWidth = scaledWidth - containerWidth;
        const excessHeight = scaledHeight - containerHeight;
        
        const maxPanX = excessWidth > 0 ? excessWidth / 2 : 0;
        const maxPanY = excessHeight > 0 ? excessHeight / 2 : 0;
        
        return {
          x: Math.max(-maxPanX, Math.min(maxPanX, newPan.x)),
          y: Math.max(-maxPanY, Math.min(maxPanY, newPan.y)),
        };
      }
      return newPan;
    });
    
    setPanStart({ x: e.clientX, y: e.clientY });
  }, [isPanning, panStart, zoom]);

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
  
  return (
    <figure id={`figure-${figure.figure_id}`} className="rounded-md border bg-white shadow-sm scroll-mt-4">
      {/* Zoom Controls Header */}
      <div className="flex items-center justify-between border-b bg-slate-50 px-3 py-2">
        <span className="text-xs font-medium text-slate-700">Figure Controls</span>
        <div className="flex items-center space-x-1">
          <button
            onClick={handleZoomOut}
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
            onClick={handleZoomIn}
            disabled={zoom >= 3.0}
            className="flex items-center rounded px-1.5 py-0.5 text-xs text-slate-600 hover:bg-slate-200 disabled:opacity-50 disabled:cursor-not-allowed"
            title="Zoom In (Ctrl/Cmd + Scroll)"
          >
            <ZoomIn size={14} />
          </button>
          <button
            onClick={handleZoomReset}
            className="flex items-center rounded px-1.5 py-0.5 text-xs text-slate-600 hover:bg-slate-200"
            title="Reset Zoom"
          >
            <RotateCw size={12} />
          </button>
        </div>
      </div>
      
      <div 
        ref={containerRef}
        className="relative overflow-hidden"
        style={{ 
          cursor: isPanning ? 'grabbing' : (zoom > 1.0 ? 'grab' : 'default'),
          minHeight: '200px',
        }}
        onMouseDown={handleMouseDown}
        onWheel={handleWheel}
      >
        <div 
          className="flex items-center justify-center relative"
          style={{
            transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
            transformOrigin: 'center center',
            minHeight: imageLoaded ? 'auto' : '300px',
          }}
        >
          {/* Loading skeleton */}
          {!imageLoaded && !imageError && (
            <div className="absolute inset-0 flex items-center justify-center bg-slate-100 animate-pulse">
              <div className="text-slate-400 text-sm">Loading figure...</div>
            </div>
          )}
          
          {/* Error state */}
          {imageError && (
            <div className="p-4 text-red-600 text-sm text-center">
              Failed to load figure image. Please try refreshing.
            </div>
          )}
          
          {/* Actual image */}
          <img
            ref={imageRef}
            src={imageUrl}
            alt={figure.caption || "Figure"}
            className={`h-auto w-full object-contain transition-opacity duration-300 ${
              imageLoaded ? 'opacity-100' : 'opacity-0'
            }`}
            loading="eager"
            decoding="async"
            onError={(e) => {
              const img = e.target as HTMLImageElement;
              console.error(`Failed to load figure image: ${imageUrl}`, {
                figure,
                naturalWidth: img.naturalWidth,
                naturalHeight: img.naturalHeight,
                src: img.src
              });
              setImageError(true);
              setImageLoaded(false);
            }}
            onLoad={(e) => {
              const img = e.target as HTMLImageElement;
              console.log(`Successfully loaded figure image: ${imageUrl}`, {
                naturalWidth: img.naturalWidth,
                naturalHeight: img.naturalHeight
              });
              setImageLoaded(true);
              setImageError(false);
            }}
            draggable={false}
          />
        </div>
        {zoom > 1.0 && (
          <div className="absolute bottom-2 left-1/2 transform -translate-x-1/2 bg-black/70 text-white text-xs px-2 py-1 rounded pointer-events-none">
            Click and drag to pan
          </div>
        )}
      </div>
      <figcaption className="px-4 py-3 text-sm text-slate-700 border-t">
        <strong className="font-semibold">{figure.caption || "Figure"}</strong>
        {figure.explanation && (
          <div className="mt-3 pt-3 border-t border-slate-200">
            <p className="text-xs text-slate-600 leading-relaxed italic">
              {figure.explanation}
            </p>
          </div>
        )}
      </figcaption>
    </figure>
  );
};

