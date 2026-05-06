"""
TradeVue Cloud API — Trading Journal & Watchlist
Deploy this to Render via GitHub.
Endpoints:
  GET  /                        - health check
  POST /analysis/save           - save an analysis result
  GET  /analysis/history        - get all saved analyses (newest first)
  GET  /analysis/history/{ticker} - get analyses for one ticker
  DELETE /analysis/{analysis_id}  - delete one analysis
  POST /watchlist/{ticker}      - add ticker to watchlist
  GET  /watchlist               - get full watchlist
  DELETE /watchlist/{ticker}    - remove ticker from watchlist
"""
from fastapi import FastAPI, HTTPException, Security, Depends
from fastapi.security.api_key import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from starlette.status import HTTP_403_FORBIDDEN
from datetime import datetime
import uuid
 
app = FastAPI(title="TradeVue Cloud API", version="2.0")
 
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
 
# ── Auth ───────────────────────────────────────────────────────────────────────
API_KEY      = "aeebb318825a950831d17bfd32037e17"
API_KEY_NAME = "access_token"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)
 
async def get_api_key(header_value: str = Security(api_key_header)):
    if header_value == API_KEY:
        return header_value
    raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="Invalid API key")
 
# ── In-memory stores ───────────────────────────────────────────────────────────
# Note: resets when Render free tier sleeps (after ~15 min inactivity).
analysis_history: List[dict] = []
watchlist: List[dict] = []
 
# ── Models ─────────────────────────────────────────────────────────────────────
class AnalysisEntry(BaseModel):
    ticker:         Optional[str] = "UNKNOWN"
    timeframe:      Optional[str] = "1D"
    sentiment:      str            # BULLISH | BEARISH | NEUTRAL
    confidence:     float
    risk_level:     str            # LOW | MEDIUM | HIGH
    patterns:       List[str] = []
    recommendation: str
    projection:     Optional[str] = "SIDEWAYS"
    ai_powered:     Optional[bool] = False
    notes:          Optional[str] = ""
 
class WatchlistEntry(BaseModel):
    ticker:  str
    notes:   Optional[str] = ""
 
# ── Health check (public) ──────────────────────────────────────────────────────
@app.get("/")
def root():
    return {
        "service": "TradeVue Cloud API",
        "version": "2.0",
        "status":  "online",
        "analyses_saved": len(analysis_history),
        "watchlist_count": len(watchlist),
    }
 
# ── Analysis History ───────────────────────────────────────────────────────────
@app.post("/analysis/save", status_code=201)
def save_analysis(entry: AnalysisEntry, api_key: str = Depends(get_api_key)):
    record = {
        "id":             str(uuid.uuid4())[:8],
        "ticker":         entry.ticker.upper() if entry.ticker else "UNKNOWN",
        "timeframe":      entry.timeframe,
        "sentiment":      entry.sentiment,
        "confidence":     round(entry.confidence * 100),
        "risk_level":     entry.risk_level,
        "patterns":       entry.patterns,
        "recommendation": entry.recommendation,
        "projection":     entry.projection,
        "ai_powered":     entry.ai_powered,
        "notes":          entry.notes,
        "saved_at":       datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
    }
    analysis_history.insert(0, record)   # newest first
    # Keep last 100 entries
    if len(analysis_history) > 100:
        analysis_history.pop()
    return {"message": "Analysis saved", "id": record["id"], "entry": record}
 
 
@app.get("/analysis/history")
def get_history(api_key: str = Depends(get_api_key)):
    return {
        "count":    len(analysis_history),
        "analyses": analysis_history,
    }
 
 
@app.get("/analysis/history/{ticker}")
def get_history_by_ticker(ticker: str, api_key: str = Depends(get_api_key)):
    ticker = ticker.upper()
    filtered = [a for a in analysis_history if a["ticker"] == ticker]
    return {
        "ticker":   ticker,
        "count":    len(filtered),
        "analyses": filtered,
    }
 
 
@app.delete("/analysis/{analysis_id}")
def delete_analysis(analysis_id: str, api_key: str = Depends(get_api_key)):
    global analysis_history
    before = len(analysis_history)
    analysis_history = [a for a in analysis_history if a["id"] != analysis_id]
    if len(analysis_history) == before:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return {"message": f"Analysis {analysis_id} deleted"}
 
 
# ── Watchlist ──────────────────────────────────────────────────────────────────
@app.post("/watchlist/{ticker}", status_code=201)
def add_to_watchlist(ticker: str, api_key: str = Depends(get_api_key)):
    ticker = ticker.upper()
    if any(w["ticker"] == ticker for w in watchlist):
        return {"message": f"{ticker} already in watchlist"}
    watchlist.append({
        "ticker":   ticker,
        "added_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
    })
    return {"message": f"{ticker} added to watchlist", "watchlist": watchlist}
 
 
@app.get("/watchlist")
def get_watchlist(api_key: str = Depends(get_api_key)):
    return {"count": len(watchlist), "watchlist": watchlist}
 
 
@app.delete("/watchlist/{ticker}")
def remove_from_watchlist(ticker: str, api_key: str = Depends(get_api_key)):
    global watchlist
    ticker = ticker.upper()
    before = len(watchlist)
    watchlist = [w for w in watchlist if w["ticker"] != ticker]
    if len(watchlist) == before:
        raise HTTPException(status_code=404, detail=f"{ticker} not in watchlist")
    return {"message": f"{ticker} removed", "watchlist": watchlist}
