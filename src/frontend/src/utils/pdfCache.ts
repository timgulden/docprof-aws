/**
 * PDF Cache Service using IndexedDB
 * Stores PDF blobs for offline access and fast loading
 */

const DB_NAME = "maexpert_pdf_cache";
const STORE_NAME = "pdfs";
const DB_VERSION = 1;

const MAX_CACHE_SIZE = 500 * 1024 * 1024; // 500MB
const MAX_AGE_MS = 7 * 24 * 60 * 60 * 1000; // 7 days

interface CachedPDF {
  bookId: string;
  blob: Blob;
  size: number;
  lastAccessed: number;
  accessCount: number;
  url: string;
}

let db: IDBDatabase | null = null;

const openDB = (): Promise<IDBDatabase> => {
  return new Promise((resolve, reject) => {
    if (db) {
      resolve(db);
      return;
    }

    const request = indexedDB.open(DB_NAME, DB_VERSION);

    request.onerror = () => reject(request.error);
    request.onsuccess = () => {
      db = request.result;
      resolve(db);
    };

    request.onupgradeneeded = (event) => {
      const database = (event.target as IDBOpenDBRequest).result;
      if (!database.objectStoreNames.contains(STORE_NAME)) {
        const store = database.createObjectStore(STORE_NAME, { keyPath: "bookId" });
        store.createIndex("lastAccessed", "lastAccessed", { unique: false });
        store.createIndex("accessCount", "accessCount", { unique: false });
      }
    };
  });
};

export const cachePDF = async (bookId: string, pdfBlob: Blob, url: string): Promise<void> => {
  const database = await openDB();
  const transaction = database.transaction([STORE_NAME], "readwrite");
  const store = transaction.objectStore(STORE_NAME);

  const cached: CachedPDF = {
    bookId,
    blob: pdfBlob,
    size: pdfBlob.size,
    lastAccessed: Date.now(),
    accessCount: 1,
    url,
  };

  await new Promise<void>((resolve, reject) => {
    const request = store.put(cached);
    request.onsuccess = () => resolve();
    request.onerror = () => reject(request.error);
  });

  // Prune cache if needed
  await pruneCache();
};

export const getCachedPDF = async (bookId: string): Promise<Blob | null> => {
  const database = await openDB();
  const transaction = database.transaction([STORE_NAME], "readwrite");
  const store = transaction.objectStore(STORE_NAME);

  const cached = await new Promise<CachedPDF | undefined>((resolve, reject) => {
    const request = store.get(bookId);
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });

  if (!cached) {
    return null;
  }

  // Check if expired
  if (Date.now() - cached.lastAccessed > MAX_AGE_MS) {
    await clearCachedPDF(bookId);
    return null;
  }

  // Update access metadata
  cached.lastAccessed = Date.now();
  cached.accessCount += 1;
  await new Promise<void>((resolve, reject) => {
    const request = store.put(cached);
    request.onsuccess = () => resolve();
    request.onerror = () => reject(request.error);
  });

  return cached.blob;
};

export const isCached = async (bookId: string): Promise<boolean> => {
  const database = await openDB();
  const transaction = database.transaction([STORE_NAME], "readonly");
  const store = transaction.objectStore(STORE_NAME);

  return new Promise((resolve, reject) => {
    const request = store.get(bookId);
    request.onsuccess = () => {
      const cached = request.result;
      if (!cached) {
        resolve(false);
        return;
      }
      // Check if expired
      if (Date.now() - cached.lastAccessed > MAX_AGE_MS) {
        resolve(false);
        return;
      }
      resolve(true);
    };
    request.onerror = () => reject(request.error);
  });
};

export const clearCachedPDF = async (bookId?: string): Promise<void> => {
  const database = await openDB();
  const transaction = database.transaction([STORE_NAME], "readwrite");
  const store = transaction.objectStore(STORE_NAME);

  await new Promise<void>((resolve, reject) => {
    const request = bookId ? store.delete(bookId) : store.clear();
    request.onsuccess = () => resolve();
    request.onerror = () => reject(request.error);
  });
};

export const getCacheSize = async (): Promise<number> => {
  const database = await openDB();
  const transaction = database.transaction([STORE_NAME], "readonly");
  const store = transaction.objectStore(STORE_NAME);

  return new Promise((resolve, reject) => {
    const request = store.getAll();
    request.onsuccess = () => {
      const cached = request.result as CachedPDF[];
      const totalSize = cached.reduce((sum, item) => sum + (item.size || 0), 0);
      resolve(totalSize);
    };
    request.onerror = () => reject(request.error);
  });
};

const pruneCache = async (): Promise<void> => {
  const currentSize = await getCacheSize();
  if (currentSize <= MAX_CACHE_SIZE) {
    return;
  }

  const database = await openDB();
  const transaction = database.transaction([STORE_NAME], "readwrite");
  const store = transaction.objectStore(STORE_NAME);
  const index = store.index("lastAccessed");

  // Get all entries sorted by last accessed (oldest first)
  const allEntries = await new Promise<CachedPDF[]>((resolve, reject) => {
    const request = index.getAll();
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });

  // Remove oldest entries until we're under the limit
  let size = currentSize;
  for (const entry of allEntries) {
    if (size <= MAX_CACHE_SIZE) {
      break;
    }
    await new Promise<void>((resolve, reject) => {
      const request = store.delete(entry.bookId);
      request.onsuccess = () => {
        size -= entry.size || 0;
        resolve();
      };
      request.onerror = () => reject(request.error);
    });
  }
};

export const getCachedPDFUrl = async (bookId: string): Promise<string | null> => {
  const blob = await getCachedPDF(bookId);
  if (!blob) {
    return null;
  }
  return URL.createObjectURL(blob);
};

