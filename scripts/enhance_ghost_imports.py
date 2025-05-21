#!/usr/bin/env nix-shell
#! nix-shell -i python3 -p "python3.withPackages(ps: with ps; [ pyyaml ])"

"""
Enhance Ghost imported markdown files by adding missing frontmatter fields.
To be run after bin/import_ghost has completed.
"""

import os
import glob
import re
import yaml
import argparse
from datetime import datetime

def parse_frontmatter(content):
    """Extract and parse frontmatter from markdown content."""
    frontmatter_pattern = re.compile(r'^---\s*\n(.*?)\n---\s*\n', re.DOTALL)
    match = frontmatter_pattern.match(content)
    
    if not match:
        return {}, content
    
    frontmatter_str = match.group(1)
    main_content = content[match.end():]
    
    # Parse YAML frontmatter
    try:
        frontmatter = yaml.safe_load(frontmatter_str)
        if frontmatter is None:  # Empty frontmatter
            frontmatter = {}
    except yaml.YAMLError:
        # If YAML parsing fails, try manual parsing
        frontmatter = {}
        for line in frontmatter_str.split('\n'):
            if ':' in line:
                key, value = line.split(':', 1)
                frontmatter[key.strip()] = value.strip()
    
    return frontmatter, main_content

def enhance_frontmatter(frontmatter):
    """Add missing fields with sensible defaults to frontmatter."""
    # Ensure title exists
    if 'title' not in frontmatter:
        frontmatter['title'] = 'Untitled Post'
    
    # Add subtitle if missing (using title as default)
    if 'subtitle' not in frontmatter:
        frontmatter['subtitle'] = frontmatter['title']
    
    # Add header_text if missing (using title as default)
    if 'header_text' not in frontmatter:
        frontmatter['header_text'] = frontmatter['title']
    
    # Add meta_title if missing (using title as default)
    if 'meta_title' not in frontmatter:
        frontmatter['meta_title'] = frontmatter['title']
    
    # Set a default header image if none exists
    if 'header_image' not in frontmatter:
        frontmatter['header_image'] = '/images/8a9c7e1f043ce971.jpg'
    
    # Ensure date exists
    if 'date' not in frontmatter:
        frontmatter['date'] = datetime.now().strftime('%Y-%m-%d')
    
    return frontmatter

def process_file(file_path):
    """Process a single markdown file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    frontmatter, main_content = parse_frontmatter(content)
    enhanced_frontmatter = enhance_frontmatter(frontmatter)
    
    # Format frontmatter as YAML
    frontmatter_yaml = yaml.dump(enhanced_frontmatter, default_flow_style=False, sort_keys=False)
    
    # Combine everything back together
    new_content = f"---\n{frontmatter_yaml}---\n{main_content}"
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print(f"Enhanced: {os.path.basename(file_path)}")
    return True

def main():
    parser = argparse.ArgumentParser(description='Enhance Ghost imported markdown files')
    parser.add_argument('--dir', default='news', help='Directory containing markdown files')
    
    args = parser.parse_args()
    
    # Get all markdown files in the directory
    md_files = glob.glob(os.path.join(args.dir, '*.md'))
    
    if not md_files:
        print(f"No markdown files found in {args.dir}")
        return
    
    processed_count = 0
    for file_path in md_files:
        if process_file(file_path):
            processed_count += 1
    
    print(f"Processed {processed_count} markdown files")

if __name__ == "__main__":
    main()