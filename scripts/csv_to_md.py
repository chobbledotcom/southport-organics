#!/usr/bin/env nix-shell
#! nix-shell -i python3 -p python3 python3Packages.pandas

import os
import re
import pandas as pd
import unicodedata
import sys

def slugify(text):
    """Convert a string to a URL-friendly slug."""
    # Normalize unicode characters and convert to lowercase
    text = unicodedata.normalize('NFKD', text)
    text = text.lower()
    # Remove non-alphanumeric characters and replace spaces with hyphens
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '-', text)
    return text.strip('-')

def extract_features(description):
    """Extract features/bullet points from description."""
    features = []
    lines = description.split('\n')
    for line in lines:
        line = line.strip()
        if line.startswith('- '):
            features.append(line[2:])
    return features


def process_images(row):
    """Process image URLs into gallery items with full external URLs."""
    gallery = {}
    image_prefix = "IMAGE"

    # Find all image columns
    image_cols = [col for col in row.index if col.startswith(image_prefix) and pd.notna(row[col])]

    # Process each image
    for i, col in enumerate(image_cols):
        image_url = row[col]
        if not image_url or pd.isna(image_url):
            continue

        # Store the full URL
        image_num = i + 1
        image_key = f"Image {image_num}"
        gallery[image_key] = image_url

    return gallery

def generate_specs(row):
    """Generate specs from row data."""
    specs = []

    if pd.notna(row['PRICE']) and row['PRICE']:
        specs.append({"name": "Price", "value": f"£{row['PRICE']}"})

    if pd.notna(row['MATERIALS']) and row['MATERIALS']:
        specs.append({"name": "Materials", "value": row['MATERIALS']})

    # Add more specs based on available data
    if "Vegan" in row['DESCRIPTION']:
        specs.append({"name": "Vegan", "value": "Yes"})

    if "Cruelty Free" in row['DESCRIPTION']:
        specs.append({"name": "Cruelty Free", "value": "Yes"})

    return specs

def extract_categories(tags):
    """Extract categories from tags."""
    if pd.isna(tags):
        return ["products"]

    # Convert tags string to list and limit to 3 categories
    tag_list = tags.split(',')[:3]
    categories = [tag.strip().replace('_', '-') for tag in tag_list]
    return categories

def create_markdown_file(row, output_dir):
    """Create a markdown file from a row in the CSV."""
    title = row['TITLE'].split(',')[0].strip()  # Use the first part of the title
    slug = slugify(title)
    filename = f"{slug}.md"

    # Process description and extract features
    description = row['DESCRIPTION'] if pd.notna(row['DESCRIPTION']) else ""
    features = extract_features(description)

    # Generate specs
    specs = generate_specs(row)

    # Process images with full URLs
    gallery = process_images(row)

    # Extract categories
    categories = extract_categories(row['TAGS']) if pd.notna(row['TAGS']) else ["products"]

    # Short description (first paragraph of description)
    short_description = description.split('\n\n')[0] if description else ""
    # Limit short description to ~100 characters
    if len(short_description) > 100:
        short_description = short_description[:97] + "..."

    # Create markdown content
    content = [
        "---",
        f"title: {title}",
        f"        f"price: £{row['PRICE']}" if pd.notna(row['PRICE']) else "price: Contact for pricing",
    ]

    # Add categories
    content.append("categories:")
    for category in categories:
        content.append(f"  - {category}")

    # Add gallery with full URLs
    content.append("gallery:")
    for name, image_url in gallery.items():
        content.append(f"  - /images/{image_url}")

    # Add specs
    content.append("specs:")
    for spec in specs:
        content.append(f"  - name: {spec['name']}")
        content.append(f"    value: {spec['value']}")

    # Add features
    if features:
        content.append("features:")
        for feature in features:
            content.append(f"  - {feature}")

    content.append("---")
    content.append("")

    # Add the full description (excluding the bullet points we already extracted)
    description_paragraphs = [p for p in description.split('\n\n') if not p.strip().startswith('-')]
    content.extend(description_paragraphs)

    # Write to file
    filepath = os.path.join(output_dir, filename)
    with open(filepath, 'w') as f:
        f.write('\n'.join(content))

    return filepath

def main():
    # Get absolute paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(script_dir)  # Go up one level to repo root
    csv_path = os.path.join(script_dir, 'etsy.csv')

    # Use main products directory instead of a subdirectory
    products_dir = os.path.join(repo_root, 'products')

    # Clean up existing markdown files in products directory
    if os.path.exists(products_dir):
        print(f"Cleaning up existing product pages in: {products_dir}")
        for file in os.listdir(products_dir):
            if file.endswith('.md'):
                file_path = os.path.join(products_dir, file)
                if os.path.isfile(file_path):
                    os.unlink(file_path)
    else:
        print(f"Creating products directory: {products_dir}")

    # Ensure the products directory exists
    os.makedirs(products_dir, exist_ok=True)

    # Read CSV file
    try:
        df = pd.read_csv(csv_path)
        print(f"Found {len(df)} products in the CSV file.")
    except Exception as e:
        print(f"Error reading CSV file: {e}")
        sys.exit(1)

    # Process each row
    files_created = []

    for _, row in df.iterrows():
        try:
            # Create markdown file with full image URLs
            filepath = create_markdown_file(row, products_dir)
            files_created.append(filepath)

            print(f"Created: {filepath}")
        except Exception as e:
            print(f"Error processing row with title '{row.get('TITLE', 'unknown')}': {e}")

    print(f"\nProcessed {len(df)} rows:")
    print(f"- Created {len(files_created)} markdown files in {products_dir}")

if __name__ == "__main__":
    main()
