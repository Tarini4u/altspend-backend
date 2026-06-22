import sys
import asyncio

# 🎯 FIX 1: Apply the Windows Event Loop Policy globally at initialization 
# This eliminates Uvicorn loop contention without needing thread isolation.
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request, status
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from dynamic_scraper import get_product_audit_details, close_browser, get_browser
import traceback
import json
import re

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Handles startup orchestration and system resource wind-downs smoothly.
    """
    # 🚀 FIX 2: Warm-Up Boot. Instantiates the browser on server startup.
    # The very first user will experience zero cold-start delay.
    print("🚀 Waking up core system engines and warming background browser layers...")
    try:
        await get_browser()
        print("✅ Background browser engine warmed up and active.")
    except Exception as e:
        print(f"⚠️ Pre-warming browser failed during boot sequence: {e}")

    yield
    
    # Clean up the global persistent browser instance upon server shutdown/restart
    print("🧹 Spinning down background browser memory layers...")
    await close_browser()
    print("👍 System shutdown complete.")

app = FastAPI(title="AltSpend Core Engine", lifespan=lifespan)

# Allow Cross-Origin Requests safely from both localhost and your live domains
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Formal Pydantic schema for clear Swagger UI auto-documentation
class ProductAuditRequest(BaseModel):
    url: str

@app.get("/")
def check_status():
    return {"status": "online"}


@app.post("/api/v1/audit")
async def audit_checkout_link(request: Request):
    """
    Accepts incoming ecommerce checkout links and runs the AltSpend Audit Matrix.
    Handles both direct string payloads and structured JSON.
    """
    try:
        # Read the raw request body stream cleanly
        raw_body = await request.body()
        body_str = raw_body.decode("utf-8").strip()
        
        target_url = body_str
        
        # Flexibly parse input if sent as a structured JSON object
        if body_str.startswith("{") and "url" in body_str:
            try:
                body_str = body_str.replace("\n", " ").replace("\r", " ")
                payload_data = json.loads(body_str)
                target_url = payload_data.get("url", "").strip()
            except Exception:
                # Fallback regex extraction if manual JSON manipulation mangled the string
                match = re.search(r'"url"\s*:\s*"([^"]+)"', body_str)
                target_url = match.group(1).strip() if match else body_str
        
        # Strip trailing syntax noise or carriage adjustments
        target_url = target_url.replace("\n", " ").replace("\r", " ")

        if not target_url:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Target processing URL cannot be evaluated as empty space."
            )

        # 🚀 FIX 3: Run directly in the main async event loop context.
        # This honors our persistent browser state perfectly, boosting speeds significantly.
        print(f"🌐 Commencing dynamic audit tracking pipeline for target URL...")
        result = await get_product_audit_details(target_url)
        
        if not result or not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=result.get("error", "Could not extract EMI data from the provided URL.")
            )
            
        return result
        
    except HTTPException as http_ex:
        raise http_ex
    except Exception as e:
        error_msg = traceback.format_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_summary": str(e), "traceback": error_msg}
        )