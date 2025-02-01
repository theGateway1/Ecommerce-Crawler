from playwright.async_api import async_playwright
import json
import asyncio
from urllib.parse import urlparse

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
                # print(full_url)
                category_links.add(full_url)


async def extract_product_urls_helper(elements, product_urls, page, site_url, seed_level=False):
    #Check if the product links follow common URL patterns
    for element in elements:
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
                href = await link.get_attribute("href")
                # Filter out image/pdf links
                if href and not any(ext in href for ext in [".jpg", ".png", ".jpeg", ".gif", ".webp", ".pdf"]):  
                    full_url = href if href.startswith("http") else site_url + href
                    if(is_valid_link(site_url, full_url)):
                        print(full_url + '\n')
                        product_urls.add(full_url)


# Get category links that are loaded dynamically (clicking/hovering)
async def load_category_links_dynamically(page, category_links):
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
                    dialog_box = await page.query_selector("div[role='dialog'], ul.dropdown, div.menu")  # Adjust selector as needed
                    if dialog_box:
                        print("Dialog box found")
                        elements = await dialog_box.query_selector_all("a")  # Select only links inside this box
                    else:
                        elements = await page.query_selector_all("a")  # Fallback: Get all links if no specific dialog is found

                    await extract_category_urls(elements, category_links, site_url, dialog_box)
                    
            except Exception as e:
                print(f"Skipping item due to error: {e}")  # Debugging message
            

async def extract_product_urls(site_url, max_scrolls=5):
    async with async_playwright() as p:
        #TODO: Set headless to True
        browser = await p.chromium.launch(headless=False)  # Set to True for headless mode
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
        await load_category_links_dynamically(page, category_links)

        #Step 5: At this point, if both category_links and product_links is empty, this site is most probably not an ecommerce site
        if(len(product_urls) == 0 and len(category_links) == 0):
            return []
    
        # Step 6: Visit each category and extract product links
        for category_url in category_links:
            print(f"Visiting category: {category_url}")
            await page.goto(category_url, timeout=60000)
            await asyncio.sleep(5)  # Allow page to load
            
            # Handle infinite scrolling
            for _ in range(max_scrolls):
                await page.mouse.wheel(0, 2000)  # Scroll down
                await asyncio.sleep(5)  # Wait for new products to load
            
            # Extract product links
            await extract_product_urls_helper(await page.query_selector_all("a"), product_urls, page, site_url)
            print(product_urls)

            #TODO: Remove this
            if(len(product_urls) >= 30):
                break
        await browser.close()
    
    return list(product_urls)

if __name__ == "__main__":
    site_url = "https://zara.com"  
    product_links = asyncio.run(extract_product_urls(site_url))
    
    # Save results
    # with open("product_urls.json", "w") as f:
    #     json.dump(product_links, f, indent=4)

    with open("product_links.txt", "w") as f:
        for link in product_links:
            f.write(link + "\n")
    
    print(f"Extracted {len(product_links)} product URLs. Saved to product_urls.txt")


#TODO:
#1. Support multiple URLs given at once - parallelly
#2. Visit product page and get URLs of products on that page
