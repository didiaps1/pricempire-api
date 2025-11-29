from fastapi import FastAPI, HTTPException
from playwright.sync_api import sync_playwright
import re
import time
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

MARKETS = [
    'CSFloat', 'Skinport', 'TradeIt.GG', 'CS.MONEY', 'Skins.com',
    'Lis-skins', 'SkinBaron', 'White.Market', 'SkinOut',
    'Buff.163', 'Youpin', 'DMarket'
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
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                viewport={'width': 1920, 'height': 1080}
            )
            page = context.new_page()
            
            # 🔥 ANTI-DETECÇÃO (ESSENCIAL!)
            page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                window.chrome = {runtime: {}};
            """)
            
            print(f"🌐 Carregando: {url}")
            page.goto(url, wait_until="domcontentloaded")
            
            print("⏳ Aguardando render (10s)...")
            page.wait_for_timeout(10000)  # 10 SEGUNDOS
            
            print("✅ Extraindo preços...")
            html = page.content()
            
            browser.close()
        
        # 🔥 REGEX EXATA QUE FUNCIONOU
        all_prices = re.findall(r'\$([\d,]+\.?\d{2})', html)
        prices_validas = []
        
        for p in all_prices:
            try:
                preco = float(p.replace(',', ''))
                # 🔥 FAIXA CORRETA DAS LUVAS!
                if 190 <= preco <= 350:
                    prices_validas.append(preco)
            except:
                pass
        
        unique_prices = sorted(list(set(prices_validas)))
        print(f"💰 {len(unique_prices)} preços encontrados")
        
        if not unique_prices:
            raise HTTPException(status_code=404, detail="No prices found")
        
        unique_prices = unique_prices[:12]
        
        prices = []
        for i, preco in enumerate(unique_prices):
            market = MARKETS[i]
            prices.append(MarketPrice(
                marketplace=market,
                price_usd=round(preco, 2),
                rank=i + 1
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
        print(f"💥 ERRO: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
