/**
 * Formats a timestamp string to Eastern Time.
 * Handles timestamps with or without timezone indicators.
 * 
 * @param timestamp - ISO timestamp string (may or may not have timezone)
 * @returns Formatted time string in Eastern Time, or original string if invalid
 */
export function formatTimestamp(timestamp: string): string {
  try {
    // Normalize timestamp - add 'Z' if missing to ensure UTC interpretation
    let timestampStr = String(timestamp).trim();
    
    // Check if it has timezone indicator
    const hasTimezone = timestampStr.endsWith('Z') || 
                       /[+-]\d{2}:\d{2}$/.test(timestampStr) ||
                       /[+-]\d{4}$/.test(timestampStr);
    
    if (!hasTimezone) {
      // No timezone - assume UTC (backend sends UTC without timezone)
      // JavaScript interprets strings without timezone as LOCAL time, not UTC!
      // We MUST add 'Z' to force UTC interpretation
      timestampStr = timestampStr + 'Z';
    }
    
    const date = new Date(timestampStr);
    if (isNaN(date.getTime())) {
      console.warn("Invalid timestamp:", timestamp);
      return timestamp;
    }
    
    // Convert UTC timestamp to Eastern Time
    const etTime = date.toLocaleTimeString("en-US", {
      timeZone: "America/New_York",
      hour: "numeric",
      minute: "2-digit",
      hour12: true,
    });
    
    return etTime;
  } catch (error) {
    console.error("Error converting timestamp:", error, timestamp);
    return timestamp;
  }
}

