from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from datetime import datetime
import re
import time
from playwright.sync_api import sync_playwright
from typing import List, Dict
import uvicorn

app = FastAPI(title="PriceEmpire API", version="1.0.0")

class PriceResponse(BaseModel):
    success: bool
    data: List[Dict]
    summary: Dict
    pricempire_url: str
    execution_time: float

def scrape_prices(url: str) -> List[Dict]:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080}
        )
        page = context.new_page()
        
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            window.chrome = {runtime: {}};
        """)
        
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(10000)
        
        html = page.content()
        browser.close()
        
        # Extrai preços $
        all_prices = re.findall(r'\$([\d,]+\.?\d{2})', html)
        prices_validas = []
        
        for p in all_prices:
            try:
                preco = float(p.replace(',', ''))
                if 50 <= preco <= 3000:  # Range amplo
                    prices_validas.append(preco)
            except:
                continue
        
        unique_prices = sorted(list(set(prices_validas)))[:15]
        
        markets = [
            'CSFloat', 'Skinport', 'TradeIt.GG', 'CS.MONEY', 'Skins.com',
            'Lis-skins', 'SkinBaron', 'White.Market', 'SkinOut',
            'Buff.163', 'Youpin', 'DMarket', 'ShadowPay', 'Bitskins', 'Skinflow'
        ]
        
        return [{
            'marketplace': markets[i] if i < len(markets) else f'Market_{i+1}',
            'price_usd': round(preco, 2),
            'rank': i + 1
        } for i, preco in enumerate(unique_prices)]

@app.get("/api/prices/{item_slug}", response_model=PriceResponse)
async def get_prices(item_slug: str):
    inicio = time.time()
    url = f"https://pricempire.com/cs2-items/{item_slug}"
    
    try:
        prices = scrape_prices(url)
        
        if not prices:
            raise HTTPException(status_code=404, detail="No prices found")
        
        summary = {
            'total': len(prices),
            'best_price': prices[0]['price_usd'],
            'average_price': round(sum(p['price_usd'] for p in prices) / len(prices), 2)
        }
        
        return PriceResponse(
            success=True,
            data=prices,
            summary=summary,
            pricempire_url=url,
            execution_time=round(time.time() - inicio, 2)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/examples")
async def examples():
    return {
        "gloves": [
            "glove/specialist-gloves-foundation/battle-scarred",
            "glove/sport-gloves-arctic/factory-new"
        ],
        "weapons": [
            "weapon/ak-47-redline/field-tested",
            "weapon/m4a1-s-cyrex/minimal-wear"
        ]
    }

@app.get("/health")
async def health():
    return {"status": "OK", "service": "PriceEmpire API"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
