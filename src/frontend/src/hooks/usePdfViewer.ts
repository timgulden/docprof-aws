import { useState } from "react";
import { getCitationData } from "../utils/citations";
import type { SourceCitation } from "../types/chat";

interface PdfViewerState {
  isOpen: boolean;
  bookId: string | null;
  page: number;
  bookTitle: string | undefined;
}

/**
 * Custom hook for managing PDF viewer state.
 * Encapsulates PDF viewer state and provides functions to open/close it.
 */
export const usePdfViewer = () => {
  const [state, setState] = useState<PdfViewerState>({
    isOpen: false,
    bookId: null,
    page: 1,
    bookTitle: undefined,
  });

  const openPdf = (bookId: string, page: number, bookTitle?: string) => {
    setState({
      isOpen: true,
      bookId,
      page,
      bookTitle,
    });
  };

  const closePdf = () => {
    setState({
      isOpen: false,
      bookId: null,
      page: 1,
      bookTitle: undefined,
    });
  };

  const openPdfFromCitation = (citationId: string, sources: SourceCitation[]) => {
    const citationData = getCitationData(citationId, sources);
    if (citationData) {
      openPdf(citationData.bookId, citationData.page, citationData.bookTitle);
    }
  };

  return {
    ...state,
    openPdf,
    closePdf,
    openPdfFromCitation,
  };
};

