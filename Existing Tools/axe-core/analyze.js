const puppeteer = require('puppeteer');
const axeCore = require('axe-core');
const { parse: parseURL } = require('url');
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const xlsx = require('xlsx');

// Read URLs from Excel file, replace your test case file here
const workbook = xlsx.readFile(path.join(__dirname, '../Test Cases Tailored.xlsx'));
const sheet = workbook.Sheets[workbook.SheetNames[0]];
const data = xlsx.utils.sheet_to_json(sheet);

// Extract URLs and WCAG Criteria
const urls = data.map(row => ({ url: row.URL, criterion: row['WCAG Criterion'] }));

// Cheap URL validation
const isValidURL = input => {
  const u = parseURL(input);
  return u.protocol && u.host;
};

// Extract WCAG criterion from tags
const extractWcagCriteria = tags => {
  const wcagTags = tags.filter(tag => tag.startsWith('wcag'));
  return wcagTags.length > 0 ? wcagTags.map(tag => tag.replace('wcag', 'WCAG ')) : ['N/A'];
};

// Convert URL to a valid file name
const urlToFileName = url => {
  const parsedUrl = parseURL(url);
  const segments = parsedUrl.pathname.split('/').filter(segment => segment.length > 0);
  const pathname = segments.pop();
  return `${pathname}_axe_result.json`.toLowerCase();
};

// Sanitize folder name for Windows
const sanitizeFolderName = name => {
  return name.replace(/[*?"<>|:]/g, '').replace(/[\\/:]/g, '-');
};

(async () => {
  for (const { url, criterion } of urls) {
    assert(isValidURL(url), `Invalid URL: ${url}`);

    let browser;
    let results;
    try {
      // Setup Puppeteer
      browser = await puppeteer.launch();

      // Get new page
      const page = await browser.newPage();
      await page.goto(url);

      // Inject and run axe-core
      const handle = await page.evaluateHandle(`
        // Inject axe source code
        ${axeCore.source}
        // Run axe
        axe.run()
      `);

      // Get the results from `axe.run()`.
      results = await handle.jsonValue();

      // Check if results and violations exist
      if (results && results.violations) {
        const formattedViolations = results.violations.map(violation => {
          const wcagCriteria = extractWcagCriteria(violation.tags);
          return wcagCriteria[0] !== 'N/A' ? violation.nodes.map(node => ({
            issueName: violation.description,
            wcagTags: wcagCriteria,
            html: node.html
          })) : [];
        }).flat();

        // Create results directory
        const resultsDir = path.join(__dirname, 'results');
        if (!fs.existsSync(resultsDir)) {
          fs.mkdirSync(resultsDir);
        }

        // Sanitize criterion name for folder creation
        const sanitizedCriterion = sanitizeFolderName(criterion);

        // Create subfolder for the WCAG criterion
        const criterionDir = path.join(resultsDir, sanitizedCriterion);
        if (!fs.existsSync(criterionDir)) {
          fs.mkdirSync(criterionDir);
        }

        const fileName = urlToFileName(url);
        fs.writeFileSync(path.join(criterionDir, fileName), JSON.stringify(formattedViolations, null, 2));

        console.log(`Formatted Violations for ${url} saved to ${fileName} in ${sanitizedCriterion}`);
      } else {
        console.log(`No violations found or error in results for ${url}`);
      }

      // Destroy the handle & return axe results.
      await handle.dispose();
    } catch (err) {
      console.error(`Error running axe-core on ${url}:`, err.message);
    } finally {
      if (browser) {
        await browser.close();
      }
    }
  }
})();



