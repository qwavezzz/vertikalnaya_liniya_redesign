const { chromium } = require('C:/Users/Admin/AppData/Local/npm-cache/_npx/e41f203b7505f1fb/node_modules/playwright');
const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');
const root = path.resolve(__dirname, '..');
const origin = 'http://127.0.0.1:4173';
const records = JSON.parse(fs.readFileSync(path.join(root,'content/pages.json'),'utf8'));

async function startServer() {
  try {
    const response=await fetch(origin+'/archive-index.html');
    if (response.ok && (await response.text()).includes('VL63')) return;
    throw new Error('Port 4173 belongs to a different service');
  } catch(error) {
    if (!String(error).includes('fetch failed')) throw error;
  }
  const log=fs.openSync(path.join(root,'server.log'),'a');
  const child=spawn('python',[path.join(root,'serve.py')],{cwd:root,detached:true,windowsHide:true,stdio:['ignore',log,log]});
  fs.writeFileSync(path.join(root,'server.pid'),String(child.pid));
  child.unref();
  for (let i=0;i<30;i++) {
    try {if((await fetch(origin)).ok)return;} catch {}
    await new Promise(resolve=>setTimeout(resolve,200));
  }
  throw new Error('Local server did not start');
}

(async()=>{
  await startServer();
  const browser=await chromium.launch({headless:true,executablePath:'C:/Users/Admin/AppData/Local/ms-playwright/chromium-1228/chrome-win64/chrome.exe'});
  const checks=[];
  const requests=[];
  const failures=[];
  const missing=[];
  try {
    const sourceArticle='https://vl63.ru/news/item/316-populyarnyj-v-tolyatti-nakladnoj-svetilnik-dlya-natyazhnyh-potolkov.html';
    const article=records.find(r=>r.source_url===sourceArticle);
    if(!article) throw new Error('Expected sample article is absent');
    const samples=[
      ['local-desktop','/',{width:1440,height:1000}],
      ['local-mobile','/',{width:390,height:844}],
      ['local-gallery','/nashi_raboty.html',{width:1440,height:1000}],
      ['local-article','/'+article.local_path,{width:1440,height:1000}],
      ['local-contact','/contacts.html',{width:1440,height:1000}],
      ['local-photos','/photo-index.html',{width:1440,height:1000}],
    ];
    for(const [name,url,viewport] of samples){
      const context=await browser.newContext({viewport});
      await context.route('**/*',route=>{
        const u=route.request().url();
        if(u.startsWith(origin)||u.startsWith('data:'))route.continue();
        else {requests.push({page:name,url:u});route.abort();}
      });
      const page=await context.newPage();
      const errors=[];
      page.on('pageerror',e=>errors.push(e.message));
      page.on('response',r=>{if(r.status()>=400)missing.push({page:name,status:r.status(),url:r.url()});});
      const response=await page.goto(origin+url,{waitUntil:'networkidle',timeout:45000});
      await page.waitForTimeout(500);
      if(name!=='local-photos'){
        const height=await page.evaluate(()=>document.documentElement.scrollHeight);
        for(let y=0;y<Math.min(height,15000);y+=900){await page.evaluate(y=>window.scrollTo(0,y),y);await page.waitForTimeout(70);}
        await page.evaluate(()=>window.scrollTo(0,0));
      }
      await page.screenshot({path:path.join(root,'evidence',name+'-viewport.png')});
      if(name==='local-desktop'||name==='local-mobile') await page.screenshot({path:path.join(root,'evidence',name+'.png'),fullPage:true});
      const data=await page.evaluate(()=>({title:document.title,scrollWidth:document.documentElement.scrollWidth,viewport:innerWidth,images:document.images.length,loadedImages:[...document.images].filter(i=>i.complete&&i.naturalWidth).length,brokenImages:[...document.images].filter(i=>i.complete&&!i.naturalWidth).map(i=>i.src),textLength:document.body.innerText.length}));
      const check={name,url:origin+url,status:response.status(),...data,errors,interactions:[]};
      if(name==='local-desktop'){
        const consent=page.getByRole('button',{name:'Принять',exact:true});
        if(await consent.count()){
          await consent.click();
          await consent.waitFor({state:'hidden',timeout:2000});
          check.interactions.push({name:'cookie notice close',passed:!await consent.isVisible()});
        }
        await page.locator('a[href="/nashi_raboty.html"]').first().click();
        await page.waitForURL('**/nashi_raboty.html');
        check.interactions.push({name:'navigation to gallery',passed:page.url()===origin+'/nashi_raboty.html'});
      }
      if(name==='local-mobile'){
        const toggle=page.locator('a.btn-navbar[data-target=".ot-sliding-100"]');
        if(await toggle.isVisible()){
          await toggle.click();await page.waitForTimeout(450);
          const visible=await page.locator('.ot-sliding-100 a[href="/nashi_raboty.html"]').first().isVisible();
          check.interactions.push({name:'mobile navigation opens',passed:visible});
        } else check.interactions.push({name:'mobile menu control present',passed:false});
      }
      if(name==='local-gallery'){
        const link=page.locator('a.sigProLink').first();
        const href=await link.getAttribute('href');
        const photo=await context.request.get(new URL(href,origin).href);
        check.interactions.push({name:'gallery original image opens locally',passed:photo.ok()&&photo.headers()['content-type']?.startsWith('image/')});
      }
      if(name==='local-photos'){
        const before=await page.locator('figure:visible').count();
        await page.locator('#filter').fill('бассейн');
        const after=await page.locator('figure:visible').count();
        check.interactions.push({name:'photo search',passed:after>0&&after<before,before,after});
      }
      checks.push(check);
      if(response.status()!==200||data.brokenImages.length||check.interactions.some(i=>!i.passed)) failures.push(name);
      console.log(name,JSON.stringify({images:data.loadedImages+'/'+data.images,errors,interactions:check.interactions}));
      await context.close();
    }
    const body=await (await fetch(origin+'/archive-index.html')).text();
    checks.push({name:'content index',passed:body.includes(String(records.length)+' страниц')});
    const report={tested_at:new Date().toISOString(),origin,pages:checks,external_network_attempts:requests,missing_resources:missing,failed_samples:failures,notes:['Network to all non-local hosts was blocked during checks.','Historical source JavaScript errors are documented separately in browser-source.json.','No forms were submitted to the public website.']};
    fs.writeFileSync(path.join(root,'verification.json'),JSON.stringify(report,null,2));
    if(failures.length||missing.length||requests.length)console.log('REVIEW',JSON.stringify({failures,missing:missing.length,external:requests.length}));
  } finally {await browser.close();}
})();
