#!/usr/bin/env nix-shell
#! nix-shell -i python3 -p python3 python3Packages.pillow python3Packages.imagehash python3Packages.numpy

import os
import sys
import json
from collections import defaultdict
from pathlib import Path
from PIL import Image, ImageOps
import imagehash
import numpy as np

# Constants
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
IMAGES_DIR = os.path.join(REPO_ROOT, 'images')
OUTPUT_FILE = os.path.join(REPO_ROOT, 'image_duplicates.json')

def normalize_image(image_path, size=(24, 24)):
    """
    Normalize an image to a standard size and convert to grayscale for comparison.
    
    Args:
        image_path: Path to the image file
        size: Tuple of (width, height) to resize to
        
    Returns:
        Normalized PIL Image object
    """
    try:
        # Open the image
        with Image.open(image_path) as img:
            # Convert to grayscale
            img = ImageOps.grayscale(img)
            
            # Resize to standard dimensions (smaller than before for more aggressive normalization)
            img = img.resize(size, Image.Resampling.LANCZOS)
            
            # Enhance contrast for better hash comparison
            img = ImageOps.autocontrast(img, cutoff=2)
            
            # Apply gaussian blur to reduce noise/details
            from PIL import ImageFilter
            img = img.filter(ImageFilter.GaussianBlur(radius=0.5))
            
            # Equalize histogram to further normalize brightness
            img = ImageOps.equalize(img)
                
            return img
    except Exception as e:
        print(f"Error processing {image_path}: {e}")
        return None

def get_image_hash(normalized_image, hash_size=16):
    """
    Generate a perceptual hash for a normalized image.
    
    Args:
        normalized_image: PIL Image that has been normalized
        hash_size: Size of the hash
        
    Returns:
        Hash string
    """
    if normalized_image is None:
        return None
        
    # Use pHash as primary method (good for detecting similar but resized/processed images)
    p_hash = str(imagehash.phash(normalized_image, hash_size=hash_size))
    
    # Use average hash as secondary method (good for minor color variations)
    a_hash = str(imagehash.average_hash(normalized_image, hash_size=hash_size))
    
    # Use wavelet hash for the third component (good for texture similarity)
    w_hash = str(imagehash.whash(normalized_image, hash_size=hash_size))
    
    # Combine hashes into a single string
    combined_hash = f"{p_hash}_{a_hash}_{w_hash}"
    return combined_hash

def get_image_signature(image_path):
    """
    Generate a signature for an image that can be used to identify duplicates.
    
    Args:
        image_path: Path to the image file
        
    Returns:
        Tuple of (hash_string, file_size)
    """
    try:
        normalized_img = normalize_image(image_path)
        if normalized_img is None:
            return None
            
        # Get perceptual hash
        img_hash = get_image_hash(normalized_img)
        
        # Get file size as additional factor
        file_size = os.path.getsize(image_path)
        
        return (img_hash, file_size)
    except Exception as e:
        print(f"Error generating signature for {image_path}: {e}")
        return None

def image_similarity_score(img1_hash_parts, img2_hash_parts):
    """
    Calculate a similarity score between two images based on their hash components.
    Lower score means more similar.
    
    Args:
        img1_hash_parts: List of hash strings for first image [phash, ahash, whash]
        img2_hash_parts: List of hash strings for second image [phash, ahash, whash]
        
    Returns:
        Similarity score (lower = more similar)
    """
    # Convert string hashes to hash objects 
    img1_hashes = [imagehash.hex_to_hash(h) for h in img1_hash_parts]
    img2_hashes = [imagehash.hex_to_hash(h) for h in img2_hash_parts]
    
    # Calculate differences for each hash type with weights
    p_diff = img1_hashes[0] - img2_hashes[0]  # pHash (good for similar images)
    a_diff = img1_hashes[1] - img2_hashes[1]  # aHash (good for colors)
    w_diff = img1_hashes[2] - img2_hashes[2]  # wHash (good for patterns/textures)
    
    # Weight the differences (pHash is most important)
    weighted_diff = (p_diff * 0.5) + (a_diff * 0.25) + (w_diff * 0.25)
    
    return weighted_diff

