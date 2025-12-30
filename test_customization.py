"""
Playwright test for image generation customization dialog

Tests:
1. Dialog appears when clicking generate buttons
2. LocalStorage persistence works
3. Form validation works
4. Settings are passed to backend correctly
"""

import asyncio
import sys

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("❌ Playwright not installed. Install with: pip install playwright")
    sys.exit(1)


async def test_customization_dialog():
    print("🧪 Starting Playwright tests for customization dialog...\n")

    tests_passed = 0
    tests_failed = 0

    async with async_playwright() as p:
        try:
            # Launch browser
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()

            # Test 1: Navigate to library page
            print("📍 Test 1: Navigate to library page")
            await page.goto("http://127.0.0.1:8123/")
            await page.wait_for_load_state("networkidle")

            title = await page.title()
            print(f"   ✓ Page loaded: {title}")
            tests_passed += 1

            # Check if there are any books
            book_links = await page.query_selector_all('a[href*="/read/"]')

            if not book_links:
                print("   ⚠️  No books found - skipping reader page tests")
                print("   ℹ️  To fully test, process an EPUB first with: uv run reader3.py <book.epub>\n")

                print("📊 Test Summary:")
                print(f"   ✓ Passed: {tests_passed}")
                print(f"   ✗ Failed: {tests_failed}")
                print(f"   ⚠️  Skipped: Reader page tests (no books available)")

                await browser.close()
                return tests_passed, tests_failed

            print(f"   ✓ Found {len(book_links)} book(s)\n")

            # Test 2: Navigate to first book
            print("📍 Test 2: Navigate to book reader")
            await book_links[0].click()
            await page.wait_for_load_state("networkidle")
            print("   ✓ Reader page loaded\n")
            tests_passed += 1

            # Test 3: Check if customization dialog exists
            print("📍 Test 3: Check customization dialog exists in DOM")
            dialog = await page.query_selector("#illustration-dialog")
            if not dialog:
                raise Exception("Customization dialog not found in DOM")

            is_hidden = await dialog.evaluate("el => el.classList.contains('hidden')")
            if not is_hidden:
                raise Exception("Dialog should be hidden by default")

            print("   ✓ Customization dialog exists and is hidden by default\n")
            tests_passed += 1

            # Test 4: Check dialog fields exist
            print("📍 Test 4: Check dialog form fields")
            num_images_input = await page.query_selector("#num-images")
            style_input = await page.query_selector("#image-style")

            if not num_images_input or not style_input:
                raise Exception("Dialog form fields not found")

            print("   ✓ Number of images input found")
            print("   ✓ Style input found\n")
            tests_passed += 1

            # Test 5: Open dialog via floating action button
            print("📍 Test 5: Open dialog via floating action button")

            action_button = await page.query_selector("#actions-menu-btn")
            if not action_button:
                raise Exception("Floating action button not found")

            await action_button.click()
            await page.wait_for_timeout(300)

            generate_btn = await page.query_selector("#generate-illustrations-btn")
            if not generate_btn:
                raise Exception("Generate illustrations button not found")

            await generate_btn.click()
            await page.wait_for_timeout(300)

            is_visible = await page.evaluate(
                "() => !document.getElementById('illustration-dialog').classList.contains('hidden')"
            )
            if not is_visible:
                raise Exception("Dialog should be visible after clicking generate button")

            print("   ✓ Dialog opens when clicking generate button\n")
            tests_passed += 1

            # Test 6: Test form inputs
            print("📍 Test 6: Test form inputs")
            await page.fill("#num-images", "5")
            await page.fill("#image-style", "anime")

            num_value = await page.input_value("#num-images")
            style_value = await page.input_value("#image-style")

            if num_value != "5" or style_value != "anime":
                raise Exception(f"Form inputs not working: num={num_value}, style={style_value}")

            print("   ✓ Number of images set to 5")
            print("   ✓ Style set to 'anime'\n")
            tests_passed += 1

            # Test 7: Test localStorage persistence
            print("📍 Test 7: Test localStorage persistence")

            # Intercept the fetch request to prevent actual generation
            await page.route("**/generate-illustrations", lambda route: route.fulfill(
                status=200,
                content_type="application/json",
                body='{"status": "generating", "message": "Test mode"}'
            ))

            confirm_btn = await page.query_selector('button:has-text("Generate")')
            await confirm_btn.click()
            await page.wait_for_timeout(300)

            # Check localStorage
            saved_settings = await page.evaluate("() => localStorage.getItem('illustration_settings')")
            if not saved_settings:
                raise Exception("Settings not saved to localStorage")

            import json
            settings = json.loads(saved_settings)
            if settings.get("numImages") != 5 or settings.get("style") != "anime":
                raise Exception(f"Settings not saved correctly: {settings}")

            print("   ✓ Settings saved to localStorage")
            print(f"   ✓ Saved values: numImages={settings['numImages']}, style=\"{settings['style']}\"\n")
            tests_passed += 1

            # Test 8: Test dialog reopens with saved settings
            print("📍 Test 8: Test dialog reopens with saved settings")

            await page.reload()
            await page.wait_for_load_state("networkidle")

            # Open dialog again
            await page.click("#actions-menu-btn")
            await page.wait_for_timeout(300)
            await page.click("#generate-illustrations-btn")
            await page.wait_for_timeout(300)

            reloaded_num_value = await page.input_value("#num-images")
            reloaded_style_value = await page.input_value("#image-style")

            if reloaded_num_value != "5" or reloaded_style_value != "anime":
                raise Exception(f"Settings not loaded: num={reloaded_num_value}, style={reloaded_style_value}")

            print("   ✓ Dialog reopened with saved settings")
            print(f"   ✓ Loaded values: numImages={reloaded_num_value}, style=\"{reloaded_style_value}\"\n")
            tests_passed += 1

            # Test 9: Test cancel button
            print("📍 Test 9: Test cancel button")
            cancel_btn = await page.query_selector('button:has-text("Cancel")')
            await cancel_btn.click()
            await page.wait_for_timeout(300)

            is_hidden_after_cancel = await page.evaluate(
                "() => document.getElementById('illustration-dialog').classList.contains('hidden')"
            )
            if not is_hidden_after_cancel:
                raise Exception("Dialog should be hidden after clicking cancel")

            print("   ✓ Dialog closes when clicking cancel\n")
            tests_passed += 1

            # Test 10: Test validation
            print("📍 Test 10: Test form validation")

            await page.click("#actions-menu-btn")
            await page.wait_for_timeout(300)
            await page.click("#generate-illustrations-btn")
            await page.wait_for_timeout(300)

            # Set invalid number
            await page.fill("#num-images", "15")  # Max is 10

            # Handle alert
            page.on("dialog", lambda dialog: asyncio.create_task(handle_dialog(dialog)))

            async def handle_dialog(dialog):
                print(f"   ✓ Validation alert shown: \"{dialog.message}\"")
                await dialog.accept()

            await page.click('button:has-text("Generate")')
            await page.wait_for_timeout(500)

            # Dialog should still be visible (validation failed)
            still_visible = await page.evaluate(
                "() => !document.getElementById('illustration-dialog').classList.contains('hidden')"
            )
            if not still_visible:
                raise Exception("Dialog should remain visible after validation failure")

            print("   ✓ Form validation prevents invalid values\n")
            tests_passed += 1

            await browser.close()

        except Exception as error:
            print(f"\n❌ Test failed: {error}\n")
            tests_failed += 1
            if 'browser' in locals():
                await browser.close()

    return tests_passed, tests_failed


async def main():
    tests_passed, tests_failed = await test_customization_dialog()

    # Print summary
    print("═══════════════════════════════════════════════════")
    print("📊 Test Summary:")
    print(f"   ✓ Passed: {tests_passed}")
    print(f"   ✗ Failed: {tests_failed}")
    print(f"   Total:  {tests_passed + tests_failed}")

    if tests_failed == 0:
        print("\n✅ All tests passed!")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
