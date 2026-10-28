const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const path = require('node:path');
(async () => {
    const browser = await chromium.launch({headless:true});
    const page = await browser.newPage();
    await page.setContent(`<form><select id="id_academic_year"><option value="one">one</option><option value="two">two</option></select>
        <div id="id_students"><label><input name="students" type="checkbox" value="a" checked>A</label><label><input name="students" type="checkbox" value="b">B</label></div>
        <button type="submit">Save</button></form>
        <script id="online-class-groups" type="application/json">[{"id":"room","name":"Class A","students":[{"id":"a","name":"Alice"},{"id":"b","name":"Beth"}]}]</script>
        <div id="online-class-endpoint" data-url="/people"></div>`);
    await page.route('**/people?*', route => route.fulfill({json:{classrooms:[{id:'next',name:'Class B',students:[{id:'c',name:'Cara'}]}]}}));
    await page.evaluate(() => { document.getElementById('online-class-endpoint').dataset.url = 'https://rsp.example/people'; });
    await page.addScriptTag({path:path.resolve(__dirname, '../static/js/online-class-students.js')});
    await page.evaluate(() => document.dispatchEvent(new Event('DOMContentLoaded')));
    assert.equal(await page.locator('input[name="students"]:checked').count(), 1);
    assert.equal(await page.locator('summary input').evaluate(el=>el.indeterminate), true);
    await page.locator('summary input').check();
    assert.equal(await page.locator('input[name="students"]:checked').count(), 2);
    await page.locator('summary span').click();
    await page.locator('input[name="students"][value="a"]').uncheck();
    assert.equal(await page.locator('summary input').evaluate(el=>el.indeterminate), true);
    assert.deepEqual(await page.evaluate(()=>new FormData(document.querySelector('form')).getAll('students')), ['b']);
    await page.locator('input[type="search"]').fill('Alice');
    assert.equal(await page.locator('label:visible').count(),1);
    await page.locator('input[type="search"]').fill('');
    await page.locator('#id_academic_year').selectOption('two');
    await page.waitForFunction(()=>document.querySelector('input[value="c"]'));
    assert.equal(await page.locator('input[name="students"]:checked').count(),0);
    await browser.close();
    console.log('PASS: saved choices, class select-all, individual exclusion, submitted IDs, search, year reload');
})().catch(error=>{console.error(error);process.exit(1);});
