from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import pandas as pd
from datetime import datetime
import re
import time
from playwright.sync_api import sync_playwright
from typing import List, Dict, Optional
import uvicorn
import os

app = FastAPI(title="PriceEmpire API", version="1.0.0")

class PriceResponse(BaseModel):
    success: bool
    data: List[Dict]
    summary: Dict
    timestamp: str
    execution_time: float

def scrape_prices(url: str) -> List[Dict]:
    """Core scraper - mesma lógica que funcionou!"""
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
        
        # Extrair preços
        all_prices = re.findall(r'\$([\d,]+\.?\d{2})', html)
        prices_validas = []
        
        for p in all_prices:
            try:
                preco = float(p.replace(',', ''))
                if 190 <= preco <= 350:  # Ajuste conforme item
                    prices_validas.append(preco)
            except:
                pass
        
        unique_prices = sorted(list(set(prices_validas)))
        
        # Marketplaces
        markets = [
            'CSFloat', 'Skinport', 'TradeIt.GG', 'CS.MONEY', 'Skins.com',
            'Lis-skins', 'SkinBaron', 'White.Market', 'SkinOut',
            'Buff.163', 'Youpin', 'DMarket'
        ]
        
        resultado = []
        for i, preco in enumerate(unique_prices[:12]):
            market = markets[i] if i < len(markets) else f'Market_{i+1}'
            resultado.append({
                'marketplace': market,
                'price_usd': round(preco, 2),
                'rank': i + 1
            })
        
        return resultado

@app.get("/api/prices/{item_slug}", response_model=PriceResponse)
async def get_prices(item_slug: str):
    """🔥 API PRINCIPAL - Retorna preços por slug"""
    inicio = time.time()
    
    # Monta URL automaticamente
    base_url = f"https://pricempire.com/cs2-items/{item_slug}"
    
    try:
        print(f"🌐 Scraping: {base_url}")
        prices = scrape_prices(base_url)
        
        if not prices:
            raise HTTPException(status_code=404, detail="No prices found")
        
        # Summary
        summary = {
            'total': len(prices),
            'best_price': prices[0]['price_usd'],
            'average_price': sum(p['price_usd'] for p in prices) / len(prices),
            'url': base_url
        }
        
        response = PriceResponse(
            success=True,
            data=prices,
            summary=summary,
            timestamp=datetime.now().isoformat(),
            execution_time=round(time.time() - inicio, 2)
        )
        
        return response
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scrape failed: {str(e)}")

@app.get("/api/prices")
async def list_examples():
    """📋 Exemplos de uso"""
    examples = [
        "/api/prices/glove/specialist-gloves-foundation/battle-scarred",
        "/api/prices/glove/sport-gloves-arctic/factory-new",
        "/api/prices/weapon/ak-47-redline/field-tested"
    ]
    return {"examples": examples, "base_url": "https://your-api.render.com"}

@app.get("/health")
async def health_check():
    return {"status": "OK", "service": "PriceEmpire API"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)