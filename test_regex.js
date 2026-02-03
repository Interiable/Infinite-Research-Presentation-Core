const fs = require('fs');
const path = require('path');

const filePath = '/home/hgeon/gravity/LangAIAgent/backend/artifacts/20260202_110241_slide_v1.tsx';
const rawCode = fs.readFileSync(filePath, 'utf8');

console.log("--- ORIGINAL LENGTH:", rawCode.length);

// The regex from SlidePreview.tsx
const regex = /import\s+[\s\S]*?from\s+['"].*?['"];?/g;
const cleanCode = rawCode.replace(regex, '');

console.log("--- CLEANED LENGTH:", cleanCode.length);
console.log("--- FIRST 500 CHARS OF CLEANED CODE ---");
console.log(cleanCode.substring(0, 500));
console.log("--- END ---");

if (cleanCode.includes('import {')) {
    console.log("!!! FAIL: 'import {' still found in code!");
} else {
    console.log("SUCCESS: No imports found.");
}
