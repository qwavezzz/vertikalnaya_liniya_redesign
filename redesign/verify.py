"""Browser smoke checks for all variants. Uses installed Chromium and websockets.

Outputs stay in .impeccable/site-checks. Nothing is sent, posted or submitted remotely.
"""
import argparse
import base64
import json
import os
import re
import subprocess
import tempfile
import time
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit, unquote
from websockets.sync.client import connect

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '.impeccable/site-checks'
OUT.mkdir(exist_ok=True)
CHROME = os.environ.get('REDESIGN_CHROME', r'C:/Users/Admin/AppData/Local/ms-playwright/chromium-1228/chrome-win64/chrome.exe')
MANIFEST = json.loads((ROOT/'redesign/build-manifest.json').read_text(encoding='utf-8'))
report = {'static_pages':0,'routes':[],'interactions':[],'layouts':[],'errors':[],'external_requests':[]}

class References(HTMLParser):
    def handle_starttag(self, tag, attrs):
        attrs=dict(attrs)
        for attr in ('href','src'):
            value=attrs.get(attr,'')
            parsed=urlsplit(value)
            if not value or parsed.scheme or value.startswith('#'): continue
            target=unquote(parsed.path)
            if target: self.links.add(target)

for output in MANIFEST['outputs']:
    directory=ROOT/Path(output['entry']).parent
    for page in directory.glob('*.html'):
        parser=References(); parser.links=set(); parser.feed(page.read_text(encoding='utf-8'))
        for reference in parser.links:
            assert (directory/reference).is_file(), (page.name,reference)
        report['static_pages']+=1

