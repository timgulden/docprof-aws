#!/usr/bin/env python3
"""
Compare MAExpert legacy database schema with AWS implementation.
This script analyzes the code to identify what fields are being stored.
"""

import sys
import os
import re

# Read MAExpert database_client.py to extract schema
maexpert_db_client = "/Users/tgulden/Documents/AI Projects/MAExpert/src/effects/database_client.py"
aws_schema_init = "/Users/tgulden/Documents/AI Projects/docprof-aws/src/lambda/schema_init/handler.py"

def extract_chunk_fields_from_code(filepath):
    """Extract chunk fields from MAExpert insert_chunks method."""
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Find insert_chunks method
    insert_chunks_match = re.search(
        r'def insert_chunks\([^)]*\):[^}]*?payload\.append\([^)]*\)',
        content,
        re.DOTALL
    )
    
    if not insert_chunks_match:
        return None
    
    # Extract the payload.append section
    payload_section = insert_chunks_match.group(0)
    
    # Extract field names from chunk.get() calls
    fields = []
    field_pattern = r'chunk\.get\(["\']([^"\']+)["\']'
    for match in re.finditer(field_pattern, payload_section):
        fields.append(match.group(1))
    
    return fields

def extract_schema_from_sql(filepath):
    """Extract table schema from SQL CREATE TABLE statements."""
    with open(filepath, 'r') as f:
        content = f.read()
    
    schemas = {}
    
    # Find CREATE TABLE statements
    table_pattern = r'CREATE TABLE\s+(\w+)\s*\((.*?)\);'
    for match in re.finditer(table_pattern, content, re.DOTALL | re.IGNORECASE):
        table_name = match.group(1)
        table_def = match.group(2)
        
        # Extract column definitions
        columns = []
        for line in table_def.split('\n'):
            line = line.strip()
            if line and not line.startswith('--') and not line.startswith('PRIMARY') and not line.startswith('FOREIGN') and not line.startswith('UNIQUE') and not line.startswith('CHECK'):
                # Extract column name (first word)
                col_match = re.match(r'(\w+)', line)
                if col_match:
                    columns.append(col_match.group(1))
        
        schemas[table_name] = columns
    
    return schemas

def compare_schemas():
    """Compare MAExpert and AWS schemas."""
    print("=" * 80)
    print("MAExpert vs AWS Schema Comparison")
    print("=" * 80)
    print()
    
    # Read MAExpert database_client.py
    print("📖 Analyzing MAExpert database_client.py...")
    maexpert_chunk_fields = extract_chunk_fields_from_code(maexpert_db_client)
    
    # Read AWS schema_init
    print("☁️  Analyzing AWS schema_init/handler.py...")
    aws_schemas = extract_schema_from_sql(aws_schema_init)
    
    # Compare chunks table
    print("\n" + "=" * 80)
    print("CHUNKS TABLE COMPARISON")
    print("=" * 80)
    
    if maexpert_chunk_fields:
        print("\nMAExpert insert_chunks fields:")
        for i, field in enumerate(maexpert_chunk_fields, 1):
            print(f"  {i}. {field}")
    
    if 'chunks' in aws_schemas:
        print("\nAWS chunks table columns:")
        for i, col in enumerate(aws_schemas['chunks'], 1):
            print(f"  {i}. {col}")
    
    # Compare other tables
    for table in ['books', 'figures', 'chapter_documents']:
        if table in aws_schemas:
            print(f"\n{table.upper()} table columns:")
            for i, col in enumerate(aws_schemas[table], 1):
                print(f"  {i}. {col}")
    
    print("\n" + "=" * 80)
    print("ANALYSIS")
    print("=" * 80)
    
    # Check for missing fields
    if maexpert_chunk_fields and 'chunks' in aws_schemas:
        maexpert_set = set(maexpert_chunk_fields)
        aws_set = set(aws_schemas['chunks'])
        
        missing_in_aws = maexpert_set - aws_set
        extra_in_aws = aws_set - maexpert_set
        
        if missing_in_aws:
            print(f"\n⚠️  Fields in MAExpert but NOT in AWS:")
            for field in sorted(missing_in_aws):
                print(f"  • {field}")
        
        if extra_in_aws:
            print(f"\n➕ Fields in AWS but NOT in MAExpert:")
            for field in sorted(extra_in_aws):
                print(f"  • {field}")
        
        if not missing_in_aws and not extra_in_aws:
            print("\n✅ All fields match!")

if __name__ == '__main__':
    compare_schemas()

