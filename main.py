from fastapi import FastAPI, HTTPException
import re
import time
from playwright.sync_api import sync_playwright
from pydantic import BaseModel
from typing import List
import uvicorn

app = FastAPI()

class MarketPrice(BaseModel):
    marketplace: str
    price_usd: float
    rank: int

class PriceSummary(BaseModel):
    total: int
    best_price: float
    avg_price: float

class PriceResponse(BaseModel):
    success: bool
    data: List[MarketPrice]
    summary: PriceSummary
    execution_time: float

PRICE_PATTERN = re.compile(r"\$([\d,]+\.?\d{2})")
MARKETS = [
    "CSFloat", "Skinport", "TradeIt.GG", "CS.MONEY", "Skins.com",
    "Lis-skins", "SkinBaron", "White.Market", "SkinOut",
    "Buff.163", "Youpin", "DMarket"
]

@app.get("/")
async def root():
    return {"message": "PriceEmpire API 🏆", "endpoints": ["/health", "/api/prices/{slug}"]}

@app.get("/health")
async def health():
    return {"status": "🟢 OK", "service": "PriceEmpire API"}

@app.get("/api/prices/{item_slug}")
async def get_prices(item_slug: str):
    start_time = time.time()
    
    try:
        url = f"https://pricempire.com/cs2-items/{item_slug}"
        
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True, args=["--no-sandbox"])
            page = browser.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(10000)
            html = page.content()
            browser.close()
        
        # Extrai preços
        raw_prices = PRICE_PATTERN.findall(html)
        filtered_prices = []
        seen = set()
        
        for raw in raw_prices:
            try:
                price = float(raw.replace(",", ""))
                if 50 <= price <= 3000 and price not in seen:
                    seen.add(price)
                    filtered_prices.append(price)
            except ValueError:
                continue
        
        filtered_prices.sort()
        filtered_prices = filtered_prices[:15]
        
        if not filtered_prices:
            raise HTTPException(status_code=404, detail="No prices found")
        
        prices = []
        for idx, price in enumerate(filtered_prices):
            market = MARKETS[idx % len(MARKETS)]
            prices.append(MarketPrice(
                marketplace=market,
                price_usd=round(price, 2),
                rank=idx + 1
            ))
        
        summary = PriceSummary(
            total=len(prices),
            best_price=prices[0].price_usd,
            avg_price=round(sum(p.price_usd for p in prices) / len(prices), 2)
        )
        
        return PriceResponse(
            success=True,
            data=prices,
            summary=summary,
            execution_time=round(time.time() - start_time, 2)
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
