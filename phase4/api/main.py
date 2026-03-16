from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from service.service import RecommendationService
from recommender.engine import get_metadata as engine_get_metadata
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("zomato.api")

app = FastAPI(title="Zomato-AI Restaurant Service")

# Add CORS middleware to allow requests from the frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify the actual frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

service = RecommendationService()

class RecommendationRequest(BaseModel):
    user_message: str
    session_id: Optional[str] = None
    limit: int = 10

class RefineRequest(BaseModel):
    user_message: str
    session_id: str
    limit: int = 10

@app.post("/api/recommendations")
async def get_recommendations(req: RecommendationRequest):
    try:
        logger.info(f"Recommendation request: {req.user_message}")
        result = service.recommend(
            user_message=req.user_message,
            session_id=req.session_id,
            limit=req.limit
        )
        return result
    except Exception as e:
        logger.error(f"Error in recommendations: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/refine")
async def refine_recommendations(req: RefineRequest):
    try:
        logger.info(f"Refinement request for session {req.session_id}: {req.user_message}")
        result = service.refine(
            user_message=req.user_message,
            session_id=req.session_id,
            limit=req.limit
        )
        return result
    except Exception as e:
        logger.error(f"Error in refinement: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/health")
async def health_check():
    return {"status": "healthy"}

@app.get("/")
async def root():
    return {"message": "Zomato AI Backend is running! Please open the frontend at http://localhost:3000 to use the service."}

@app.get("/api/metadata")
async def fetch_metadata():
    try:
        # Re-using the logic from phase 2 engine
        return engine_get_metadata()
    except Exception as e:
        logger.error(f"Error in metadata: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
