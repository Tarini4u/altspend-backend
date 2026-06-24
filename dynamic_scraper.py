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
        # Centralized ScraperAPI Token Access
        self.scraper_api_key = "757d022130ae8d2768cbdaf4653cd3d6"

    def identify_platform(self, url):
        if "amazon.in" in url.lower():
            return "amazon"
        elif "flipkart.com" in url.lower():
            return "flipkart"
        return None

    def resolve_keyword_to_url(self, keyword, default_platform="amazon"):
        """
        Takes raw text keywords, executes a proxy-backed search request,
        and returns the canonical URL of the first organic Amazon product listing.
        """
        if default_platform == "amazon":
            encoded_keyword = urllib.parse.quote(keyword)
            search_url = f"https://www.amazon.in/s?k={encoded_keyword}"
            
            # Route keyword search requests through proxy to avoid Amazon's search WAF barriers
            proxy_url = f"http://api.scraperapi.com?api_key={self.scraper_api_key}&url={urllib.parse.quote(search_url)}&premium=true"
            
            try:
                print(f"🔍 Querying Amazon Search Index via Proxy for: '{keyword}'...")
                response = requests.get(proxy_url, timeout=30)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    # Target primary Amazon search card link classes
                    link_el = soup.select_one("a.a-link-normal.s-no-outline")
                    if not link_el:
                        link_el = soup.select_one(".s-main-slot .s-result-item a.a-link-normal")
                        
                    if link_el:
                        href = link_el.get("href")
                        if href:
                            if href.startswith("/"):
                                return f"https://www.amazon.in{href}"
                            return href
            except Exception as e:
                print(f"⚠️ Keyword resolution proxy pipeline failure: {e}")
        
        return None

    def scrape_product_meta(self, url):
        platform = self.identify_platform(url)
        if not platform:
            return {"success": False, "error": "Unsupported platform link."}

        # 🔀 ROUTE 1: Amazon Execution Plane via Residential Proxy Network
        if platform == "amazon":
            return self._scrape_amazon_proxy(url)

        # 🔀 ROUTE 2: Flipkart Static Engine Plane via Ultra-Fast curl_cffi (UNTOUCHED)
        return self._scrape_static_flipkart(url)

    def _scrape_amazon_proxy(self, url):
        """
        Bypasses Amazon structural blocks using ScraperAPI residential routes.
        Completely eliminates Playwright driver execution overhead.
        """
        # URL-Decoding Patch: Handle URL-encoded paths inside tracking structures
        decoded_url = urllib.parse.unquote(url)
        asin_match = re.search(r'/dp/([A-Z0-9]{10})', decoded_url)
        canonical_url = f"https://www.amazon.in/dp/{asin_match.group(1)}" if asin_match else url

        # Build execution proxy gateway endpoint
        proxy_url = f"http://api.scraperapi.com?api_key={self.scraper_api_key}&url={urllib.parse.quote(canonical_url)}&premium=true"

        try:
            print(f"🚀 Dispatching Amazon product fetch through clean residential network edge...")
            response = requests.get(proxy_url, timeout=30)
            
            if response.status_code != 200:
                return {"success": False, "error": f"ScraperAPI proxy rejected with code {response.status_code}"}

            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 1. Extract Title Block
            title_el = soup.find(id="productTitle") or soup.find("span", {"id": "productTitle"})
            title = title_el.get_text().strip() if title_el else "Unknown Amazon Product"

            # 2. Extract Image Asset
            image = None
            landing_img = soup.find(id="landingImage") or soup.find(id="imgBlkFront")
            if landing_img:
                image = landing_img.get("src")
                if landing_img.get("data-a-dynamic-image"):
                    try:
                        img_map = json.loads(landing_img.get("data-a-dynamic-image"))
                        if img_map: 
                            image = list(img_map.keys())[0]
                    except Exception: 
                        pass

            # 3. Extract Price via Multiple Target Tree Nodes
            price = None
            price_selectors = [
                "span.a-price-whole",
                "span.apexPriceToPay span.a-offscreen",
                "span.priceToPay",
                "#priceblock_ourprice"
            ]
            
            for selector in price_selectors:
                price_element = soup.select_one(selector)
                if price_element:
                    text = price_element.get_text()
                    if text:
                        clean_p = re.sub(r'[^\d]', '', text.split(".")[0])
                        if clean_p and int(clean_p) > 0:
                            price = float(clean_p)
                            break

            if not price:
                return {"success": False, "error": "Failed to extract sticker price from proxy payload.", "title": title}

            return {
                "success": True,
                "platform": "amazon",
                "title": title,
                "sticker_price": price,
                "product_image": image
            }

        except Exception as e:
            return {"success": False, "error": f"Proxy Pipeline Driver Error: {str(e)}"}

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

if __name__ == "__main__":
    scraper = ProductScraper()
    print("🤖 Executing validation engine test pass...")
    resolved_url = scraper.resolve_keyword_to_url("Primebook Laptop")
    print(f"🔗 Cleanly Resolved Search Asset To: {resolved_url}")