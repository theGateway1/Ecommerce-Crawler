from playwright.async_api import async_playwright
import json
import asyncio
import os
from urllib.parse import urlparse
SEMAPHORE_LIMIT = 10  #Limit number of concurrent tasks to 10
MAX_PRODUCT_URLS_PER_SEED_URL = 20
import aiofiles
seed_urls = ['https://www.zara.com', 'https://www.westside.com', 'https://nefsfinds.com', 'https://outcasts.in', 'https://freakins.com', 'https://selcouth.co.in', 'https://www.houseofsal.com', 'https://www.virgio.com', 'https://lazostore.in', 'https://tagthelabel.in', 'https://blushade.in', 'https://girlsdontdressforboys.com', 'https://www.summersomewhereshop.com', 'https://sagebymala.com', 'https://thehouseofrare.com', 'https://www.snitch.co.in', 'https://www.bonkerscorner.com', 'https://offduty.in']

#Filter external site links 
def is_valid_link(site_url, full_url):
    parsed_site_url = urlparse(site_url)
    allowed_domain = parsed_site_url.netloc.lstrip("www.")  # Remove "www."

    parsed_url = urlparse(full_url)
    current_domain = parsed_url.netloc.lstrip("www.") 

    return current_domain == allowed_domain  # Compare base domains


async def extract_category_urls(elements, category_links, site_url, dialog_box_found=False):
    for element in elements:
        href = await element.get_attribute("href")
        
        if href and (dialog_box_found or any(keyword in href for keyword in ["/collections/", "/category/"])):
            
            full_url = href if href.startswith("http") else site_url + href
            if(is_valid_link(site_url, full_url)):
                category_links.add(full_url)


async def extract_product_urls_helper(elements, product_urls, page, site_url, seed_level=False):
    #Check if the product links follow common URL patterns
    for element in elements:
        if len(product_urls) >= MAX_PRODUCT_URLS_PER_SEED_URL:
            return 

        href = await element.get_attribute("href")
        if href and any(keyword in href for keyword in ["/p/", "/product/", "/products/", "/dp/", "?prodId=", "?skuId=", "?productId=", "?pid="]): 
            full_url = href if href.startswith("http") else site_url + href
            if(is_valid_link(site_url, full_url)):
                product_urls.add(full_url)

    #Check if there is a div with class that describes it contains products
    if(not seed_level):
        product_containers = await page.query_selector_all("[class*='product-groups']")
        
        for container in product_containers:
            # Get all <a> elements inside the product container
            links = await container.query_selector_all("a")

            for link in links:
                if len(product_urls) >= MAX_PRODUCT_URLS_PER_SEED_URL:
                    return 

                href = await link.get_attribute("href")
                # Filter out image/pdf links
                if href and not any(ext in href for ext in [".jpg", ".png", ".jpeg", ".gif", ".webp", ".pdf"]):  
                    full_url = href if href.startswith("http") else site_url + href
                    if(is_valid_link(site_url, full_url)):
                        product_urls.add(full_url)


# Get category links that are loaded dynamically (clicking/hovering)
async def load_category_links_dynamically(page, category_links, site_url):
    category_items = await page.query_selector_all("li")  # Select all list item elements
    for item in category_items:
        item_text = (await item.inner_text()).strip().lower()
        if any(keyword == item_text for keyword in ["men", "man", "woman", "women", "kids", "beauty", "view more", "others"]):
            try:
                if not await item.is_visible():
                    continue  # Skip if not visible
                await item.hover(timeout=5000)  # Shorter timeout to avoid long waits
                await asyncio.sleep(2)  # Allow dropdown to appear

                if await item.is_enabled():
                    dialog_box = await page.query_selector("div[role='dialog'], ul.dropdown, div.menu") 
                    if dialog_box:
                        elements = await dialog_box.query_selector_all("a")  # Select only links inside this box
                    else:
                        elements = await page.query_selector_all("a")  # Fallback: Get all links if no specific dialog is found

                    await extract_category_urls(elements, category_links, site_url, dialog_box)
                    
            except Exception as e:
                print(f"Skipping {site_url} due to error: {e}")
            

