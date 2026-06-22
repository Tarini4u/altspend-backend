import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import re
import httpx
import json
import os

# ---- GLOBAL CONFIGURATION LOADER INTERFACE ----
def load_engine_config() -> dict:
    """Reads and parses the externalized platform configuration layout safely."""
    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Critical configuration engine canvas missing at: {config_path}")
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)

CONFIG = load_engine_config()

# ---- GLOBAL PERSISTENT BROWSER INSTANCE ENGINE ----
_playwright_instance = None
_global_browser = None

async def get_browser():
    global _playwright_instance, _global_browser
    if _global_browser is None:
        _playwright_instance = await async_playwright().start()
        _global_browser = await _playwright_instance.chromium.launch(headless=True)
    return _global_browser

async def close_browser():
    global _playwright_instance, _global_browser
    if _global_browser:
        await _global_browser.close()
        _global_browser = None
    if _playwright_instance:
        await _playwright_instance.stop()
        _playwright_instance = None


async def clean_and_resolve_url(user_input: str) -> str:
    url_pattern = r"(https?://[^\s]+)"
    match = re.search(url_pattern, user_input)
    processed_url = match.group(1).strip() if match else user_input.strip()
    
    if "amzn.in" in processed_url:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.head(processed_url)
            return str(response.url)
            
    return processed_url


