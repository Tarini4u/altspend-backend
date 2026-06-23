import json
import math
import re
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dynamic_scraper import ProductScraper

app = FastAPI(title="Altspend Core Fintech Engine API")
scraper = ProductScraper()

# Load central banking configurations once on engine startup
with open("config.json", "r") as f:
    config_data = json.load(f)

class SearchRequest(BaseModel):
    # Keeping the field name as 'url' to prevent breaking your current frontend payload
    url: str 

def calculate_reducing_emi(principal, annual_rate, months):
    """Standard regulatory reducing balance EMI formula execution"""
    # 🎯 STEP 0: Zero-rate guard condition to prevent ZeroDivisionError on No-Cost EMI
    if annual_rate == 0:
        return round(principal / months, 2)

    r = (annual_rate / 12) / 100
    emi = (principal * r * math.pow(1 + r, months)) / (math.pow(1 + r, months) - 1)
    return round(emi, 2)

@app.post("/api/audit-product")
async def audit_product_link(request: SearchRequest):
    raw_input = request.url.strip()
    
    # 🎯 STEP 1: Detect Input Type (URL vs Raw Text Keyword)
    is_url = re.match(r'^https?://', raw_input, re.IGNORECASE)
    
    if is_url:
        target_url = raw_input
    else:
        # User typed raw text! Resolve it to the top marketplace match automatically.
        print(f"🔍 Keyword detected: '{raw_input}'. Resolving to top marketplace match...")
        target_url = scraper.resolve_keyword_to_url(raw_input, default_platform="amazon")
        
        if not target_url:
            raise HTTPException(
                status_code=404, 
                detail=f"Could not find any matching products for '{raw_input}' on partner platforms."
            )

    # 🎯 STEP 2: Extract metadata components from the resolved target URL
    meta = scraper.scrape_product_meta(target_url)
    if not meta or not meta["success"]:
        raise HTTPException(status_code=422, detail=meta.get("error", "Extraction Failure"))

    platform = meta["platform"]
    price = meta["sticker_price"]
    
    # 🎯 STEP 3: Fetch corresponding configuration map rules
    platform_rules = config_data["platforms"][platform]
    supported_banks = platform_rules["supported_banks"]
    rates_matrix = config_data["interest_rates_p_a"]

    audited_emi_options = []

    # 🎯 STEP 4: Run programmatic financial loops
    for bank in supported_banks:
        if bank not in rates_matrix:
            continue
        
        # Format display name cleanly depending on provider type
        bank_display_name = "Bajaj Finserv EMI Card" if bank == "BAJAJ" else f"{bank} Bank"
        
        for tenure_str, annual_rate in rates_matrix[bank].items():
            tenure_months = int(tenure_str)
            
            # Compute raw calculations dynamically
            monthly_emi = calculate_reducing_emi(price, annual_rate, tenure_months)
            total_repayment = monthly_emi * tenure_months
            total_interest_charged = max(0.00, total_repayment - price)
            
            # Incorporate processing fees and compounding GST rules
            est_processing_fee = round((price * config_data["global_processing_fee_percent"]) / 100, 2)
            gst_on_charges = round((total_interest_charged + est_processing_fee) * config_data["gst_rate"], 2)
            
            true_net_out_of_pocket = round(total_repayment + est_processing_fee + gst_on_charges, 2)
            real_premium_over_sticker = round(true_net_out_of_pocket - price, 2)

            audited_emi_options.append({
                "bank": bank_display_name,
                "tenure_months": tenure_months,
                "nominal_monthly_emi": monthly_emi,
                "upfront_marketplace_discount": 0.00, 
                "hidden_bank_interest_gst": gst_on_charges,
                "processing_fee_inclusive_gst": est_processing_fee,
                "true_net_out_of_pocket": true_net_out_of_pocket,
                "real_premium_over_sticker": real_premium_over_sticker
            })

    return {
        "success": True,
        "platform_display_name": platform_rules["display_name"],
        "title": meta["title"],
        "sticker_price": price,
        "product_image": meta["product_image"],
        "resolved_source_url": target_url,  # Returns the actual product link found back to the UI
        "exclusive_card_perks": platform_rules["exclusive_cards"],
        "audited_emi_options": audited_emi_options
    }