#!/usr/bin/env python3
import asyncio

from playwright.async_api import async_playwright

from common import launch_browser, TARGET_URL


async def main() -> None:
    async with async_playwright() as p:
        browser, context = await launch_browser(p, headless=False)
        page = await context.new_page()
        await page.goto(TARGET_URL, timeout=60000)
        await page.wait_for_selector("select", timeout=30000)

        print("Browser open — navigate manually. Close the browser window when done.")
        await page.wait_for_event("close", timeout=0)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"ERROR: {e}")
