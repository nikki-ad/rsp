// Run: NODE_PATH="$CODEX_PRIMARY_RUNTIME_NODE_MODULES" node tests/upload-progress.cjs
const { chromium } = require('playwright');
const fs = require('node:fs');
const assert = require('node:assert/strict');

(async () => {
    const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROMIUM_EXECUTABLE_PATH });
    try {
        const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
        const script = fs.readFileSync('static/js/upload-progress.js', 'utf8');
        const css = fs.readFileSync('static/css/upload-progress.css', 'utf8');
        await page.route('http://rsp.test/**', route => route.fulfill({ contentType: 'text/html', body: '<p>destination</p>' }));
        async function setup() {
            await page.goto('http://rsp.test/form');
            await page.setContent(`<html lang="fa" dir="rtl"><head><style>${css}</style></head><body>
                <form action="/save" method="post" data-upload-progress>
                <input name="csrfmiddlewaretoken" value="csrf-test" type="hidden">
                <input name="title" value="عنوان" required>
                <input name="disabled_field" value="skip" disabled>
                <input name="video" type="file"><button type="submit">ذخیره</button></form>
                <form id="ordinary"><button type="submit">Other</button></form></body></html>`);
            await page.evaluate(() => {
                window.requests = [];
                window.XMLHttpRequest = class extends EventTarget {
                    constructor() { super(); this.upload = new EventTarget(); this.headers = {}; }
                    open(method, url) { this.method = method; this.url = url; }
                    setRequestHeader(name, value) { this.headers[name] = value; }
                    send(data) { this.data = data; window.requests.push(this); }
                };
            });
            await page.addScriptTag({ content: script });
            await page.evaluate(() => document.dispatchEvent(new Event('DOMContentLoaded')));
        }
        const status = () => page.locator('.upload-progress__status').textContent();
        async function start() {
            await page.locator('input[type=file]').setInputFiles({ name: 'lesson.mp4', mimeType: 'video/mp4', buffer: Buffer.from('video') });
            await page.locator('form[data-upload-progress] button').click();
        }
        async function finish(code, body, url = '') {
            await page.evaluate(({ code, body, url }) => {
                const xhr = window.requests.at(-1);
                xhr.status = code;
                xhr.responseText = typeof body === 'string' ? body : JSON.stringify(body);
                xhr.responseURL = url;
                xhr.dispatchEvent(new Event('load'));
            }, { code, body, url });
        }
        await setup();
        assert.equal(await page.locator('#ordinary .upload-progress').count(), 0);
        await start();
        assert.equal(await page.locator('button').first().isDisabled(), true);
        const payload = await page.evaluate(() => {
            const xhr = requests[0];
            document.querySelector('form[data-upload-progress]').dispatchEvent(new Event('submit', { cancelable: true }));
            return { count: requests.length, csrf: xhr.data.get('csrfmiddlewaretoken'), file: xhr.data.get('video').name, omitted: xhr.data.has('disabled_field'), header: xhr.headers['X-RSP-Upload'] };
        });
        assert.deepEqual(payload, { count: 1, csrf: 'csrf-test', file: 'lesson.mp4', omitted: false, header: '1' });
        await page.evaluate(() => requests[0].upload.dispatchEvent(new ProgressEvent('progress', { lengthComputable: true, loaded: 45, total: 100 })));
        assert.equal(await page.locator('[role=progressbar]').getAttribute('aria-valuenow'), '45');
        assert.equal(await page.locator('.upload-progress__percent').textContent(), '۴۵٪');
        await page.evaluate(() => requests[0].upload.dispatchEvent(new Event('load')));
        assert.match(await status(), /در حال ذخیره/);
        assert.doesNotMatch(await status(), /با موفقیت/);
        assert.equal(await page.locator('[role=progressbar]').getAttribute('aria-valuenow'), '100');
        await finish(422, { success: false, message: 'خطای اعتبارسنجی', errors: { title: [{ message: '<script>invalid</script>' }] } });
        assert.equal(await page.locator('button').first().isDisabled(), false);
        assert.equal(await page.locator('input[name=disabled_field]').isDisabled(), true);
        assert.equal(await page.locator('input[name=title]').getAttribute('aria-invalid'), 'true');
        assert.equal(await page.locator('.upload-progress__errors').textContent(), '<script>invalid</script>');
        assert.equal(await page.locator('input[type=file]').evaluate(input => input.files[0].name), 'lesson.mp4');
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
        await page.locator('form[data-upload-progress] button').click();
        assert.equal(await page.locator('[data-upload-error]').count(), 0);
        await finish(200, { success: true, message: 'با موفقیت انجام شد.', redirect_url: '/done' });
        await page.waitForURL('http://rsp.test/done');

        for (const [code, body, url, expected] of [
            [413, '<html>too large</html>', '', /حجم فایل/],
            [500, 'error', '', /تأیید ذخیره/],
            [403, 'forbidden', '', /اجازه ثبت/],
            [200, '<html>login</html>', 'http://rsp.test/accounts/login/?next=/save', /نشست شما/],
            [200, { success: true, redirect_url: 'http://outside.test' }, '', /نامعتبر/],
        ]) {
            await setup(); await start(); await finish(code, body, url);
            assert.match(await status(), expected);
            assert.doesNotMatch(await status(), /با موفقیت/);
            assert.equal(await page.locator('button').first().isDisabled(), false);
        }
        for (const type of ['error', 'abort']) {
            await setup(); await start();
            await page.evaluate(type => requests[0].dispatchEvent(new Event(type)), type);
            assert.doesNotMatch(await status(), /با موفقیت/);
            assert.equal(await page.locator('button').first().isDisabled(), false);
        }
        await setup();
        await page.locator('form[data-upload-progress] button').click();
        assert.equal(await page.locator('.upload-progress__percent').isHidden(), true);
        assert.equal(await page.locator('[role=progressbar]').getAttribute('aria-valuenow'), null);
        console.log('PASS: progress, server confirmation, duplicate prevention, validation retry, CSRF payload, errors, expired session, no-file save, mobile layout');
    } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
