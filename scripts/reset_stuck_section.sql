-- Reset stuck sections (status=in_progress but no recent activity)
-- Run this to clean up sections that failed during generation

-- Option 1: Reset specific section by ID
-- UPDATE course_sections 
-- SET status = 'not_started', generation_progress = NULL 
-- WHERE section_id = 'YOUR-SECTION-ID-HERE'::uuid;

-- Option 2: Reset ALL stuck sections (in_progress for > 15 minutes)
UPDATE course_sections 
SET status = 'not_started', generation_progress = NULL 
WHERE status = 'in_progress' 
  AND (updated_at IS NULL OR updated_at < NOW() - INTERVAL '15 minutes');

-- Show sections that were reset
SELECT section_id, title, status, generation_progress
FROM course_sections
WHERE status = 'not_started' AND updated_at > NOW() - INTERVAL '1 minute';

