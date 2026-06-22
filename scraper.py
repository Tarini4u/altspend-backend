import requests
from bs4 import BeautifulSoup

def fetch_product_page(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-IN,en-GB;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1"
    }
    print("Requesting target URL...")
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            print("🎉 Success! Page fetched cleanly.")
            return response.text
        else:
            print(f"❌ Blocked or Failed. Status Code: {response.status_code}")
            return None
    except Exception as e:
        print(f"An error occurred: {e}")
        return None

# --- THE EXECUTION ZONE (Make sure this starts at the far left edge, no indentation!) ---
if __name__ == "__main__":
    # Paste your iPhone link here
    test_url = "https://www.amazon.in/Apple-iPhone-17e-256-GB/dp/B0GQVL6STN/ref=sr_1_1_sspa?crid=1I5O3TGM5ZW58&dib=eyJ2IjoiMSJ9.S5vjz7qXca0cgfARelOdOe44g7pHbRvUMMinTf394wpWHqqYVWxvTWI9tyOJh8oJyR1H2-5tP7SZO_gMFxyji7EaH4jNuUdonE5LU8A49d4bPsgrUu8sPmt2x8uIennrydq4CYw6WXSArlvm2i2X9MwRurCGMme9UWrz3X76Ejk3LCe56U3aOOJ6a7IrIEIRPtN9D6-s3qx3Aeyhzj8Fxh4V1VpsDb5SIgZg846-7D4.y8YT_1dw4PXfXgUd5kSUaSwG7B78I9m6SuJXk6AYFpY&dib_tag=se&keywords=iphone&qid=1781960120&sprefix=iphone%2Caps%2C363&sr=8-1-spons&aref=D2Qdjw89fR&sp_csd=d2lkZ2V0TmFtZT1zcF9hdGY&th=1"
    
    html_content = fetch_product_page(test_url)
    
    if html_content:
        soup = BeautifulSoup(html_content, "lxml")
        
        # 1. Verify Title
        title_element = soup.find(id="productTitle")
        if title_element:
            print(f"📊 Product: {title_element.get_text().strip()}")
        
        print("\n--- Digging for Financial Data ---")
        
        # 2. Extract the Deal Price
        price_element = soup.find("span", class_="a-price-whole")
        if price_element:
            raw_price = price_element.get_text().replace(",", "").replace(".", "").strip()
            print(f"💰 Current Platform Price: ₹{raw_price}")
        else:
            print("⚠️ Price block not found.")

        # --- (KEEP THE SAME FETCHING AND PRICE CODE ABOVE) ---

        # 3. Holistic Search for Indian Financial & Bank Arrays
        print("\n--- Running Global Financial Data Map Check ---")
        
        # We will scan all scripts and layout elements across the entire page tree
        found_any_bank = False
        target_keywords = ["hdfc", "icici", "sbi", "axis", "no cost emi", "emiplans"]
        
        # Let's see if there is another hidden JSON block anywhere else on the page
        for index, script in enumerate(soup.find_all("script")):
            script_text = script.string if script.string else ""
            if any(keyword in script_text.lower() for keyword in target_keywords):
                print(f"🎯 Pattern match found in Script block #{index}!")
                found_any_bank = True
                
                # Print a clean window around the keyword to analyze structural formatting
                for keyword in target_keywords:
                    pos = script_text.lower().find(keyword)
                    if pos != -1:
                        start = max(0, pos - 50)
                        end = min(len(script_text), pos + 150)
                        print(f"   ↳ Snippet around '{keyword}': ... {script_text[start:end].strip()} ...")
                        break
        
        if not found_any_bank:
            print("📋 Script matrices private. Checking layout document hooks for raw elements...")
            # Plan C: Let's inspect text wrappers that hold data-attributes or text blocks directly
            for elem in soup.find_all(attrs={"data-action": True}):
                if "emi" in str(elem.get("data-action")).lower():
                    print(f"⚓ Found dynamic layout action trigger element: {elem.name} -> {elem.get('data-action')}")
                    found_any_bank = True

        if not found_any_bank:
            print("ℹ️ Inline selectors clean. Page structure ready for asynchronous proxy-session requests.")