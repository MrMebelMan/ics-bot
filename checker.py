#!/usr/bin/env python3
import asyncio
import os
import random
import sys

from dotenv import load_dotenv
from playwright.async_api import async_playwright

from common import launch_browser, send_telegram, send_telegram_error, TARGET_URL, NOTIFY_ON_ERROR, TIMEOUT

load_dotenv()

NO_SLOTS_TEXT = os.getenv("NO_SLOTS_TEXT", "")

HEADLESS = "--headless" in sys.argv


async def check_slots() -> bool:
    """Returns True if the site was reachable and evaluated (slots or no slots),
    False if the site/auth was unavailable (empty page, cert error)."""
    async with async_playwright() as p:
        browser, context = await launch_browser(p, headless=HEADLESS)
        try:
            page = await context.new_page()

            print(f"Navigating to {TARGET_URL}")
            await page.goto(TARGET_URL, timeout=TIMEOUT)
            print("Waiting for tramite dropdown...")
            await page.wait_for_selector("#tramiteGrupo\\[0\\]", timeout=TIMEOUT)
            print("Selecting TOMA DE HUELLAS (4010)...")
            await asyncio.sleep(random.uniform(1.0, 3.0))
            await page.select_option("#tramiteGrupo\\[0\\]", value="4010")
            await asyncio.sleep(random.uniform(1.0, 3.0))
            print("Clicking Aceptar...")
            await page.click("#btnAceptar")
            await page.wait_for_load_state("networkidle", timeout=TIMEOUT)
            print(f"Page after Aceptar: {page.url}")
            await asyncio.sleep(random.uniform(1.0, 3.0))

            print("Clicking Cl@ve button...")
            await page.click("#btnAccesoClave")
            await page.wait_for_load_state("networkidle", timeout=TIMEOUT)
            print(f"Page after Cl@ve: {page.url}")
            await asyncio.sleep(random.uniform(1.0, 3.0))

            print("Clicking DNIe / Certificado electrónico...")
            await page.click("button.idp-button[onclick*='AFIRMA']")
            print("Waiting for post-auth redirect...")
            try:
                await page.wait_for_url("**/acEntrada**", timeout=TIMEOUT)
            except Exception:
                await page.screenshot(path="timeout_debug.png")
                print(f"Timed out waiting for redirect — screenshot saved to timeout_debug.png, current URL: {page.url}")
                raise
            await page.wait_for_load_state("networkidle", timeout=TIMEOUT)
            print(f"Final page: {page.url}")

            page_text = await page.inner_text("body")

            if not page_text.strip():
                print("\033[31mERROR: Page body is empty — cert auth may have failed.\033[0m")
                return False

            if "playwright client-certificate error" in page_text.lower() or "unable to verify" in page_text.lower():
                print("\033[31mERROR: Certificate/TLS error.\033[0m")
                return False

            if not NO_SLOTS_TEXT:
                print("\033[33mWARN: NO_SLOTS_TEXT not set — cannot detect slots.\033[0m")
                return True

            if NO_SLOTS_TEXT.lower() in page_text.lower():
                print("\033[31mNo slots available.\033[0m")
            else:
                print("\033[32mSLOTS AVAILABLE — sending notification!\033[0m")
                send_telegram(f"ICP appointment slots may be available!\n{TARGET_URL}")

            return True
        finally:
            await browser.close()


if __name__ == "__main__":
    try:
        ok = asyncio.run(check_slots())
    except Exception as e:
        msg = str(e)
        print(f"ERROR: {msg}")
        if NOTIFY_ON_ERROR:
            send_telegram_error(f"ICP checker failed: {msg[:300]}")
        ok = False

    sys.exit(0 if ok else 1)
