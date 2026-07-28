#!/usr/bin/env python3
import asyncio
import os
import random
import sys

from dotenv import load_dotenv
from playwright.async_api import async_playwright

from common import launch_browser, send_telegram, send_telegram_error, send_telegram_success, send_telegram_photo, TARGET_URL

load_dotenv()

NO_SLOTS_TEXT = os.getenv("NO_SLOTS_TEXT", "")

HEADLESS = "--headless" in sys.argv


async def check_slots() -> tuple[bool, str | None]:
    """Returns (True, None) if the site was reachable and evaluated (slots or no
    slots), or (False, reason) if the site/auth was unavailable."""
    async with async_playwright() as p:
        browser, context = await launch_browser(p, headless=HEADLESS)
        page = None
        try:
            timeout_ms = random.randint(25000, 35000)
            page = await context.new_page()

            print(f"Navigating to {TARGET_URL}")
            await page.goto(TARGET_URL, timeout=timeout_ms)
            print("Waiting for tramite dropdown...")
            await page.wait_for_selector("#tramiteGrupo\\[0\\]", timeout=timeout_ms)
            print("Selecting TOMA DE HUELLAS (4010)...")
            await asyncio.sleep(random.uniform(1.0, 3.0))
            await page.select_option("#tramiteGrupo\\[0\\]", value="4010")
            await asyncio.sleep(random.uniform(1.0, 3.0))
            print("Clicking Aceptar...")
            await page.click("#btnAceptar")
            await page.wait_for_load_state("networkidle", timeout=timeout_ms)
            print(f"Page after Aceptar: {page.url}")
            await asyncio.sleep(random.uniform(1.0, 3.0))

            print("Clicking Cl@ve button...")
            await page.click("#btnAccesoClave")
            await page.wait_for_load_state("networkidle", timeout=timeout_ms)
            print(f"Page after Cl@ve: {page.url}")
            await asyncio.sleep(random.uniform(1.0, 3.0))

            print("Clicking DNIe / Certificado electrónico...")
            await page.click("button.idp-button[onclick*='AFIRMA']")
            print("Waiting for post-auth redirect...")
            await page.wait_for_url("**/acEntrada**", timeout=timeout_ms)
            await page.wait_for_load_state("networkidle", timeout=timeout_ms)
            print(f"Final page: {page.url}")

            page_text = await page.inner_text("body")

            if not page_text.strip():
                reason = "Page body is empty — cert auth may have failed."
                print(f"\033[31mERROR: {reason}\033[0m")
                return False, reason

            if "playwright client-certificate error" in page_text.lower() or "unable to verify" in page_text.lower():
                reason = "Certificate/TLS error."
                print(f"\033[31mERROR: {reason}\033[0m")
                return False, reason

            if not NO_SLOTS_TEXT:
                print("\033[33mWARN: NO_SLOTS_TEXT not set — cannot detect slots.\033[0m")
                return True, None

            if NO_SLOTS_TEXT.lower() not in page_text.lower():
                print("\033[32mSLOTS AVAILABLE — sending notification!\033[0m")
                await page.screenshot(path="slots_found.png")
                send_telegram(f"ICP appointment slots may be available!\n{TARGET_URL}")
                # send_telegram_photo("slots_found.png", caption="Slots may be available!")
                return True, None

            print("\033[31mNo slots available.\033[0m")

            # Disabled for now — this deeper booking-request flow (clicking
            # through to a page where the no-slots text is fully reliable)
            # was triggering WAF blocks on the live site. Relying on just the
            # first-page check until that's sorted out.
            # print("No-slots text found here, but it's not conclusive — continuing to verify...")
            # # This deeper booking-request flow hits more sensitive/rate-limited
            # # endpoints than plain browsing, so use longer delays here.
            # await asyncio.sleep(random.uniform(3.0, 6.0))
            # await page.click("#btnCopiar")
            # await page.wait_for_load_state("networkidle", timeout=timeout_ms)
            # await asyncio.sleep(random.uniform(3.0, 6.0))
            #
            # print("Clicking Aceptar (step 2)...")
            # await page.click("#btnEnviar")
            # await page.wait_for_load_state("networkidle", timeout=timeout_ms)
            # await asyncio.sleep(random.uniform(3.0, 6.0))
            #
            # print("Clicking Solicitar Cita...")
            # await page.click("#btnEnviar")
            # await page.wait_for_load_state("networkidle", timeout=timeout_ms)
            #
            # final_text = await page.inner_text("body")
            # if NO_SLOTS_TEXT.lower() in final_text.lower():
            #     print("\033[31mNo slots available (confirmed).\033[0m")
            # else:
            #     print("\033[32mSLOTS AVAILABLE — sending notification!\033[0m")
            #     await page.screenshot(path="slots_found.png")
            #     send_telegram(f"ICP appointment slots may be available!\n{TARGET_URL}")
            #     # send_telegram_photo("slots_found.png", caption="Slots may be available!")

            return True, None
        except Exception:
            if page is not None:
                try:
                    await page.screenshot(path="error_debug.png")
                    html = await page.content()
                    with open("error_debug.html", "w") as f:
                        f.write(html)
                    print(f"Error occurred — screenshot/HTML saved to error_debug.png/.html, current URL: {page.url}")
                except Exception:
                    pass
            raise
        finally:
            await browser.close()


if __name__ == "__main__":
    try:
        ok, error_reason = asyncio.run(check_slots())
    except Exception as e:
        ok, error_reason = False, str(e)
        print(f"ERROR: {error_reason}")

    if not ok:
        send_telegram_error(f"ICP checker failed: {(error_reason or 'unknown error')[:300]}")
    else:
        send_telegram_success("🟢 ICP checker: run completed successfully.")

    sys.exit(0 if ok else 1)
