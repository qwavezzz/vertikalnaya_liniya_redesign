const { chromium } = require('C:/Users/Admin/AppData/Local/npm-cache/_npx/e41f203b7505f1fb/node_modules/playwright');
const fs = require('fs');
const path = require('path');
const root = path.resolve(__dirname, '..');

(async () => {
  const browser = await chromium.launch({headless:true,executablePath:'C:/Users/Admin/AppData/Local/ms-playwright/chromium-1228/chrome-win64/chrome.exe'});
  const report = [];
  try {
    for (const [name,url,viewport] of [
      ['source-desktop','https://vl63.ru/',{width:1440,height:1000}],
      ['source-mobile','https://vl63.ru/',{width:390,height:844}],
      ['source-gallery','https://vl63.ru/nashi_raboty.html',{width:1440,height:1000}],
      ['source-article','https://vl63.ru/news/item/316-populyarnyj-v-tolyatti-nakladnoj-svetilnik-dlya-natyazhnyh-potolkov.html',{width:1440,height:1000}],
    ]) {
      const page = await browser.newPage({viewport});
      const errors=[];
      page.on('pageerror', e=>errors.push(e.message));
      await page.goto(url,{waitUntil:'domcontentloaded',timeout:45000});
      await page.waitForTimeout(1500);
      const height = await page.evaluate(()=>document.documentElement.scrollHeight);
      for (let y=0;y<Math.min(height,15000);y+=800) {
        await page.evaluate(y=>window.scrollTo(0,y),y);await page.waitForTimeout(140);
      }
      await page.evaluate(()=>window.scrollTo(0,0));
      await page.screenshot({path:path.join(root,'evidence',name+'.png'),fullPage:true});
      await page.screenshot({path:path.join(root,'evidence',name+'-viewport.png')});
      const data=await page.evaluate(()=>({title:document.title,url:location.href,width:innerWidth,scrollWidth:document.documentElement.scrollWidth,images:document.images.length,loadedImages:[...document.images].filter(i=>i.complete&&i.naturalWidth).length,forms:[...document.forms].map(f=>({action:f.action,method:f.method})),mainClasses:[...document.querySelectorAll('.component>*')].map(n=>({tag:n.tagName,id:n.id,classes:n.className})),links:[...document.querySelectorAll('.component a[href]')].slice(0,30).map(a=>({text:a.textContent.trim(),href:a.href}))}));
      report.push({name,...data,errors});
      console.log(name,data.title,data.loadedImages+'/'+data.images,JSON.stringify(errors));
      await page.close();
    }
    fs.writeFileSync(path.join(root,'evidence','browser-source.json'),JSON.stringify(report,null,2));
  } finally {await browser.close();}
})();
