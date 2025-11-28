from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from datetime import datetime
import re
import time
from playwright.sync_api import sync_playwright
from typing import List, Dict
import uvicorn
import json

app = FastAPI(title="🛒 PriceEmpire API", version="2.0")

class PriceResponse(BaseModel):
    success: bool
    data: List[Dict]
    summary: Dict
    request_url: str
    pricempire_url: str
    timestamp: str
    execution_time: float

def scrape_dynamic(url: str, min_price: float = 50, max_price: float = 2000) -> List[Dict]:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            viewport={'width': 1920, 'height': 1080}
        )
        page = context.new_page()
        
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            window.chrome = {runtime: {}};
        """)
        
        page.goto(url, wait_until="domcontentloaded")
        page.wait_for_timeout(10000)
        
        html = page.content()
        browser.close()
        
        all_prices = re.findall(r'\$([\d,]+\.?\d{2})', html)
        prices_validas = []
        
        for p in all_prices:
            try:
                preco = float(p.replace(',', ''))
                if min_price <= preco <= max_price:
                    prices_validas.append(preco)
            except:
                pass
        
        unique_prices = sorted(list(set(prices_validas)))
        
        markets = [
            'CSFloat', 'Skinport', 'TradeIt.GG', 'CS.MONEY', 'Skins.com',
            'Lis-skins', 'SkinBaron', 'White.Market', 'SkinOut',
            'Buff.163', 'Youpin', 'DMarket', 'ShadowPay', 'Bitskins'
        ]
        
        resultado = []
        for i, preco in enumerate(unique_prices[:15]):
            market = markets[i] if i < len(markets) else f'Market_{i+1}'
            resultado.append({
                'marketplace': market,
                'price_usd': round(preco, 2),
                'rank': i + 1
            })
        
        return resultado

@app.get("/api/prices/{item_slug}", response_model=PriceResponse)
async def get_prices(
    item_slug: str,
    min_price: float = Query(50, ge=0),
    max_price: float = Query(2000, ge=0)
):
    inicio = time.time()
    pricempire_url = f"https://pricempire.com/cs2-items/{item_slug}"
    request_url = f"/api/prices/{item_slug}"
    
    try:
        prices = scrape_dynamic(pricempire_url, min_price, max_price)
        
        if not prices:
            raise HTTPException(status_code=404, detail="No prices found")
        
        summary = {
            'total': len(prices),
            'best_price': prices[0]['price_usd'],
            'average_price': round(sum(p['price_usd'] for p in prices) / len(prices), 2),
            'price_range': f"${min_price} - ${max_price}"
        }
        
        return PriceResponse(
            success=True,
            data=prices,
            summary=summary,
            request_url=request_url,
            pricempire_url=pricempire_url,
            timestamp=datetime.now().isoformat(),
            execution_time=round(time.time() - inicio, 2)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

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
    return {"status": "🟢 OK", "api": "PriceEmpire v2.0"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
