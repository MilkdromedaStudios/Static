// Real Chromium workflow against tests/ui_server.py. Does not call paid providers.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require(process.env.BUNS_PLAYWRIGHT_PATH || 'playwright');
const base = process.env.BUNS_TEST_URL || 'http://127.0.0.1:8765';
(async()=>{
  for(let i=0;i<40;i++){try{if((await fetch(base+'/api/health')).ok)break;}catch{} await new Promise(r=>setTimeout(r,250));}
  const browser=await chromium.launch({headless:true,executablePath:process.env.BUNS_CHROMIUM_PATH||undefined,args:['--no-sandbox','--disable-dev-shm-usage']});
  try{
    const page=await browser.newPage({viewport:{width:1440,height:1000},acceptDownloads:true});
    const errors=[];page.on('pageerror',e=>errors.push(e.message));
    await page.goto(base);await page.waitForFunction(()=>document.querySelector('#connection-label').textContent.includes('Ollama'));
    assert.match(await page.title(),/Buns/);
    fs.mkdirSync('test-results',{recursive:true});
    await page.screenshot({path:'test-results/desktop.png',fullPage:true});
    await page.locator('.nav-item[data-view="settings"]').click();
    await page.locator('.model-card summary').click();
    await page.getByRole('button',{name:'Test connection',exact:true}).click();
    await page.waitForFunction(()=>document.querySelector('.model-actions>span').textContent==='Connected');
    await page.locator('.nav-item[data-view="skills"]').click();
    await page.waitForSelector('.skill-card');
    assert.equal(await page.locator('.skill-card').count(),10);
    const toggle=page.getByRole('checkbox',{name:'Enable mesh_create'});
    await toggle.uncheck();await page.waitForFunction(()=>document.querySelector('#toast').textContent==='Skill updated');
    await toggle.check();
    await page.locator('#new-chat').click();
    await page.locator('#prompt').fill('Create a project plan as a Markdown file.');
    await page.locator('#send').click();
    await page.waitForSelector('.message.assistant');
    assert.match(await page.locator('.message.assistant').innerText(),/project-plan.md/);
    const downloadPromise=page.waitForEvent('download');
    await page.locator('.message.assistant a').click();
    const download=await downloadPromise;const file=await download.path();
    assert.match(fs.readFileSync(file,'utf8'),/# Project plan/);
    await page.reload();await page.locator('#recent button').first().click();
    await page.waitForSelector('.message.assistant');
    assert.equal(await page.locator('.message').count(),2);
    await page.locator('.nav-item[data-view="files"]').click();
    await page.waitForSelector('.file-card');
    assert.match(await page.locator('.file-card').first().innerText(),/project-plan.md/);
    await page.locator('#new-chat').click();
    await page.setViewportSize({width:390,height:844});
    await page.screenshot({path:'test-results/mobile.png',fullPage:true});
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'mobile horizontal overflow');
    await page.locator('#menu').click();
    await page.locator('.nav-item[data-view="settings"]').click();
    await page.waitForSelector('.model-card');
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'settings overflow');
    assert.deepEqual(errors,[]);
    console.log('Browser smoke passed: navigation, model settings, skill toggles, tool run, download, persistence, mobile layout.');
    console.log('Screenshots: '+path.resolve('test-results'));
  }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
