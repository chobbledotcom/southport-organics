#!/usr/bin/env node

const { execSync } = require("child_process");
const fs = require("fs");
const path = require("path");
const glob = require("glob");

// Configuration
const TEMP_DIR = path.join(__dirname, "temp-eleventy-import");
const LOG_FILE = `/tmp/eleventy-import-${process.pid}.log`;
const OUTPUT_DIR = path.join(__dirname, "..", "news");
const RSS_URL = "https://news.southportorganics.co.uk/rss/";

// Helper functions
function printStatus(message) {
  process.stdout.write(`\x1b[1A\x1b[K${message}\n`);
}

function cleanup() {
  try {
    execSync(`rm -rf ${TEMP_DIR}`);
  } catch (error) {
    console.error("Error during cleanup:", error);
  }
}

function cleanupUnusedAssets() {
  try {
    // Check if assets directory exists
    const assetsDir = path.resolve(path.join(__dirname, "..", "news", "assets"));
    if (fs.existsSync(assetsDir)) {
      // Get all markdown files to check if assets are being used
      const newsDir = path.resolve(path.join(__dirname, "..", "news"));
      const files = glob.sync(path.join(newsDir, "*.md"));
      const allContent = files.map(file => fs.readFileSync(file, "utf8")).join("");
      
      // Get all assets
      const assets = glob.sync(path.join(assetsDir, "*.*"));
      let removedCount = 0;
      
      // Check each asset to see if it's referenced in any content
      assets.forEach(asset => {
        const assetBasename = path.basename(asset);
        // Check if asset is referenced in any content
        if (!allContent.includes(`/assets/${assetBasename}`)) {
          fs.unlinkSync(asset);
          removedCount++;
          console.log(`  Removed unused asset: ${assetBasename}`);
        }
      });
      
      console.log(`Removed ${removedCount} unused assets`);
      
      // Remove the assets directory if it's empty
      if (fs.readdirSync(assetsDir).length === 0) {
        fs.rmdirSync(assetsDir);
        console.log("Removed empty assets directory");
      }
    }
  } catch (err) {
    console.error("Error cleaning up unused assets:", err);
  }
}

async function main() {
  console.log("~~ spooky ghost importer 👻 ~~\n");

  // Clean up any previous temp dir
  cleanup();

  try {
    // Create temp directory
    fs.mkdirSync(TEMP_DIR, { recursive: true });

    // Clone eleventy-import repo
    printStatus("👻 summoning @11ty/import");
    execSync(
      `git clone --depth=1 --quiet https://github.com/11ty/eleventy-import/ ${TEMP_DIR}`,
      {
        stdio: [
          "ignore",
          fs.openSync(LOG_FILE, "a"),
          fs.openSync(LOG_FILE, "a"),
        ],
      }
    );

    // Patch RSS parser
    printStatus("🔮 patching rss parser");

    // Fix media:description null issue
    let rssFilePath = path.join(TEMP_DIR, "src/DataSource/Rss.js");
    let rssContent = fs.readFileSync(rssFilePath, "utf8");

    rssContent = rssContent.replace(
      'source["media:description"]["#text"]',
      'source["media:description"]?.["#text"] || ""'
    );

    // Set contentType to html for RSS feeds so markdown conversion works
    rssContent = rssContent.replace(
      '// contentType: "", // unknown',
      'contentType: "html", // Set to html for markdown conversion'
    );

    fs.writeFileSync(rssFilePath, rssContent);

    // Install dependencies
    printStatus("⚰ gathering dependencies");
    process.chdir(TEMP_DIR);
    execSync("npm install --quiet", {
      stdio: ["ignore", fs.openSync(LOG_FILE, "a"), fs.openSync(LOG_FILE, "a")],
    });

    // Run the import using the CLI
    printStatus("🧟 transplanting blog posts");
    
    const importOutput = execSync(
      `node cli.js rss ${RSS_URL} --assetrefs=absolute --output=../../news --format=markdown --cacheduration=0 --overwrite`,
      { encoding: "utf8" }
    );
    
    console.log(importOutput);

    // Enhance markdown files and process images
    printStatus("💅 enhancing markdown files");
    enhanceMarkdownFiles();
    
    // Clean up unused assets
    printStatus("🧹 cleaning up unused assets");
    cleanupUnusedAssets();

    // Clean up
    printStatus("🦇 disappearing");
    cleanup();

    printStatus("👻 ghosts captured successfully");
    console.log("\n🎃 yay");
  } catch (error) {
    console.error("Error during import:", error);
    cleanup();
    process.exit(1);
  }
}