def convert_to_json():
    try:
        jsonl_file = "product_urls.jsonl"
        json_file = "product_urls.json"

        # Read JSONL and convert to a structured JSON object
        data = []

        with open(jsonl_file, "r") as f:
            for line in f:
                data.append(json.loads(line.strip()))  # Load each line as a JSON object

        # Convert the list of JSON objects into a single structured dictionary
        merged_data = {key: value for entry in data for key, value in entry.items()}

        # Save as JSON
        with open(json_file, "w") as f:
            json.dump(merged_data, f, indent=4)
        
        os.remove(jsonl_file)

    except Exception as e:
        print(f"Error occured {e}")


async def extract_product_urls(site_url, browser, max_scrolls=5, semaphore=None):
    async with semaphore:  # Limit concurrency    
        try:
            page = await browser.new_page()
            await page.goto(site_url, timeout=60000)
            await asyncio.sleep(5)  # Allow time for page elements to load
            
            # Step 1: Handle popups like cookie consent and notifications
            try:
                accept_buttons = await page.query_selector_all("button")  # Select all buttons
                for button in accept_buttons:
                    button_text = (await button.inner_text()).strip().lower()
                    if "accept" in button_text or "agree" in button_text or "allow" in button_text or "go" in button_text:
                        await button.click()
                        await asyncio.sleep(2)  # Give time for popup to close
            except:
                print("No cookie or notification popup detected.")
            
            elements = await page.query_selector_all("a")  # Select all anchor tags

            # Step 2: Get product links present on seed URL
            product_urls = set()
            await extract_product_urls_helper(elements, product_urls, page, site_url, True)

            # Step 3: Get category links present on seed URL
            category_links = set()
            await extract_category_urls(elements, category_links, site_url)

            # Step 4: Additional category links might be loaded dynamically (clicking/hovering)
            await load_category_links_dynamically(page, category_links, site_url)

            #Step 5: At this point, if both category_links and product_links is empty, this site is most probably not an ecommerce site
            if(len(product_urls) == 0 and len(category_links) == 0):
                return []
        
            # Step 6: Visit each category and extract product links
            for category_url in category_links:
                if len(product_urls) >= MAX_PRODUCT_URLS_PER_SEED_URL:
                    break 

                print(f"Visiting category: {category_url}")
                await page.goto(category_url, timeout=60000)
                await asyncio.sleep(5)  # Allow page to load
                
                # Handle infinite scrolling
                for _ in range(max_scrolls):
                    await page.mouse.wheel(0, 2000)  # Scroll down
                    await asyncio.sleep(5)  # Wait for new products to load
                
                # Extract product links
                await extract_product_urls_helper(await page.query_selector_all("a"), product_urls, page, site_url)

            await page.close()
            print(f"URL: {site_url}: Found {len(product_urls)} product URLs")
            return list(product_urls)
        except Exception as e:
            print(f"Error processing {site_url}: {e}")
            return []

async def main(seed_urls):
    try:
        semaphore = asyncio.Semaphore(SEMAPHORE_LIMIT)  # Limit concurrent tasks
        async with async_playwright() as p:
            # These settings try to prevent bot detection
            browser = await p.chromium.launch(
                headless=True, 
                args=[
                    "--disable-blink-features=AutomationControlled",  # Prevents detection
                    "--disable-infobars",  # Remove automation flags
                    "--no-sandbox", 
                    "--disable-dev-shm-usage"  
                ]
            )
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                viewport={"width": 1280, "height": 800},  # Mimic a real user screen
                java_script_enabled=True,  # Ensure JS content loads
            )

            async def process_url(url):
                product_urls = await extract_product_urls(url, context, 5, semaphore=semaphore)
                output = {url: product_urls}
                
                # Append to file immediately after fetching URLs for a seed URL
                async with aiofiles.open("product_urls.jsonl", "a") as f:
                    await f.write(json.dumps(output) + "\n")
                print(f"Saved {len(product_urls)} product URLs for {url}")

            # Run all tasks concurrently with asyncio.gather
            tasks = [process_url(url) for url in seed_urls]
            await asyncio.gather(*tasks)
            
            await browser.close()
        print("Extraction complete. Converting file to JSON")
        convert_to_json()
        print("Operation complete. Results saved to product_urls.json")

    except Exception as e:
        print(f"Error occured: {e}")

if __name__ == "__main__":
    asyncio.run(main(seed_urls))
