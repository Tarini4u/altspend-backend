from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request, status
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from dynamic_scraper import get_product_audit_details, close_browser
import traceback
import sys
import asyncio
import re  # 🎯 FIXED: Added missing regex engine import

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Let the app run smoothly...
    yield
    # Clean up the global persistent browser instance upon server shutdown/restart
    await close_browser()

app = FastAPI(title="AltSpend Core Engine", lifespan=lifespan)

# Allow Cross-Origin Requests safely from both localhost and your live domains
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ProductAuditRequest(BaseModel):
    url: str

@app.get("/")
def check_status():
    return {"status": "online"}

def run_scraper_in_worker_thread(url: str):
    """
    Creates a pristine, isolated event loop on a separate native thread
    where WindowsProactorEventLoopPolicy can be applied without Uvicorn interference.
    """
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    # Run the async crawler task inside a brand new, clean loop context
    return asyncio.run(get_product_audit_details(url))

@app.post("/api/v1/audit")
async def audit_checkout_link(request: Request):  # Accepts raw Request stream
    try:
        # Read the raw request body as text bytes, then convert it to a clean UTF-8 string
        raw_body = await request.body()
        body_str = raw_body.decode("utf-8")
        
        # If the request came from your Swagger UI/docs, it might look like: {"url": "..."}
        if body_str.startswith("{") and "url" in body_str:
            import json
            try:
                # Clean up any literal backslash newlines if it was encoded awkwardly
                body_str = body_str.replace("\n", " ").replace("\r", " ")
                payload_data = json.loads(body_str)
                target_url = payload_data.get("url", "").strip()
            except Exception:
                # Fallback extraction using basic regex if JSON decoding still stumbles
                match = re.search(r'"url"\s*:\s*"([^"]+)"', body_str)
                target_url = match.group(1).strip() if match else body_str
        else:
            # If it's a direct clean text string dump, just use it straight away
            target_url = body_str.strip()
            
        # Remove any lingering internal physical newline/carriage return characters
        target_url = target_url.replace("\n", " ").replace("\r", " ")

        # Offload execution entirely to your isolated background thread worker
        result = await asyncio.to_thread(run_scraper_in_worker_thread, target_url)
        
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