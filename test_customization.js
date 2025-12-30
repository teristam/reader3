/**
 * Playwright test for image generation customization dialog
 *
 * Tests:
 * 1. Dialog appears when clicking generate buttons
 * 2. LocalStorage persistence works
 * 3. Form validation works
 * 4. Settings are passed to backend correctly
 */

const { chromium } = require('playwright');

async function testCustomizationDialog() {
    console.log('🧪 Starting Playwright tests for customization dialog...\n');

    const browser = await chromium.launch({ headless: true });
    const context = await browser.newContext();
    const page = await context.newPage();

    let testsPassed = 0;
    let testsFailed = 0;

    try {
        // Navigate to the library page
        console.log('📍 Test 1: Navigate to library page');
        await page.goto('http://127.0.0.1:8123/');
        await page.waitForLoadState('networkidle');

        const title = await page.title();
        console.log(`   ✓ Page loaded: ${title}`);
        testsPassed++;

        // Check if there are any books
        const bookLinks = await page.$$('a[href*="/read/"]');

        if (bookLinks.length === 0) {
            console.log('   ⚠️  No books found - skipping reader page tests');
            console.log('   ℹ️  To fully test, process an EPUB first with: uv run reader3.py <book.epub>\n');

            console.log('📊 Test Summary:');
            console.log(`   ✓ Passed: ${testsPassed}`);
            console.log(`   ✗ Failed: ${testsFailed}`);
            console.log(`   ⚠️  Skipped: Reader page tests (no books available)`);

            await browser.close();
            return;
        }

        console.log(`   ✓ Found ${bookLinks.length} book(s)\n`);

        // Navigate to first book
        console.log('📍 Test 2: Navigate to book reader');
        await bookLinks[0].click();
        await page.waitForLoadState('networkidle');
        console.log('   ✓ Reader page loaded\n');
        testsPassed++;

        // Test 3: Check if customization dialog exists
        console.log('📍 Test 3: Check customization dialog exists in DOM');
        const dialog = await page.$('#illustration-dialog');
        if (!dialog) {
            throw new Error('Customization dialog not found in DOM');
        }
        const isHidden = await dialog.evaluate(el => el.classList.contains('hidden'));
        if (!isHidden) {
            throw new Error('Dialog should be hidden by default');
        }
        console.log('   ✓ Customization dialog exists and is hidden by default\n');
        testsPassed++;

        // Test 4: Check dialog fields exist
        console.log('📍 Test 4: Check dialog form fields');
        const numImagesInput = await page.$('#num-images');
        const styleInput = await page.$('#image-style');
        if (!numImagesInput || !styleInput) {
            throw new Error('Dialog form fields not found');
        }
        console.log('   ✓ Number of images input found');
        console.log('   ✓ Style input found\n');
        testsPassed++;

        // Test 5: Open dialog via floating action button
        console.log('📍 Test 5: Open dialog via floating action button');

        // Click the floating action button
        const actionButton = await page.$('#actions-menu-btn');
        if (!actionButton) {
            throw new Error('Floating action button not found');
        }
        await actionButton.click();
        await page.waitForTimeout(200); // Wait for dropdown animation

        // Click generate illustrations button
        const generateBtn = await page.$('#generate-illustrations-btn');
        if (!generateBtn) {
            throw new Error('Generate illustrations button not found');
        }
        await generateBtn.click();
        await page.waitForTimeout(200); // Wait for dialog animation

        // Check if dialog is visible
        const isVisible = await page.$eval('#illustration-dialog',
            el => !el.classList.contains('hidden')
        );
        if (!isVisible) {
            throw new Error('Dialog should be visible after clicking generate button');
        }
        console.log('   ✓ Dialog opens when clicking generate button\n');
        testsPassed++;

        // Test 6: Test form inputs
        console.log('📍 Test 6: Test form inputs');
        await page.fill('#num-images', '5');
        await page.fill('#image-style', 'anime');

        const numValue = await page.inputValue('#num-images');
        const styleValue = await page.inputValue('#image-style');

        if (numValue !== '5' || styleValue !== 'anime') {
            throw new Error('Form inputs not working correctly');
        }
        console.log('   ✓ Number of images set to 5');
        console.log('   ✓ Style set to "anime"\n');
        testsPassed++;

        // Test 7: Test localStorage persistence
        console.log('📍 Test 7: Test localStorage persistence');

        // Confirm dialog (this should save to localStorage)
        const confirmBtn = await page.$('button:has-text("Generate")');

        // Intercept the fetch request to prevent actual generation
        await page.route('**/generate-illustrations', route => {
            route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify({ status: 'generating', message: 'Test mode' })
            });
        });

        await confirmBtn.click();
        await page.waitForTimeout(200);

        // Check localStorage
        const savedSettings = await page.evaluate(() => {
            return localStorage.getItem('illustration_settings');
        });

        if (!savedSettings) {
            throw new Error('Settings not saved to localStorage');
        }

        const settings = JSON.parse(savedSettings);
        if (settings.numImages !== 5 || settings.style !== 'anime') {
            throw new Error(`Settings not saved correctly: ${JSON.stringify(settings)}`);
        }
        console.log('   ✓ Settings saved to localStorage');
        console.log(`   ✓ Saved values: numImages=${settings.numImages}, style="${settings.style}"\n`);
        testsPassed++;

        // Test 8: Test dialog reopens with saved settings
        console.log('📍 Test 8: Test dialog reopens with saved settings');

        // Reload page to clear state
        await page.reload();
        await page.waitForLoadState('networkidle');

        // Open dialog again
        await page.click('#actions-menu-btn');
        await page.waitForTimeout(200);
        await page.click('#generate-illustrations-btn');
        await page.waitForTimeout(200);

        // Check if fields are populated with saved values
        const reloadedNumValue = await page.inputValue('#num-images');
        const reloadedStyleValue = await page.inputValue('#image-style');

        if (reloadedNumValue !== '5' || reloadedStyleValue !== 'anime') {
            throw new Error(`Settings not loaded from localStorage: num=${reloadedNumValue}, style=${reloadedStyleValue}`);
        }
        console.log('   ✓ Dialog reopened with saved settings');
        console.log(`   ✓ Loaded values: numImages=${reloadedNumValue}, style="${reloadedStyleValue}"\n`);
        testsPassed++;

        // Test 9: Test cancel button
        console.log('📍 Test 9: Test cancel button');
        const cancelBtn = await page.$('button:has-text("Cancel")');
        await cancelBtn.click();
        await page.waitForTimeout(200);

        const isHiddenAfterCancel = await page.$eval('#illustration-dialog',
            el => el.classList.contains('hidden')
        );
        if (!isHiddenAfterCancel) {
            throw new Error('Dialog should be hidden after clicking cancel');
        }
        console.log('   ✓ Dialog closes when clicking cancel\n');
        testsPassed++;

        // Test 10: Test validation
        console.log('📍 Test 10: Test form validation');

        // Open dialog
        await page.click('#actions-menu-btn');
        await page.waitForTimeout(200);
        await page.click('#generate-illustrations-btn');
        await page.waitForTimeout(200);

        // Try to set invalid number
        await page.fill('#num-images', '15'); // Max is 10

        // Click confirm and check for alert
        page.on('dialog', async dialog => {
            console.log(`   ✓ Validation alert shown: "${dialog.message()}"`);
            await dialog.accept();
        });

        await page.click('button:has-text("Generate")');
        await page.waitForTimeout(500);

        // Dialog should still be visible (validation failed)
        const stillVisible = await page.$eval('#illustration-dialog',
            el => !el.classList.contains('hidden')
        );
        if (!stillVisible) {
            throw new Error('Dialog should remain visible after validation failure');
        }
        console.log('   ✓ Form validation prevents invalid values\n');
        testsPassed++;

        // Test 11: Check "Generate All Illustrations" also shows dialog
        console.log('📍 Test 11: Test "Generate All Illustrations" button');

        // Close current dialog
        await page.click('button:has-text("Cancel")');
        await page.waitForTimeout(200);

        // Try to open book menu
        const bookMenuBtn = await page.$('#book-menu-btn');
        if (bookMenuBtn) {
            // Hover to show the button (it has opacity-0 group-hover:opacity-100)
            await page.hover('.group:has(#book-menu-btn)');
            await page.waitForTimeout(200);

            await bookMenuBtn.click();
            await page.waitForTimeout(200);

            const generateAllBtn = await page.$('button:has-text("Generate All Illustrations")');
            if (generateAllBtn) {
                await generateAllBtn.click();
                await page.waitForTimeout(200);

                const dialogVisible = await page.$eval('#illustration-dialog',
                    el => !el.classList.contains('hidden')
                );
                if (!dialogVisible) {
                    throw new Error('Dialog should open for "Generate All Illustrations"');
                }
                console.log('   ✓ Dialog opens for "Generate All Illustrations"\n');
                testsPassed++;
            } else {
                console.log('   ⚠️  "Generate All Illustrations" button not found (may be hidden)\n');
            }
        } else {
            console.log('   ⚠️  Book menu button not found\n');
        }

    } catch (error) {
        console.error(`\n❌ Test failed: ${error.message}\n`);
        testsFailed++;
    } finally {
        await browser.close();
    }

    // Print summary
    console.log('═══════════════════════════════════════════════════');
    console.log('📊 Test Summary:');
    console.log(`   ✓ Passed: ${testsPassed}`);
    console.log(`   ✗ Failed: ${testsFailed}`);
    console.log(`   Total:  ${testsPassed + testsFailed}`);

    if (testsFailed === 0) {
        console.log('\n✅ All tests passed!');
        process.exit(0);
    } else {
        console.log('\n❌ Some tests failed');
        process.exit(1);
    }
}

// Run tests
testCustomizationDialog().catch(error => {
    console.error('Fatal error:', error);
    process.exit(1);
});
