/**
 * Empty state component for PDF viewer when no PDF is selected.
 * Shows a helpful message and instructions.
 */
export const PDFViewerEmpty = () => {
  return (
    <div className="flex h-full w-full flex-col items-center justify-center bg-slate-50 p-8">
      <div className="max-w-md text-center">
        <div className="mb-4 text-slate-400">
          <svg
            className="mx-auto h-16 w-16"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1.5}
              d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
            />
          </svg>
        </div>
        <h3 className="mb-2 text-lg font-semibold text-slate-900">PDF Viewer</h3>
        <p className="text-sm text-slate-600">
          Click on a citation <span className="mx-1 inline-flex items-center rounded bg-blue-100 px-1.5 py-0.5 text-xs font-medium text-blue-800">[1]</span> in a message to view the source document.
        </p>
      </div>
    </div>
  );
};