def find_similar_images(images_dir, similarity_threshold=6):
    """
    Find visually similar images in a directory.
    
    Args:
        images_dir: Directory containing images
        similarity_threshold: Maximum similarity score to consider as similar
        
    Returns:
        Dictionary mapping image signatures to lists of similar images
    """
    # Store image data: hash and file info
    image_data = []
    
    # List all image files
    image_files = [f for f in os.listdir(images_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif'))]
    print(f"Found {len(image_files)} images to compare")
    
    # First pass: Process all images and collect their hashes
    for i, img_file in enumerate(image_files):
        if i % 10 == 0:
            print(f"Processing image {i+1}/{len(image_files)}", end='\r')
        
        img_path = os.path.join(images_dir, img_file)
        signature = get_image_signature(img_path)
        
        if signature:
            # Split the combined hash into its components
            hash_parts = signature[0].split('_')
            
            # Skip if we don't have all hash parts
            if len(hash_parts) < 3:
                print(f"Warning: Incomplete hash for {img_file}")
                continue
                
            image_data.append({
                "file": img_file,
                "path": img_path,
                "size": signature[1],
                "hash": signature[0],
                "hash_parts": hash_parts
            })
    
    print("\nCompleted initial processing")
    
    # Second pass: Group similar images
    similar_groups = []
    processed = set()
    
    # Compare each image with every other image
    for i, img1 in enumerate(image_data):
        if img1["file"] in processed:
            continue
            
        # Create a new group with this image
        group = [img1]
        processed.add(img1["file"])
        
        # Compare with all other unprocessed images
        for img2 in image_data[i+1:]:
            if img2["file"] in processed:
                continue
                
            # Calculate similarity score
            try:
                similarity = image_similarity_score(img1["hash_parts"], img2["hash_parts"])
                
                # If within threshold, add to group
                if similarity <= similarity_threshold:
                    group.append(img2)
                    processed.add(img2["file"])
            except Exception as e:
                print(f"Error comparing {img1['file']} and {img2['file']}: {e}")
        
        # If we found similar images, add the group
        if len(group) > 1:
            similar_groups.append(group)
    
    print(f"Found {len(similar_groups)} groups of similar images")
    
    # Now create a more readable result dictionary
    result = {}
    
    for i, group in enumerate(similar_groups):
        # Sort files in group by size (largest first - likely highest quality)
        group.sort(key=lambda x: x['size'], reverse=True)
        
        # Add to result with a simple group ID
        group_name = f"group_{i+1}"
        result[group_name] = {
            "reference_hash": group[0]['hash'],
            "files": [img['file'] for img in group],
            "file_sizes": [img['size'] for img in group],
            "paths": [img['path'] for img in group],
            "primary": group[0]['file'],  # First file is the primary (largest) one
            "duplicates": [img['file'] for img in group[1:]]  # Rest are duplicates
        }
    
    return result

def main():
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description='Find duplicate images based on visual similarity.')
    parser.add_argument('--threshold', type=int, default=6, 
                        help='Similarity threshold (lower = more similar, higher = more matches)')
    parser.add_argument('--visualize', action='store_true',
                        help='Generate visualization of each group')
    args = parser.parse_args()
    
    # Find duplicate images
    print(f"Analyzing images in: {IMAGES_DIR}")
    print(f"Using similarity threshold: {args.threshold}")
    duplicate_groups = find_similar_images(IMAGES_DIR, similarity_threshold=args.threshold)
    
    # Save results to JSON file
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(duplicate_groups, f, indent=2)
    
    # Print summary
    total_duplicates = sum(len(group["files"]) - 1 for group in duplicate_groups.values())
    total_groups = len(duplicate_groups)
    
    print(f"\nAnalysis complete:")
    print(f"- Found {total_groups} groups of similar images")
    print(f"- Identified {total_duplicates} potential duplicate files")
    print(f"- Results saved to: {OUTPUT_FILE}")
    
    # Print some examples
    if duplicate_groups:
        print("\nExample duplicate groups:")
        for i, (group_name, group_data) in enumerate(list(duplicate_groups.items())[:3]):
            file_list = ", ".join(group_data["files"])
            print(f"  Group {i+1}: {file_list}")
    
    # Generate visual comparison if requested
    if args.visualize and duplicate_groups:
        visualization_dir = os.path.join(REPO_ROOT, 'image_duplicates_visual')
        os.makedirs(visualization_dir, exist_ok=True)
        
        print(f"\nGenerating visualizations in {visualization_dir}...")
        
        for group_name, group_data in duplicate_groups.items():
            # Create a combined image showing all duplicates
            files = group_data["files"]
            if len(files) > 1:
                try:
                    # Calculate grid dimensions
                    cols = min(3, len(files))
                    rows = (len(files) + cols - 1) // cols
                    
                    # Load all images in group
                    images = []
                    for img_file in files:
                        img_path = os.path.join(IMAGES_DIR, img_file)
                        img = Image.open(img_path)
                        # Resize to reasonable dimensions
                        img.thumbnail((400, 400))
                        images.append(img)
                    
                    # Find max dimensions
                    max_width = max(img.width for img in images)
                    max_height = max(img.height for img in images)
                    
                    # Create grid image
                    grid_img = Image.new('RGB', (max_width * cols, max_height * rows))
                    
                    # Paste images into grid
                    for i, img in enumerate(images):
                        row = i // cols
                        col = i % cols
                        grid_img.paste(img, (col * max_width, row * max_height))
                    
                    # Save grid
                    grid_path = os.path.join(visualization_dir, f"{group_name}.jpg")
                    grid_img.save(grid_path)
                    print(f"  Created visualization for {group_name}")
                except Exception as e:
                    print(f"  Error creating visualization for {group_name}: {e}")
    
    print("\nYou can now review the duplicates in image_duplicates.json")
    print("The first file in each group is typically the largest/highest quality version")
    print("\nTo find more or fewer duplicates, run with --threshold option:")
    print("  Lower threshold = stricter matching (fewer duplicates)")
    print("  Higher threshold = looser matching (more duplicates)")
    print("Example: ./scripts/find_duplicate_images.py --threshold 8")

if __name__ == "__main__":
    main()