/**
 * Normalizes a timestamp string to ensure UTC interpretation.
 * Adds 'Z' suffix if timezone indicator is missing.
 * 
 * @param timestamp - ISO timestamp string (may or may not have timezone)
 * @returns Normalized timestamp string with timezone indicator
 */
export function normalizeTimestamp(timestamp: string): string {
  const tsStr = String(timestamp).trim();
  const hasTimezone =
    tsStr.endsWith("Z") ||
    /[+-]\d{2}:\d{2}$/.test(tsStr) ||
    /[+-]\d{4}$/.test(tsStr);
  return hasTimezone ? tsStr : tsStr + "Z";
}

/**
 * Sorts messages by timestamp in ascending order.
 * 
 * @param messages - Array of messages to sort
 * @returns Sorted array of messages
 */
export function sortMessagesByTimestamp<T extends { timestamp: string }>(
  messages: T[]
): T[] {
  return [...messages].sort((a, b) => {
    const aNormalized = normalizeTimestamp(a.timestamp);
    const bNormalized = normalizeTimestamp(b.timestamp);
    return new Date(aNormalized).getTime() - new Date(bNormalized).getTime();
  });
}

