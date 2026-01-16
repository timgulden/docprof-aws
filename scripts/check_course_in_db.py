#!/usr/bin/env python3
"""Check if course sections exist in PostgreSQL"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'lambda'))

from shared.db_utils import get_db_connection

COURSE_ID = "a684bb3e-ff2a-4a08-8581-0c403b4f6df8"

with get_db_connection() as conn:
    with conn.cursor() as cur:
        # Check if course exists in PostgreSQL
        cur.execute('SELECT course_id, title, original_query FROM courses WHERE course_id = %s::uuid', (COURSE_ID,))
        course = cur.fetchone()
        print(f'Course in PostgreSQL: {course}')
        
        # Check sections
        cur.execute('SELECT COUNT(*) FROM course_sections WHERE course_id = %s::uuid', (COURSE_ID,))
        section_count = cur.fetchone()[0]
        print(f'Number of sections in PostgreSQL: {section_count}')
        
        if section_count > 0:
            cur.execute('SELECT section_id, title, order_index, parent_section_id FROM course_sections WHERE course_id = %s::uuid ORDER BY order_index LIMIT 10', (COURSE_ID,))
            sections = cur.fetchall()
            print(f'First few sections:')
            for section in sections:
                print(f'  {section}')
