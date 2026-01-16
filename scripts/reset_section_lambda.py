"""
Quick Lambda to reset stuck section
"""
import sys
sys.path.insert(0, '/Users/tgulden/Documents/AI Projects/docprof-aws/src/lambda')

from shared.db_utils import get_db_connection

section_id = "5758b872-ff7d-4e1b-a9d9-3ec175ecf4ab"

print(f"Resetting section {section_id}...")

with get_db_connection() as conn:
    with conn.cursor() as cur:
        # Check current status
        cur.execute(
            "SELECT status, generation_progress FROM course_sections WHERE section_id = %s::uuid",
            (section_id,)
        )
        result = cur.fetchone()
        print(f"Current status: {result}")
        
        # Reset to not_started
        cur.execute(
            """
            UPDATE course_sections
            SET status = 'not_started', generation_progress = NULL
            WHERE section_id = %s::uuid
            """,
            (section_id,)
        )
        conn.commit()
        
        # Verify
        cur.execute(
            "SELECT status, generation_progress FROM course_sections WHERE section_id = %s::uuid",
            (section_id,)
        )
        result = cur.fetchone()
        print(f"New status: {result}")

print("✅ Section reset successfully! You can now try generating it again.")