PROFILE=Path(tempfile.mkdtemp(prefix='browser-',dir=OUT))
process=subprocess.Popen([CHROME,'--headless=new','--no-sandbox','--remote-debugging-port=0',f'--user-data-dir={PROFILE}','--no-first-run','--no-default-browser-check','--disable-background-networking','--disable-component-update','about:blank'],stdout=subprocess.DEVNULL,stderr=(OUT/'browser.log').open('w'),creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
counter=0
try:
    deadline=time.monotonic()+20
    while not (PROFILE/'DevToolsActivePort').exists():
        assert time.monotonic()<deadline and process.poll() is None,'Browser failed to start'
        time.sleep(.2)
    port=(PROFILE/'DevToolsActivePort').read_text().splitlines()[0]
    targets=json.load(urllib.request.urlopen(f'http://127.0.0.1:{port}/json'))
    target=next(p for p in targets if p['type']=='page')
    with connect(target['webSocketDebuggerUrl'],max_size=25_000_000) as socket:
        def cdp(method,params=None):
            global counter
            counter+=1
            socket.send(json.dumps({'id':counter,'method':method,'params':params or {}}))
            while True:
                r=json.loads(socket.recv(timeout=35))
                if r.get('id')==counter:
                    assert 'error' not in r,r
                    return r.get('result',{})
                if r.get('method')=='Runtime.exceptionThrown': report['errors'].append(r['params'])
                if r.get('method')=='Network.requestWillBeSent':
                    url=r['params']['request']['url']
                    if url.startswith(('https:','http:')): report['external_requests'].append(url)
        def js(expression):
            r=cdp('Runtime.evaluate',{'expression':expression,'returnByValue':True,'awaitPromise':True})
            assert 'exceptionDetails' not in r,r
            return r['result'].get('value')
        def until(expression):
            deadline=time.monotonic()+15
            while not js(f'document.body && ({expression})'):
                assert time.monotonic()<deadline,expression
                time.sleep(.05)
        def viewport(w,h):
            cdp('Emulation.setDeviceMetricsOverride',{'width':w,'height':h,'deviceScaleFactor':1,'mobile':False})
        def load(path,suffix=''):
            cdp('Page.navigate',{'url':path.as_uri()+suffix})
            until("document.readyState==='complete' && !!document.querySelector('#app h1')")
            ready()
        def ready():
            js("document.querySelectorAll('#app img[data-asset]').forEach(i=>i.loading='eager')")
            until("[...document.querySelectorAll('#app img[data-asset]')].every(i=>i.complete && i.naturalWidth>0)")
            js('document.fonts.ready.then(()=>true)')
        def route(name):
            js(f'location.hash={json.dumps("#/"+name)}')
            expected=name.split('?')[0]
            until(f'document.body.dataset.page==={json.dumps(expected)}')
            ready()
        def shot(name,width=1003,height=1568):
            cdp('Runtime.evaluate',{'expression':'scrollTo(0,0)'})
            result=cdp('Page.captureScreenshot',{'format':'png','captureBeyondViewport':True,'clip':{'x':0,'y':0,'width':width,'height':height,'scale':1}})
            (OUT/f'{name}.png').write_bytes(base64.b64decode(result['data']))
        def click(selector): js(f'document.querySelector({json.dumps(selector)}).click()')
        cdp('Page.enable'); cdp('Runtime.enable'); cdp('Network.enable')
        cdp('Network.emulateNetworkConditions',{'offline':True,'latency':0,'downloadThroughput':0,'uploadThroughput':0})
        for number in (1,2,3):
            viewport(1003,790)
            portable=ROOT/f'variant-{number}.html'
            load(portable)
            shot(f'variant-{number}-home-desktop')
            for name in MANIFEST['outputs'][number-1]['routes']:
                route(name)
                result=js("({page:document.body.dataset.page,h1:document.querySelectorAll('#app h1').length,broken:[...document.querySelectorAll('#app img[data-asset]')].filter(i=>!i.naturalWidth).length,overflow:document.documentElement.scrollWidth>innerWidth})")
                assert result['h1']==1 and not result['broken'] and not result['overflow'],result
                report['routes'].append({'variant':number,**result})
            route('ceiling-floating')
            shot(f'variant-{number}-service-desktop',1003,1500)
            click('details summary')
            assert js('document.querySelector("details").open')
            click('[data-lightbox]')
            assert js('document.getElementById("photo-dialog").open')
            cdp('Input.dispatchKeyEvent',{'type':'keyDown','key':'Escape','code':'Escape','windowsVirtualKeyCode':27})
            cdp('Input.dispatchKeyEvent',{'type':'keyUp','key':'Escape','code':'Escape','windowsVirtualKeyCode':27})
            assert not js('document.getElementById("photo-dialog").open')
            click('a[href="#/contacts?solution=floating"]')
            until('document.body.dataset.page==="contacts"')
            assert js('document.getElementById("client-solution").value')=='floating'
            click('#contact-form button[type=submit]')
            assert js('document.getElementById("client-contact").getAttribute("aria-invalid")')=='true'
            js("document.getElementById('client-contact').value='test@example.ru'; document.getElementById('client-name').value='Тест'; document.getElementById('client-message').value='Гостиная, нужен свет по периметру.'")
            click('#contact-form button[type=submit]')
            assert not js('document.getElementById("mail-preview").hidden')
            assert js('document.getElementById("mail-link").href').startswith('mailto:potolok63@yandex.ru?')
            shot(f'variant-{number}-contacts-desktop',1003,1500)
            route('projects')
            click('[data-filter="business"]')
            assert js('[...document.querySelectorAll("[data-filter-item]")].filter(i=>!i.hidden).length')==3
            js("let search=document.querySelector('input[data-search]'); search.value='несуществующий проект'; search.dispatchEvent(new Event('input',{bubbles:true}))")
            assert not js('document.querySelector("[data-empty]").hidden')
            click('[data-reset-filter]')
            assert js('[...document.querySelectorAll("[data-filter-item]")].filter(i=>!i.hidden).length')==5
            route('journal')
            click('[data-filter="Освещение"]')
            assert js('[...document.querySelectorAll("[data-filter-item]")].filter(i=>!i.hidden).length')==1
            route('article-light-planning')
            click('.article-toc a')
            assert js('location.hash')=='#/article-light-planning'
            route('projects')
            route('about')
            js('history.back()')
            until('document.body.dataset.page==="projects"')
            # Reloading an address preserves its page.
            cdp('Page.reload')
            until('document.body.dataset.page==="projects"')
            ready()
            # Returning to the initial empty hash restores the home page.
            load(portable)
            route('about')
            js('history.back()')
            until('document.body.dataset.page==="index"')
            for width,height in ((1440,1000),(1024,768),(768,1024),(390,844),(320,780)):
                viewport(width,height)
                for name in ('index','solutions','ceiling-floating','projects','journal','contacts'):
                    route(name)
                    dims=js('({width:innerWidth,scrollWidth:document.documentElement.scrollWidth})')
                    if dims['scrollWidth']>width:
                        dims['overflow_nodes']=js("[...document.querySelectorAll('#app *')].filter(e=>{const r=e.getBoundingClientRect();return r.width>0 && r.right>innerWidth+1 && getComputedStyle(e).position!=='absolute'}).slice(0,16).map(e=>({tag:e.tagName,cls:e.className,width:e.getBoundingClientRect().width,right:e.getBoundingClientRect().right}))")
                        print('OVERFLOW',number,name,dims,flush=True)
                    report['layouts'].append({'variant':number,'page':name,**dims})
                    if width==390 and name in ('index','ceiling-floating','contacts'):
                        shot(f'variant-{number}-{name}-mobile',390,1600 if name!='index' else 844)
            viewport(390,844)
            route('index')
            click('[data-open-menu]')
            assert js('document.getElementById("mobile-menu").open')
            shot(f'variant-{number}-menu-mobile',390,844)
            click('#mobile-menu a[href="#/solutions"]')
            until('document.body.dataset.page==="solutions"')
            assert not js('document.body.classList.contains("modal-open")')
            # Check conventional HTML navigation, not just the portable router.
            viewport(1440,1000)
            load(ROOT/f'redesign/variant-{number}/index.html')
            click('.nav-group a[href="solutions.html"]')
            until('document.body.dataset.page==="solutions"')
            ready()
            click('a[href="ceiling-floating.html"]')
            until('document.body.dataset.page==="ceiling-floating"')
            ready()
            report['interactions'].append({'variant':number,'passed':['FAQ','lightbox/Escape','prefilled enquiry','validation','mail preview without sending','project filters/search/empty/reset','article filters/anchors','back/reload','home without hash','mobile menu','static HTML navigation']})
            print(f'Variant {number}: all routes, interactions and widths passed',flush=True)
        assert not report['errors'],report['errors']
        assert not report['external_requests'],report['external_requests']
        (OUT/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        assert all(item['scrollWidth']<=item['width'] for item in report['layouts']), 'Responsive overflow; see verification.json'
        print(f"PASS: {report['static_pages']} static pages, {len(report['routes'])} offline routes, {len(report['layouts'])} layouts; no external requests or runtime errors")
finally:
    process.terminate()
    process.wait(timeout=10)