async def get_product_audit_details(url: str) -> dict:
    """Fetches HTML data cleanly, extracts inline specs, and processes the AltSpend Audit Matrix."""
    target_url = await clean_and_resolve_url(url)
    base_price = 0.0
    detected_no_cost_plans = []
    
    b_set = CONFIG["browser_settings"]
    f_rules = CONFIG["financial_rules"]

    # =========================================================================
    # 🏎️ ROUTE A: FLIPKART ENGINE MATRIX (CONFIG DRIVEN)
    # =========================================================================
    if CONFIG["flipkart"]["domain_identifier"] in target_url.lower():
        fk_cfg = CONFIG["flipkart"]
        print("⏳ Executing config-driven interactive parsing for Flipkart context...")
        
        browser = await get_browser()
        context = await browser.new_context(
            user_agent=b_set["user_agent"],
            viewport=b_set["viewport"],
            locale=b_set["locale"]
        )
        page = await context.new_page()
        try:
            await page.goto(target_url, wait_until="domcontentloaded", timeout=b_set["navigation_timeout_ms"])
            await page.wait_for_timeout(b_set["render_delay_ms"]) 
            
            # --- STRATEGY 1: INDESTRUCTIBLE MULTI-TIER PRICE RESOLVER ---
            html_content = await page.content()
            soup = BeautifulSoup(html_content, "html.parser")
            
            meta_tag = soup.find("meta", property="og:price:amount") or soup.find("meta", attrs={"name": "twitter:data1"})
            if meta_tag:
                clean_meta = re.sub(r'[^\d.]', '', meta_tag.get("content", ""))
                if clean_meta:
                    base_price = float(clean_meta)
                    print(f"🎯 Extracted price from Metadata: ₹{base_price}")

            if base_price == 0.0:
                try:
                    json_ld_tags = soup.find_all("script", type="application/ld+json")
                    for tag in json_ld_tags:
                        if tag.string:
                            schema_data = json.loads(tag.string)
                            def extract_price(obj):
                                if isinstance(obj, dict):
                                    if "offers" in obj and isinstance(obj["offers"], dict) and "price" in obj["offers"]:
                                        return float(obj["offers"]["price"])
                                    if "price" in obj and isinstance(obj["price"], (int, float, str)):
                                        return float(re.sub(r'[^\d.]', '', str(obj["price"])))
                                    for k, v in obj.items():
                                        res = extract_price(v)
                                        if res: return res
                                elif isinstance(obj, list):
                                    for item in obj:
                                        res = extract_price(item)
                                        if res: return res
                                return None
                            found_price = extract_price(schema_data)
                            if found_price:
                                base_price = found_price
                                print(f"🎯 Extracted price from JSON-LD Schema: ₹{base_price}")
                                break
                except Exception:
                    pass

            if base_price == 0.0:
                price_strings = soup.find_all(string=re.compile(r'^₹\s*[\d,]+$'))
                for p_str in price_strings:
                    clean_text = re.sub(r'[^\d.]', '', p_str)
                    if clean_text:
                        potential_price = float(clean_text)
                        if potential_price > 1000:
                            base_price = potential_price
                            print(f"🎯 Extracted price via Class-Agnostic String Match: ₹{base_price}")
                            break

            if base_price == 0.0:
                for selector in fk_cfg["price_selectors"]:
                    price_element = soup.find("div", class_=selector.split(".")[-1])
                    if price_element:
                        clean_text = re.sub(r'[^\d.]', '', price_element.get_text())
                        if clean_text: 
                            base_price = float(clean_text)
                            print(f"🎯 Extracted price from explicit selector array: ₹{base_price}")
                            break

            # --- STRATEGY 2: INTERACT WITH THE EMI OVERLAY ---
            print("👆 Searching for Flipkart EMI plan trigger overlay via Config Arrays...")
            emi_trigger = None
            for trigger_sel in fk_cfg["emi_triggers"]:
                emi_trigger = await page.query_selector(trigger_sel)
                if emi_trigger:
                    break
            
            if emi_trigger:
                print(f"👆 Found working trigger structure. Simulating live click event...")
                await emi_trigger.scroll_into_view_if_needed()
                await emi_trigger.click()
                await page.wait_for_timeout(b_set["render_delay_ms"])  
            else:
                print("⚠️ No structural EMI plan drawer trigger could be verified on screen.")

            # --- STRATEGY 3: BI-DIRECTIONAL WINDOWED TEXT EXTRACTION ---
            page_text = await page.evaluate("() => document.body.innerText")
            lines = [line.strip() for line in page_text.split('\n') if line.strip()]
            
            for idx, line in enumerate(lines):
                matched_bank = None
                for b_name in fk_cfg["tracked_banks"]:
                    if b_name.lower() in line.lower():
                        matched_bank = b_name
                        break
                
                if matched_bank:
                    start_scan = max(0, idx - 4)
                    end_scan = min(len(lines), idx + 5)
                    
                    for scan_idx in range(start_scan, end_scan):
                        scan_line = lines[scan_idx]
                        tenure_match = re.search(r'(\d+)\s*(?:months|month|m\b)', scan_line, re.IGNORECASE)
                        if tenure_match:
                            months = int(tenure_match.group(1))
                            display_bank = f"{matched_bank} Bank" if "bank" not in matched_bank.lower() else matched_bank
                            
                            if not any(p["bank"] == display_bank and p["tenure_months"] == months for p in detected_no_cost_plans):
                                print(f"   ✅ Successfully Harvested Config Bank: {display_bank} ({months} Months)")
                                detected_no_cost_plans.append({
                                    "bank": display_bank,
                                    "tenure_months": months
                                })
        except Exception as dom_err:
            print(f"⚠️ Interactive Flipkart extraction layer encountered an exception: {dom_err}")
        finally:
            await page.close()
            await context.close()

    # =========================================================================
    # 📦 ROUTE B: AMAZON ENGINE MATRIX (CONFIG DRIVEN)
    # =========================================================================
    else:
        az_cfg = CONFIG["amazon"]
        print("🌐 Navigating to config-driven Amazon execution layer...")
        browser = await get_browser() 
        context = await browser.new_context(
            user_agent=b_set["user_agent"],
            viewport=b_set["viewport"]
        )
        page = await context.new_page()
        
        try:
            await page.goto(target_url, wait_until="domcontentloaded", timeout=b_set["navigation_timeout_ms"])
            
            for selector in az_cfg["price_selectors"]:
                price_element = await page.query_selector(selector)
                if price_element:
                    raw_price_text = await price_element.inner_text()
                    clean_text = re.sub(r'[^\d.]', '', raw_price_text)
                    if clean_text:
                        base_price = float(clean_text)
                        break

            print("👆 Locating config-defined Amazon 'EMI options' trigger...")
            emi_link = None
            for trigger_sel in az_cfg["emi_triggers"]:
                emi_link = await page.query_selector(trigger_sel)
                if emi_link:
                    break
            
            if emi_link:
                await emi_link.click()
                await page.wait_for_timeout(b_set["render_delay_ms"]) 

                popovers = await page.query_selector_all(".a-popover")
                visible_popover = None
                for pop in popovers:
                    if await pop.is_visible():
                        visible_popover = pop
                        break

                if visible_popover:
                    see_details_trigger = await visible_popover.query_selector("text=See details")
                    if not see_details_trigger:
                     see_details_trigger = await visible_popover.query_selector("text=see details")

                    if see_details_trigger:
                     print("👆 Amazon intermediate promo block intercepted. Exposing detailed matrix...")
                     await see_details_trigger.click()
                     await page.wait_for_timeout(1500)

                    for bank_item in az_cfg["tracked_banks"]:
                        try:
                            key = bank_item["key"]
                            search_term = bank_item["search"]
                            
                            bank_locator = page.locator(f".a-popover-content >> text={search_term}").first
                            if await bank_locator.count() == 0:
                                bank_locator = page.locator(f".a-popover-content >> text={key}").first

                            if await bank_locator.count() > 0 and await bank_locator.is_visible():
                                await bank_locator.scroll_into_view_if_needed()
                                await bank_locator.click()
                                await page.wait_for_timeout(700)
                                
                                updated_popover_text = await visible_popover.inner_text()
                                lines = [line.strip() for line in updated_popover_text.split('\n') if line.strip()]
                                
                                header_idx = -1
                                for idx, line in enumerate(lines):
                                    if search_term.lower() in line.lower() or (key.lower() in line.lower() and "card" in line.lower()):
                                        if "processing fee" not in line.lower() and "amazon pay" not in line.lower():
                                            header_idx = idx
                                            break
                                
                                if header_idx != -1:
                                    for offset in range(1, 14):
                                        if header_idx + offset >= len(lines):
                                            break
                                        
                                        future_line = lines[header_idx + offset]
                                        if any(b["key"].lower() in future_line.lower() and "card" in future_line.lower() for b in az_cfg["tracked_banks"] if b["key"] != key):
                                            break
                                        
                                        tenure_match = re.search(r'\b(\d+)\s*(?:months|month|m\b)', future_line, re.IGNORECASE)
                                        if tenure_match:
                                            months = int(tenure_match.group(1))
                                            if months in [3, 6, 9, 12, 18, 24, 36]:
                                                display_bank = f"{key} Card" if key.lower() == "sbi" else f"{key} Bank"
                                                if not any(p["bank"] == display_bank and p["tenure_months"] == months for p in detected_no_cost_plans):
                                                    print(f"   ✅ Successfully Scraped Config Bank: {display_bank} ({months} Months)")
                                                    detected_no_cost_plans.append({"bank": display_bank, "tenure_months": months})
                        except Exception as accordion_err:
                            print(f"   ⚠️ Could not interact with accordion block for {bank_item['key']}: {accordion_err}")
            else:
                print("⚠️ Config 'EMI options' text link could not be matched inside current viewport.")
                
        except Exception as e:
            print(f"⚠️ Interactive collection session encountered an exception: {e}")
        finally:
            await page.close()
            await context.close()

    # =========================================================================
    # 🧮 SYSTEM ADAPTIVE CALCULATIONS (CONFIG DRIVEN)
    # =========================================================================
    if base_price == 0.0:
        return {"success": False, "error": "Could not resolve dynamic baseline price structure."}

    if not detected_no_cost_plans:
        detected_no_cost_plans = CONFIG["system_fallbacks"]

    audited_plans = []
    max_savings = base_price * f_rules["max_savings_discount_factor"]

    for plan in detected_no_cost_plans:
        months = plan["tenure_months"]
        monthly_emi_nominal = round(base_price / months, 2)
        
        if max_savings > f_rules["max_savings_threshold"] and months >= 6:
            calculated_interest = (max_savings / 9) * months
        else:
            annual_rate = f_rules["annual_fallback_interest_rate"]
            estimated_discount_factor = (annual_rate * (months + 1)) / (2 * 12)
            calculated_interest = base_price * estimated_discount_factor / (1 + estimated_discount_factor)

        hidden_gst = calculated_interest * f_rules["gst_rate"]
        processing_fee_with_gst = f_rules["standard_processing_fee"] * (1 + f_rules["gst_rate"])
        true_cost = base_price + hidden_gst + processing_fee_with_gst
        premium_paid = true_cost - base_price

        audited_plans.append({
            "bank": plan["bank"],
            "tenure_months": months,
            "nominal_monthly_emi": monthly_emi_nominal,
            "upfront_marketplace_discount": round(calculated_interest, 2),
            "hidden_bank_interest_gst": round(hidden_gst, 2),
            "processing_fee_inclusive_gst": round(processing_fee_with_gst, 2),
            "true_net_out_of_pocket": round(true_cost, 2),
            "real_premium_over_sticker": round(premium_paid, 2)
        })

    return {
        "success": True,
        "sticker_price": base_price,
        "audited_emi_options": audited_plans
    }
    

