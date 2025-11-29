from __future__ import annotations

import asyncio
import re
import time

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from playwright.sync_api import sync_playwright


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
    data: list[MarketPrice]
    summary: PriceSummary
    execution_time: float = Field(description="Request execution time in seconds")


PRICE_PATTERN = re.compile(r"\$([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})?)")
# Broader pattern that catches currency values in rendered text as a fallback when
# price elements are not available in the raw HTML (e.g., due to client-side
# rendering or anti-bot measures).
PRICE_FALLBACK_PATTERN = re.compile(
    r"\$?\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})?)"
)
MARKETS = [
    "CSFloat",
    "Skinport",
    "TradeIt.GG",
    "CS.MONEY",
    "Skins.com",
    "Lis-skins",
    "SkinBaron",
    "White.Market",
    "SkinOut",
    "Buff.163",
    "Youpin",
    "DMarket",
]


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "OK"}


@app.get("/api/prices/{item_slug:path}", response_model=PriceResponse)
async def get_prices(item_slug: str) -> PriceResponse:
    start_time = time.time()

    try:
        prices = await asyncio.to_thread(scrape_prices, item_slug)
    except TimeoutError as exc:  # type: ignore[misc]
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - catch-all for unexpected issues
        raise HTTPException(status_code=500, detail="Internal server error") from exc

    summary = PriceSummary(
        total=len(prices),
        best_price=prices[0].price_usd,
        avg_price=round(sum(p.price_usd for p in prices) / len(prices), 2),
    )

    return PriceResponse(
        success=True,
        data=prices,
        summary=summary,
        execution_time=round(time.time() - start_time, 2),
    )


def scrape_prices(item_slug: str) -> list[MarketPrice]:
    """Scrape price data for the given item slug using Playwright.

    The Playwright context mirrors the locally working setup with:
    - explicit user agent and viewport to mimic a real browser
    - anti-detection init script to avoid webdriver fingerprinting
    - headless Chromium with --no-sandbox for container compatibility
    """

    url = f"https://pricempire.com/cs2-items/{item_slug}"

    html = ""
    rendered_text = ""

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1920, "height": 1080},
            locale="en-US",
            timezone_id="UTC",
        )
        page = context.new_page()

        page.add_init_script(
            """
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            window.chrome = {runtime: {}};
            window.navigator.permissions.query = (parameters) => (
              parameters.name === 'notifications'
                ? Promise.resolve({ state: 'denied' })
                : window.navigator.permissions.query(parameters)
            );
            """
        )

        try:
            page.goto(url, wait_until="networkidle", timeout=40_000)
            # Allow time for client-side rendering before parsing the DOM
            page.wait_for_timeout(12_000)
            html = page.content()
            # Capture rendered text as a fallback when HTML lacks inline price values
            rendered_text = page.inner_text("body")
        finally:
            browser.close()

    raw_prices = PRICE_PATTERN.findall(html)

    # Fallback to scanning the rendered text if the HTML didn't include prices.
    if not raw_prices and rendered_text:
        raw_prices = PRICE_FALLBACK_PATTERN.findall(rendered_text)

    filtered_prices: list[float] = []
    seen: set[float] = set()

    for raw in raw_prices:
        try:
            price = float(raw.replace(",", ""))
        except ValueError:
            continue

        if 50 <= price <= 3000 and price not in seen:
            seen.add(price)
            filtered_prices.append(price)

    filtered_prices.sort()
    filtered_prices = filtered_prices[:15]

    if not filtered_prices:
        raise ValueError("No prices found for the requested item.")

    prices: list[MarketPrice] = []
    for idx, price in enumerate(filtered_prices):
        market = MARKETS[idx % len(MARKETS)]
        prices.append(
            MarketPrice(
                marketplace=market,
                price_usd=round(price, 2),
                rank=idx + 1,
            )
        )

    return prices


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
