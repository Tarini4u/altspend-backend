from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from dynamic_scraper import get_product_audit_details
import traceback
import sys
import asyncio

app = FastAPI(title="AltSpend Core Engine")

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
        return result
    except Exception as e:
        error_msg = traceback.format_exc()
        raise HTTPException(
            status_code=500,
            detail={"error_summary": str(e), "traceback": error_msg}
        )
    try:
        # Offload execution entirely to an isolated background thread worker
        result = await asyncio.to_thread(run_scraper_in_worker_thread, target_url)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Could not extract EMI data from the provided URL. Ensure it is a valid product checkout link."
            )
        return result
    except Exception as e:
        # Clean logging for production environments
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Scraper execution failed: {str(e)}"
        )