if __name__ == "__main__":
    async def main():
        test_url = "https://www.amazon.in/Glen-BLDC-Intelligent-Filterless-Selena/dp/B0FBWVWQXZ/ref=sr_1_1_sspa?crid=2Z3DJH8LKGTYQ&dib=eyJ2IjoiMSJ9.7cGY7uOeukYeeeDjX1IVBg3NgwBX4ipoGgXxnDdcG4_zlCpcm1ghVQ-yC1u2qcdT-ks-a05GFvK6jJF86h16dmgblEVWlpnb5vFksJSAQaOFT9F3bzkfTs-GvcFRbTmhTvpfYoL_dO5LSUbdM9ubjsU4GwcTDXnGIraJnmc-47SKydsvwrXmCzcrW5r8HM8aydY4mUGcirV2upSt9DnY0AvQlVN99lh2eU8-C94WSto.Ig5wryDl8QiJDIThkUv_2Ut4ioroIJi7rfFU4_1JSYY&dib_tag=se&keywords=chimney%2Bfor%2Bkitchen%2B90cm&qid=1782139179&sprefix=chimne%2Caps%2C359&sr=8-1-spons&aref=1JwCQqpfme&sp_csd=d2lkZ2V0TmFtZT1zcF9hdGY&th=1"
        print("🚀 Starting local live configuration-driven audit test run...")
        try:
            result = await get_product_audit_details(test_url)
            print("\n✅ Execution Finished Successfully via configuration boundaries!\n")
            print(json.dumps(result, indent=2, ensure_ascii=False))
        except Exception as e:
            print(f"\n❌ Runtime test script caught an uncaught exception: {e}")
        finally:
            await close_browser()

    asyncio.run(main())