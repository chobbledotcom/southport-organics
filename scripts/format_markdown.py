#!/usr/bin/env nix-shell
#! nix-shell -i python3 -p python3 python3Packages.pyyaml

import os
import re
import sys
import yaml
from pathlib import Path

# Constants
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
PRODUCTS_DIR = os.path.join(REPO_ROOT, 'products')

# Regular expressions
FRONTMATTER_PATTERN = re.compile(r'^---\s*$(.*?)^---\s*$', re.MULTILINE | re.DOTALL)
EMOJI_LIST_PATTERN = re.compile(r'^([\u2600-\u27BF\u1F300-\u1F64F\u1F680-\u1F6FF\u1F900-\u1F9FF].*?)$', re.MULTILINE)
SECTION_PATTERN = re.compile(r'^([A-Za-z][A-Za-z\s&]+:?)$', re.MULTILINE)
SUBHEADER_PATTERN = re.compile(r'^([A-Z][A-Za-z\s&]+)$', re.MULTILINE)

def format_product_markdown(content):
    """Format markdown content without changing the meaning or words."""
    # Split content into frontmatter and body
    match = FRONTMATTER_PATTERN.search(content)
    if not match:
        return content
        
    frontmatter_text = match.group(0)
    body_start = match.end()
    body_text = content[body_start:].strip()
    
    # Format the body text
    formatted_lines = []
    current_paragraph = []
    
    # Split by lines and process
    lines = body_text.split('\n')
    for i, line in enumerate(lines):
        line = line.strip()
        
        # Skip empty lines
        if not line:
            if current_paragraph:
                formatted_lines.append(' '.join(current_paragraph))
                current_paragraph = []
            formatted_lines.append('')
            continue
        
        # Check if it's a section header
        if SECTION_PATTERN.match(line) and (i == 0 or not lines[i-1].strip()):
            # Add a blank line before section if needed
            if formatted_lines and formatted_lines[-1]:
                formatted_lines.append('')
            # Format as h2
            section_text = line
            if section_text.endswith(':'):
                section_text = section_text[:-1]
            formatted_lines.append(f"## {section_text}")
            continue
            
        # Check if it's a sub-header
        if SUBHEADER_PATTERN.match(line) and len(line) < 40 and line.split()[0].istitle():
            # Add a blank line before if needed
            if formatted_lines and formatted_lines[-1]:
                formatted_lines.append('')
            # Format as h3
            formatted_lines.append(f"### {line}")
            continue
        
        # Check if it's an emoji list
        emoji_match = EMOJI_LIST_PATTERN.match(line)
        if emoji_match:
            # Add a blank line before if in a paragraph
            if current_paragraph:
                formatted_lines.append(' '.join(current_paragraph))
                current_paragraph = []
                formatted_lines.append('')
            # Format as list item
            formatted_lines.append(f"* {line}")
            continue
        
        # Regular paragraph content
        current_paragraph.append(line)
    
    # Add any remaining paragraph
    if current_paragraph:
        formatted_lines.append(' '.join(current_paragraph))
    
    # Join everything back together
    formatted_body = '\n'.join(formatted_lines)
    
    return f"{frontmatter_text}\n\n{formatted_body}"

def process_product_file(file_path, dry_run=True):
    """Process a single product markdown file to improve formatting."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Format the content
        formatted_content = format_product_markdown(content)
        
        # In dry-run mode, just return the results
        if dry_run:
            return {
                'original': content,
                'formatted': formatted_content,
                'changed': content != formatted_content
            }
        
        # Otherwise, write back to the file if changed
        if content != formatted_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(formatted_content)
            return True
        return False
        
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return None

def main():
    # Get all markdown files
    product_files = [os.path.join(PRODUCTS_DIR, f) for f in os.listdir(PRODUCTS_DIR) 
                   if f.endswith('.md')]
    print(f"Found {len(product_files)} product files to process")
    
    # Process the first file as example
    first_file = product_files[0]
    result = process_product_file(first_file, dry_run=True)
    
    if result and result['changed']:
        print(f"\nExample formatting for {os.path.basename(first_file)}:\n")
        print("==== ORIGINAL CONTENT ====")
        print(result['original'])
        print("\n==== FORMATTED CONTENT ====")
        print(result['formatted'])
        
        # Ask if user wants to format all files
        response = input("\nDo you want to format all files with these rules? (y/n): ")
        if response.lower() == 'y':
            # Process all files
            formatted_count = 0
            for file_path in product_files:
                result = process_product_file(file_path, dry_run=False)
                if result:
                    formatted_count += 1
                    print(f"Formatted: {os.path.basename(file_path)}")
            
            print(f"\nFormatting complete. Updated {formatted_count} of {len(product_files)} files.")
        else:
            print("Operation cancelled. No files were modified.")
    else:
        print(f"No formatting changes needed for {os.path.basename(first_file)}")

if __name__ == "__main__":
    main()