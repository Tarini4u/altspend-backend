import json
import re
import urllib.parse
from bs4 import BeautifulSoup
from curl_cffi import requests 

class ProductScraper:
    def __init__(self):
        self.generic_headers = {
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "accept-language": "en-US,en;q=0.9",
            "upgrade-insecure-requests": "1"
        }

    def identify_platform(self, url):
        if "amazon.in" in url.lower():
            return "amazon"
        elif "flipkart.com" in url.lower():
            return "flipkart"
        return None

    def resolve_keyword_to_url(self, keyword, default_platform="amazon"):
        """
        Takes raw text keywords, executes a lightweight headless marketplace search,
        and returns the canonical URL of the very first organic product listing.
        """
        if default_platform == "amazon":
            # Using standard URL encoding to guarantee safe query parameters
            encoded_keyword = urllib.parse.quote(keyword)
            search_url = f"https://www.amazon.in/s?k={encoded_keyword}"
            try:
                from playwright.sync_api import sync_playwright
                with sync_playwright() as p:
                    browser = p.chromium.launch(headless=True)
                    context = browser.new_context(
                        viewport={"width": 1280, "height": 800},
                        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                    )
                    page = context.new_page()
                    
                    # Intercept and block heavy images/media during search routing to optimize speed
                    page.route("**/*", lambda route: route.abort() if route.request.resource_type in ["image", "media", "font"] else route.continue_())
                    
                    page.goto(search_url, wait_until="domcontentloaded", timeout=15000)
                    
                    # Locate the first valid organic Amazon product link card
                    first_product_link = page.locator("a.a-link-normal.s-no-outline").first
                    href = first_product_link.get_attribute("href")
                    
                    browser.close()
                    
                    if href:
                        if href.startswith("/"):
                            return f"https://www.amazon.in{href}"
                        return href
            except Exception as e:
                print(f"⚠️ Keyword resolution pipeline failure: {e}")
        
        return None

    def scrape_product_meta(self, url):
        platform = self.identify_platform(url)
        if not platform:
            return {"success": False, "error": "Unsupported platform link."}

        # 🔀 HYBRID ROUTE 1: Amazon Execution Plane via Optimized Playwright Instance
        if platform == "amazon":
            return self._scrape_amazon_playwright(url)

        # 🔀 HYBRID ROUTE 2: Flipkart Static Engine Plane via Ultra-Fast curl_cffi
        return self._scrape_static_flipkart(url)

    def _scrape_amazon_playwright(self, url):
        """
        Executes an isolated, highly optimized headless browser transaction.
        Lazy-loads Playwright only on invocation to eliminate startup overhead for Flipkart.
        """
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return {"success": False, "error": "Playwright is not installed. Run 'pip install playwright'"}

        # 🎯 URL-Decoding Patch: Handle URL-encoded paths inside sponsored ad parameters (%2Fdp%2F)
        decoded_url = urllib.parse.unquote(url)
        asin_match = re.search(r'/dp/([A-Z0-9]{10})', decoded_url)
        if asin_match:
            url = f"https://www.amazon.in/dp/{asin_match.group(1)}"

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                
                context = browser.new_context(
                    viewport={"width": 1280, "height": 800},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                )
                page = context.new_page()

                # LATENCY OPTIMIZATION GRID: Intercept and drop heavy media requests
                def intercept_assets(route):
                    if route.request.resource_type in ["image", "media", "font", "stylesheet"]:
                        if route.request.resource_type == "stylesheet":
                            route.continue_()
                        else:
                            route.abort()
                    else:
                        route.continue_()

                page.route("**/*", intercept_assets)

                # Fetch and drop wait locks as soon as the DOM tree is loaded
                page.goto(url, wait_until="domcontentloaded", timeout=20000)
                
                # Structural safety sync: ensure the product title container is fully generated
                page.wait_for_selector("#productTitle", timeout=5000)

                dom_content = page.content()
                soup = BeautifulSoup(dom_content, 'html.parser')
                
                # 1. Extract Title
                title_el = soup.find(id="productTitle") or soup.find("span", {"id": "productTitle"})
                title = title_el.get_text().strip() if title_el else "Unknown Amazon Product"

                # 2. Extract Image
                image = None
                landing_img = soup.find(id="landingImage") or soup.find(id="imgBlkFront")
                if landing_img:
                    image = landing_img.get("src")
                    if landing_img.get("data-a-dynamic-image"):
                        try:
                            img_map = json.loads(landing_img.get("data-a-dynamic-image"))
                            if img_map: image = list(img_map.keys())[0]
                        except Exception: pass

                # 3. Extract Price via Active Browser DOM Selectors
                price = None
                price_selectors = [
                    "span.a-price-whole",
                    "span.apexPriceToPay span.a-offscreen",
                    "span.priceToPay",
                    "#priceblock_ourprice"
                ]
                
                for selector in price_selectors:
                    price_element = page.query_selector(selector)
                    if price_element:
                        text = price_element.text_content()
                        if text:
                            clean_p = re.sub(r'[^\d]', '', text.split(".")[0])
                            if clean_p and int(clean_p) > 0:
                                price = float(clean_p)
                                break

                browser.close()

                if not price:
                    return {"success": False, "error": "Could not extract price from active browser context.", "title": title}

                return {
                    "success": True,
                    "platform": "amazon",
                    "title": title,
                    "sticker_price": price,
                    "product_image": image
                }

        except Exception as e:
            return {"success": False, "error": f"Playwright Driver Error: {str(e)}"}

    def _scrape_static_flipkart(self, url):
        """
        Executes high-speed static fetch pattern for Flipkart. Zero browser overhead.
        """
        try:
            response = requests.get(url, headers=self.generic_headers, impersonate="chrome", timeout=15)
            if response.status_code != 200:
                return {"success": False, "error": f"Flipkart responded with status code {response.status_code}."}
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Title Isolation
            flipkart_title = soup.find("span", class_="VU-ZEz") or soup.find("h1")
            title = flipkart_title.get_text().strip() if flipkart_title else "Unknown Flipkart Product"
            
            # Image Isolation
            meta_image = soup.find("meta", property="og:image") or soup.find("meta", attrs={"name": "twitter:image"})
            image = meta_image.get("content") if meta_image else None
            
            # Fast Engine Regex Extraction
            price = None
            match = re.search(r'"value":\s*(\d{2,8})\.0', response.text)
            if match: 
                price = float(match.group(1))
            else:
                match_alt = re.search(r'"price":\s*(\d{2,8})', response.text)
                if match_alt: price = float(match_alt.group(1))

            if not price:
                return {"success": False, "error": "Could not isolate pricing inside static structural footprint."}

            return {
                "success": True,
                "platform": "flipkart",
                "title": title,
                "sticker_price": price,
                "product_image": image
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

# Test harness validation matrix
if __name__ == "__main__":
    scraper = ProductScraper()
    print("🤖 Testing raw text resolution pattern...")
    resolved_url = scraper.resolve_keyword_to_url("MacBook Neo 13")
    print(f"🔗 Resolved Raw Text to Live URL: {resolved_url}")