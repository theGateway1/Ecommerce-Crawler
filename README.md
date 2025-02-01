# E-Commerce Product Crawler
This crawler is designed to extract product URLs from e-commerce websites. It leverages Playwright for asynchronous web scraping and efficiently handles various website structures. The scraper follows a structured approach to detect product links, ensuring scalability, robustness, and performance.

## Product Link Detection
The crawler follows a 5 step process to identify product URLs, and deals with the situation where home page (seed URL) only contains catalogue links.

### Step 1: Handle Popups and Notifications
- Detects and interacts with popups (e.g., cookie consent, notifications) by scanning for buttons with labels like "Accept," "Agree," or "Allow."
- Closes popups before proceeding with further scraping.

### Step 2: Extract Product Links from the Seed URL
- Collects all `<a>` tags on the page.
- Checks if the links match common product URL patterns such as:
  - `/p/`, `/product/`, `/products/`, `/dp/`
  - Query parameters: `?prodId=`, `?skuId=`, `?productId=`, `?pid=`
- Validates the extracted links to ensure they belong to the seed domain.

### Step 3: Extract Category Links
- Many ecommerce sites only contain catalogues on the home page instead of products, this crawler handles that too.
- It identifies category pages that might contain product listings.
- Looks for links with common category indicators: `/collections/`, `/category/`. Validates category links to filter out external sites.
- If URL does not match this pattern, it moves to step 4.

### Step 4: Discover Dynamically Loaded Categories
- Scans for navigation items (`<li>`) with labels like "Men," "Women," "Kids," "Beauty."
- Simulates user interactions (hovering or clicking) to reveal hidden menus.
- Extracts links from dropdown menus.

### Step 5: Visit Category Pages to Extract More Product Links (Infinite scrolling)
- Iterates through extracted category pages.
- Scrolls through pages to trigger dynamically loaded content - The number of times to scroll on a particular page can be input by the user.
- Repeats product URL extraction for newly loaded content.

### Scalability
- The crawler crawls multiple pages parallelly.
- It limits concurrent tasks using a semaphore to optimize resource usage.
- It writes product URL to JSON file incrementally, as soon as it is done finding given number of product URLs for a given site, it appends it to the output file.


## Usage
1. Install dependencies:
   ```bash
   pip install playwright aiofiles
   playwright install
   ```
2. Run the script:
   ```bash
   python crawler.py
   ```
3. The results will be stored in `product_urls.json`.


