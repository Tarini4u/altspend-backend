from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from dynamic_scraper import get_product_audit_details, close_browser
import traceback
import sys
import asyncio

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
async def audit_checkout_link(payload: ProductAuditRequest):
    target_url = payload.url.strip()
    
    try:
        # Offload execution entirely to an isolated background thread worker
        result = await asyncio.to_thread(run_scraper_in_worker_thread, target_url)
        
        # If the scraping failed or returned empty records
        if not result or not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=result.get("error", "Could not extract EMI data from the provided URL. Ensure it is a valid product link.")
            )
            
        return result
        
    except HTTPException as http_ex:
        # Keep internal HTTP validations passing through cleanly
        raise http_ex
    except Exception as e:
        error_msg = traceback.format_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_summary": str(e), "traceback": error_msg}
        )