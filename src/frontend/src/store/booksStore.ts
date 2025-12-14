import { create } from "zustand";
import { persist } from "zustand/middleware";

interface BooksStore {
  selectedBookIds: string[];
  setSelectedBookIds: (bookIds: string[]) => void;
  toggleBookSelection: (bookId: string) => void;
  selectAllBooks: (bookIds: string[]) => void;
  deselectAllBooks: () => void;
}

/**
 * Store for managing user's selected books
 * Selected books are persisted to localStorage and remain active across sessions
 */
export const useBooksStore = create<BooksStore>()(
  persist(
    (set) => ({
      selectedBookIds: [],

      setSelectedBookIds: (bookIds: string[]) => {
        set({ selectedBookIds: bookIds });
      },

      toggleBookSelection: (bookId: string) => {
        set((state) => {
          const isSelected = state.selectedBookIds.includes(bookId);
          if (isSelected) {
            // Prevent deselecting the last book - must have at least 1 selected
            if (state.selectedBookIds.length <= 1) {
              return state; // No change
            }
            return { selectedBookIds: state.selectedBookIds.filter((id) => id !== bookId) };
          } else {
            return { selectedBookIds: [...state.selectedBookIds, bookId] };
          }
        });
      },

      selectAllBooks: (bookIds: string[]) => {
        set({ selectedBookIds: bookIds });
      },

      deselectAllBooks: () => {
        set({ selectedBookIds: [] });
      },
    }),
    {
      name: "books-selection", // localStorage key
    }
  )
);

