#!/usr/bin/env python3
"""Test outline parsing logic"""

import sys
import os
import re
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'lambda'))

# Get actual outline from DynamoDB
import boto3
dynamodb = boto3.client('dynamodb', region_name='us-east-1')

COURSE_ID = sys.argv[1] if len(sys.argv) > 1 else "4e7cbe9a-c5d6-4f32-a2fd-ee70b01f0988"

response = dynamodb.get_item(
    TableName='docprof-dev-course-state',
    Key={'course_id': {'S': COURSE_ID}}
)

if 'Item' not in response:
    print(f"Course {COURSE_ID} not found in DynamoDB")
    sys.exit(1)

outline_text = response['Item'].get('outline_text', {}).get('S', '')
if not outline_text:
    print("No outline_text in state")
    sys.exit(1)

print(f"Outline text length: {len(outline_text)}")
print(f"First 500 chars:\n{outline_text[:500]}\n")

# Test parsing
parts = []
current_part = None
current_sections = []
in_objectives = False
current_objectives = []

part_pattern = r'##?\s*Part\s+\d+:\s*(.+?)(?:\s*-\s*(\d+)\s*minutes?)?$'
section_pattern = r'###\s*Section\s+\d+:\s*(.+?)\s*-\s*(\d+)\s*minutes?'

lines = outline_text.split('\n')
for line in lines:
    line = line.strip()
    if not line:
        in_objectives = False
        continue
    
    part_match = re.match(part_pattern, line, re.IGNORECASE)
    section_match = re.match(section_pattern, line, re.IGNORECASE)
    
    if part_match:
        if current_part and current_sections:
            parts.append({"title": current_part, "sections": current_sections})
        current_part = part_match.group(1).strip()
        current_sections = []
        in_objectives = False
        print(f"✓ Found part: {current_part}")
        continue
    
    if section_match:
        section_title = section_match.group(1).strip()
        section_minutes = int(section_match.group(2))
        current_sections.append({
            "title": section_title,
            "time_minutes": section_minutes,
            "learning_objectives": [],
        })
        print(f"  ✓ Found section: {section_title} ({section_minutes} min)")
        in_objectives = False
        continue

if current_part and current_sections:
    parts.append({"title": current_part, "sections": current_sections})

print(f"\n=== PARSING RESULTS ===")
print(f"Parts found: {len(parts)}")
print(f"Total sections: {sum(len(p['sections']) for p in parts)}")
for i, part in enumerate(parts, 1):
    print(f"\nPart {i}: {part['title']}")
    print(f"  Sections: {len(part['sections'])}")
    for j, section in enumerate(part['sections'][:3], 1):
        print(f"    {j}. {section['title']} ({section['time_minutes']} min)")
