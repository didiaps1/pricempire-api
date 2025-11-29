from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from datetime import datetime
import re
import time
from playwright.sync_api import sync_playwright
from typing import List, Dict
import uvicorn

app = FastAPI()

class PriceResponse(BaseModel):
    success: bool
    data: List[Dict]
    summary: Dict
    execution_time: float

@app.get("/health")
async def health():
    return {"status": "OK"}

@app.get("/api/prices/{item_slug}")
async def get_prices(item_slug: str):
    inicio = time.time()
    url = f"https://pricempire.com/cs2-items/{item_slug}"
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(10000)
            html = page.content()
            browser.close()
        
        # Extrai TODOS os preços $
        all_prices = re.findall(r'\$([\d,]+\.?\d{2})', html)
        prices = []
        seen = set()
        
        for p in all_prices:
            try:
                preco = float(p.replace(',', ''))
                if 50 <= preco <= 3000 and preco not in seen:
                    seen.add(preco)
                    prices.append(preco)
            except:
                continue
        
        prices.sort()
        prices = prices[:15]
        
        markets = [
            'CSFloat', 'Skinport', 'TradeIt.GG', 'CS.MONEY', 'Skins.com',
            'Lis-skins', 'SkinBaron', 'White.Market', 'SkinOut',
            'Buff.163', 'Youpin', 'DMarket'
        ]
        
        resultado = []
        for i, preco in enumerate(prices):
            market = markets[i % len(markets)]
            resultado.append({
                'marketplace': market,
                'price_usd': round(preco, 2),
                'rank': i + 1
            })
        
        if not resultado:
            raise HTTPException(status_code=404, detail="No prices found")
        
        summary = {
            'total': len(resultado),
            'best_price': resultado[0]['price_usd'],
            'avg_price': round(sum(r['price_usd'] for r in resultado) / len(resultado), 2)
        }
        
        return {
            "success": True,
            "data": resultado,
            "summary": summary,
            "execution_time": round(time.time() - inicio, 2)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
