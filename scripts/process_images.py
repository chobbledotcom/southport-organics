#!/usr/bin/env nix-shell
#! nix-shell -i python3 -p python3 python3Packages.pillow python3Packages.requests python3Packages.pyyaml python3Packages.imagehash

import os
import re
import sys
import hashlib
import requests
import yaml
import time
import imagehash
from PIL import Image
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
import shutil

# Constants
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
PRODUCTS_DIR = os.path.join(REPO_ROOT, 'products')
IMAGES_DIR = os.path.join(REPO_ROOT, 'images')
URL_MAPPING_FILE = os.path.join(SCRIPT_DIR, 'image_url_mapping.yaml')

# Regular expressions to extract frontmatter and find image URLs
FRONTMATTER_PATTERN = re.compile(r'^---\s*$(.*?)^---\s*$', re.MULTILINE | re.DOTALL)
IMAGE_URL_PATTERN = re.compile(r'(https?://i\.etsystatic\.com/[^\s"\']+)')

def create_perceptual_hash(image):
    """Create a perceptual hash of an image using a 64x64 thumbnail."""
    # Resize to 64x64 for consistent hashing
    thumbnail = image.resize((64, 64), Image.Resampling.LANCZOS)
    # Convert to grayscale if it's not already
    if thumbnail.mode != 'L':
        thumbnail = thumbnail.convert('L')
    # Create perceptual hash
    phash = imagehash.phash(thumbnail)
    return str(phash)

def get_image_quality(image):
    """Return a quality score for an image based on resolution."""
    return image.width * image.height

def download_image(url, timeout=10):
    """Download image from URL and return as PIL Image object."""
    try:
        response = requests.get(url, stream=True, timeout=timeout)
        response.raise_for_status()
        return Image.open(BytesIO(response.content))
    except Exception as e:
        print(f"Error downloading {url}: {e}")
        return None

def extract_urls_from_markdown(content):
    """Extract all image URLs from markdown content."""
    # Extract all URLs that match the Etsy pattern
    urls = set()
    
    # Find frontmatter
    frontmatter_match = FRONTMATTER_PATTERN.search(content)
    if frontmatter_match:
        frontmatter = frontmatter_match.group(1)
        # Find all image URLs in the frontmatter
        for url in IMAGE_URL_PATTERN.findall(frontmatter):
            urls.add(url)
    
    return urls

def process_image(url, url_to_hash_map=None):
    """Download image, create hash, and save with hash-based filename."""
    if url_to_hash_map is None:
        url_to_hash_map = {}
    
    # Skip if we've already processed this URL
    if url in url_to_hash_map:
        return url_to_hash_map[url]
    
    # Download image
    image = download_image(url)
    if not image:
        return None
    
    # Create hash from the image
    hash_value = create_perceptual_hash(image)
    filename = f"{hash_value}.jpg"
    filepath = os.path.join(IMAGES_DIR, filename)
    
    # Check if we already have this image
    if os.path.exists(filepath):
        # Compare quality with existing image
        try:
            existing_image = Image.open(filepath)
            existing_quality = get_image_quality(existing_image)
            new_quality = get_image_quality(image)
            
            # If new image is higher quality, replace the existing one
            if new_quality > existing_quality:
                print(f"Replacing {filename} with higher quality version")
                image.save(filepath, format='JPEG', quality=95)
        except Exception as e:
            print(f"Error comparing image quality for {filename}: {e}")
    else:
        # Save new image
        try:
            image.save(filepath, format='JPEG', quality=95)
            print(f"Saved new image: {filename}")
        except Exception as e:
            print(f"Error saving image {filename}: {e}")
            return None
    
    # Return mapping of URL to filename
    url_to_hash_map[url] = filename
    return filename

def process_product_file(file_path, url_to_hash_map):
    """Process a product markdown file to replace image URLs with hashed filenames."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Extract image URLs
        urls = extract_urls_from_markdown(content)
        if not urls:
            print(f"No image URLs found in {file_path}")
            return
        
        # Process each URL and build replacement map
        local_url_map = {}
        for url in urls:
            filename = process_image(url, url_to_hash_map)
            if filename:
                local_url_map[url] = filename
        
        # Replace URLs in content
        new_content = content
        for url, filename in local_url_map.items():
            new_content = new_content.replace(url, filename)
        
        # Write updated content back to file
        if new_content != content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print(f"Updated {file_path} with {len(local_url_map)} image references")
        
        return local_url_map
        
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return None

def save_url_mapping(url_to_hash_map):
    """Save URL to hash mapping to a YAML file."""
    try:
        with open(URL_MAPPING_FILE, 'w', encoding='utf-8') as f:
            yaml.dump(url_to_hash_map, f, default_flow_style=False)
        print(f"Saved URL mapping to {URL_MAPPING_FILE}")
    except Exception as e:
        print(f"Error saving URL mapping: {e}")

def load_url_mapping():
    """Load URL to hash mapping from YAML file if it exists."""
    if os.path.exists(URL_MAPPING_FILE):
        try:
            with open(URL_MAPPING_FILE, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            print(f"Error loading URL mapping: {e}")
    return {}

def main():
    # Ensure images directory exists
    os.makedirs(IMAGES_DIR, exist_ok=True)
    
    # Load existing URL mapping if available
    url_to_hash_map = load_url_mapping()
    print(f"Loaded {len(url_to_hash_map)} existing URL mappings")
    
    # Get all markdown files
    product_files = [os.path.join(PRODUCTS_DIR, f) for f in os.listdir(PRODUCTS_DIR) 
                   if f.endswith('.md')]
    print(f"Found {len(product_files)} product files to process")
    
    # Process each file
    total_urls_processed = 0
    for product_file in product_files:
        local_url_map = process_product_file(product_file, url_to_hash_map)
        if local_url_map:
            total_urls_processed += len(local_url_map)
    
    # Save URL mapping
    save_url_mapping(url_to_hash_map)
    
    # Report results
    print(f"\nProcessing complete:")
    print(f"- Processed {len(product_files)} product files")
    print(f"- Processed {total_urls_processed} image URLs")
    print(f"- Created/updated {len(url_to_hash_map)} unique image files")
    print(f"- Images stored in: {IMAGES_DIR}")

if __name__ == "__main__":
    main()