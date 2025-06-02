const fs = require('fs');

// Read the list of image filenames
const filenames = fs.readFileSync('image_list.txt', 'utf8').trim().split('\n');

// Create the alt tags object with null values
const altTags = {};
filenames.forEach(filename => {
  altTags[filename] = null;
});

// Write to the output file
fs.writeFileSync('_data/alt-tags.json', JSON.stringify(altTags, null, 2));

console.log(`Created alt-tags.json with ${filenames.length} image entries`);
