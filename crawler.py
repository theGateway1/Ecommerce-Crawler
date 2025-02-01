from playwright.async_api import async_playwright
import json
import asyncio


async def extract_category_urls(elements, category_links):
    for element in elements:
        href = await element.get_attribute("href")
        if href and "/collections/" in href:  
            category_links.add(href if href.startswith("http") else site_url + href[1:])

async def extract_product_urls_helper(elements, product_urls, page):
    for element in elements:
        href = await element.get_attribute("href")
        if href and any(keyword in href for keyword in ["/p/", "/product/", "/products/", "/dp/", "?prodId=", "?skuId=", "?productId=", "?pid="]): 
            product_urls.add(href if href.startswith("http") else site_url + href[1:])

    #Check if there is a div with class that describes it contains products
    product_containers = await page.query_selector_all("[class*='products'], [class*='product-listing'], [class*='products-grid'], [class*='product-wrapper'], [class*='product-groups']")
    
    for container in product_containers:
        # Get all <a> elements inside the product container
        links = await container.query_selector_all("a")

        for link in links:
            href = await link.get_attribute("href")
            # Filter out image links
            if href and not any(ext in href for ext in [".jpg", ".png", ".jpeg", ".gif", ".webp"]):  
                full_url = href if href.startswith("http") else site_url + href
                product_urls.add(full_url)
                print(full_url)


# Get category links that are loaded dynamically (clicking/hovering)
async def load_category_links_dynamically(page, category_links):
    category_items = await page.query_selector_all("li")  # Select all list item elements
    for item in category_items:
        item_text = (await item.inner_text()).strip().lower()
        if any(keyword == item_text for keyword in ["men", "man", "woman", "women", "kids", "beauty", "all", "view more", "others"]):
            try:
                if not await item.is_visible():
                    continue  # Skip if not visible
                await item.scroll_into_view_if_needed()
                await asyncio.sleep(1)  # Allow time for scrolling
                await item.hover(timeout=5000)  # Shorter timeout to avoid long waits
                await asyncio.sleep(2)  # Allow dropdown to appear
                
                if await item.is_enabled():
                    await item.click()
                    await asyncio.sleep(2)  # Allow subcategories to load
                    dialog_box = await page.query_selector("div[role='dialog'], ul.dropdown, div.menu")  # Adjust selector as needed
                    if dialog_box:
                        print("Dialog box found")
                        elements = await dialog_box.query_selector_all("a")  # Select only links inside this box
                    else:
                        elements = await page.query_selector_all("a")  # Fallback: Get all links if no specific dialog is found
                    for element in elements:
                        href = await element.get_attribute("href")
                        if href and (dialog_box or any(keyword in href for keyword in ["/collections/", "/category/"])):
                            print(href)
                            category_links.add(href if href.startswith("http") else site_url + href)
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
        await extract_product_urls_helper(elements, product_urls, page)

        # Step 3: Get category links present on seed URL
        category_links = set()
        await extract_category_urls(elements, category_links)
        
        with open("category_links.txt", "w") as f:
            for link in category_links:
                f.write(link + "\n")

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
            
            # Step 5: Handle infinite scrolling
            for _ in range(max_scrolls):
                await page.mouse.wheel(0, 2000)  # Scroll down
                await asyncio.sleep(5)  # Wait for new products to load
            
            # Step 6: Extract product links
            await extract_product_urls_helper(await page.query_selector_all("a"), product_urls, page)
            print(product_urls)

            #TODO: Remove this
            if(len(product_urls) >= 50):
                break
        await browser.close()
    
    return list(product_urls)

if __name__ == "__main__":
    site_url = "https://blushade.in/"  
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
