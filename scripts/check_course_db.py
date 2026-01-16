#!/usr/bin/env python3
"""Check course and sections in PostgreSQL"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'lambda'))

from shared.db_utils import get_db_connection

COURSE_ID = sys.argv[1] if len(sys.argv) > 1 else "4e7cbe9a-c5d6-4f32-a2fd-ee70b01f0988"

with get_db_connection() as conn:
    with conn.cursor() as cur:
        # Check course
        cur.execute('SELECT course_id, title, original_query FROM courses WHERE course_id = %s::uuid', (COURSE_ID,))
        course = cur.fetchone()
        print(f'Course: {course}')
        
        # Check sections
        cur.execute('SELECT COUNT(*) FROM course_sections WHERE course_id = %s::uuid', (COURSE_ID,))
        count = cur.fetchone()[0]
        print(f'Sections count: {count}')
        
        if count > 0:
            cur.execute('SELECT section_id, title, order_index, parent_section_id FROM course_sections WHERE course_id = %s::uuid ORDER BY order_index LIMIT 10', (COURSE_ID,))
            print('\nSections:')
            for row in cur.fetchall():
                print(f'  {row}')