function processImages(mainContent, postSlug) {
  // Create images directory if it doesn't exist
  const newsImageDir = path.resolve(path.join(__dirname, "..", "news", "images"));
  if (!fs.existsSync(newsImageDir)) {
    fs.mkdirSync(newsImageDir, { recursive: true });
  }
  
  // Regular expression to find image tags in markdown
  const imageRegex = /!\[(.*?)\]\(\/assets\/(.*?)\.(\w+)\)/g;
  const imagePaths = [];
  let processedContent = mainContent;
  let match;
  
  // Find all images in the content
  while ((match = imageRegex.exec(mainContent)) !== null) {
    const [fullMatch, altText, assetId, extension] = match;
    const sourceAssetPath = path.resolve(path.join(__dirname, "..", "news", "assets", `${assetId}.${extension}`));
    
    // Only process if the source asset exists
    if (fs.existsSync(sourceAssetPath)) {
      // Generate a new filename based on the post slug and a counter
      const newFilename = `${postSlug}-${imagePaths.length + 1}.${extension}`;
      const newAssetPath = path.join(newsImageDir, newFilename);
      
      // Copy the image to the new location
      try {
        fs.copyFileSync(sourceAssetPath, newAssetPath);
        console.log(`  Copied image to: images/${newFilename}`);
        
        // Replace the image URL in the content
        const newImageMarkdown = `![${altText}](/news/images/${newFilename})`;
        processedContent = processedContent.replace(fullMatch, newImageMarkdown);
        
        // Save the image path for potential use as header image
        imagePaths.push(`/news/images/${newFilename}`);
      } catch (err) {
        console.error(`  Error copying image ${sourceAssetPath}:`, err);
      }
    }
  }
  
  return { processedContent, imagePaths };
}

function enhanceMarkdownFiles() {
  try {
    // Get all markdown files in the output directory
    const newsDir = path.resolve(path.join(__dirname, "..", "news"));
    const files = glob.sync(path.join(newsDir, "*.md"));

    files.forEach((file) => {
      try {
        // Read the file
        const content = fs.readFileSync(file, "utf8");

        // Split into front matter and content
        const parts = content.split("---\n");
        if (parts.length < 3) return; // Skip if no proper front matter

        // Parse the front matter
        const frontMatter = parts[1];
        let mainContent = parts.slice(2).join("---\n");

        // Parse existing front matter
        const frontMatterLines = frontMatter.trim().split("\n");
        const frontMatterObj = {};

        frontMatterLines.forEach((line) => {
          const [key, ...valueParts] = line.split(":");
          if (key && valueParts.length) {
            frontMatterObj[key.trim()] = valueParts.join(":").trim();
          }
        });
        
        // Generate a slug for the post based on the filename or title
        const fileNameWithoutExt = path.basename(file, '.md');
        const postSlug = fileNameWithoutExt.replace(/^\d{4}-\d{2}-\d{2}-/, ''); // Remove date prefix if present
        
        // Process images and update content
        const { processedContent, imagePaths } = processImages(mainContent, postSlug);
        mainContent = processedContent;

        // Add missing fields with defaults
        if (!frontMatterObj.subtitle && frontMatterObj.title) {
          frontMatterObj.subtitle = frontMatterObj.title;
        }

        if (!frontMatterObj.header_text && frontMatterObj.title) {
          frontMatterObj.header_text = frontMatterObj.title;
        }

        if (!frontMatterObj.meta_title && frontMatterObj.title) {
          frontMatterObj.meta_title = frontMatterObj.title;
        }

        // Set header image from the first image found in the post if one exists
        if (!frontMatterObj.header_image && imagePaths.length > 0) {
          frontMatterObj.header_image = imagePaths[0];
        } else if (!frontMatterObj.header_image) {
          // Default fallback image if no images in the post
          frontMatterObj.header_image = "/images/8a9c7e1f043ce971.jpg";
        }

        // Generate the new front matter
        let newFrontMatter = "";
        for (const [key, value] of Object.entries(frontMatterObj)) {
          newFrontMatter += `${key}: ${value}\n`;
        }

        // Combine everything back together
        const newContent = `---\n${newFrontMatter}---\n${mainContent}`;

        // Write the updated file
        fs.writeFileSync(file, newContent, "utf8");
        console.log(`Enhanced: ${path.basename(file)}`);
      } catch (err) {
        console.error(`Error processing file ${file}:`, err);
      }
    });
  } catch (err) {
    console.error("Error enhancing markdown files:", err);
  }
}

// Run the main function
main().catch((error) => {
  console.error("Unhandled error:", error);
  cleanup();
  process.exit(1);
});