"""Read-only, bounded archive of linked public VL63 pages; never uses the anomalous sitemap."""
import argparse
import csv
import hashlib
import html
import json
import mimetypes
import re
import sys
import time
import urllib.error
import urllib.parse as urlparse
import urllib.request
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '.deps'))
from bs4 import BeautifulSoup

sys.stdout.reconfigure(encoding='utf-8')
ORIGIN = 'https://vl63.ru'
SITE_HOSTS = {'vl63.ru', 'www.vl63.ru'}
ASSET_HOSTS = SITE_HOSTS | {'ajax.googleapis.com', 'fonts.googleapis.com', 'fonts.gstatic.com', 'i.ytimg.com'}
ASSET_SUFFIXES = {'.jpg','.jpeg','.png','.gif','.svg','.webp','.avif','.ico','.bmp','.css','.js','.woff','.woff2','.ttf','.eot','.otf','.pdf','.swf'}
EXCLUDED_ROOTS = ('/administrator','/installation','/cli','/logs','/tmp','/libraries','/includes')
TRACKERS = re.compile(r'mc\.yandex|metrika|google-analytics|googletagmanager|VK\.Widgets|vk\.com/js|top\.mail\.ru|jivosite|facebook\.net', re.I)
CSS_URL = re.compile(r'url\(\s*([\"\x27]?)([^)\"\x27]+)\1\s*\)', re.I)
CSS_IMPORT = re.compile(r'@import\s+[\"\x27]([^\"\x27]+)[\"\x27]', re.I)
run_date = datetime.now(timezone.utc).isoformat()
manifest = {}
pages = []
failures = []
skipped = []
asset_queue = set()
total_bytes = 0
offline_mode = False


def absolute(raw, base=ORIGIN+'/'):
    if not raw or raw.startswith(('data:','blob:','#','javascript:','mailto:','tel:')):
        return None
    raw = html.unescape(raw.strip())
    parsed = urlparse.urlsplit(urlparse.urljoin(base, raw))
    if parsed.scheme not in ('http','https'):
        return None
    host = (parsed.hostname or '').lower()
    if host in SITE_HOSTS:
        host = 'vl63.ru'
    pathname = urlparse.quote(urlparse.unquote(parsed.path or '/'), safe='/!$&\x27()*+,;=:@-._~')
    return urlparse.urlunsplit(('https',host,pathname,parsed.query,''))


def page_url(raw, base=ORIGIN+'/'):
    value = absolute(raw, base)
    if not value:
        return None
    u = urlparse.urlsplit(value)
    if u.hostname != 'vl63.ru' or u.path.startswith(EXCLUDED_ROOTS) or '//' in u.path:
        return None
    if u.path.lower().endswith(tuple(ASSET_SUFFIXES)):
        return None
    if u.path not in ('/','/index.php') and not u.path.endswith(('.html','/')):
        return None
    params = dict(urlparse.parse_qsl(u.query, keep_blank_values=True))
    if any(key.lower() in params for key in ('task','format','tmpl','print','viewmode','sort','order','cookie')):
        return None
    allowed = {'start','limitstart'}
    if u.path == '/index.php' and params.get('option') in ('com_content','com_k2','com_virtuemart'):
        allowed |= {'option','view','id','Itemid','catid','virtuemart_category_id'}
    if set(params)-allowed:
        return None
    params = {k:v for k,v in params.items() if not (k in ('start','limitstart') and v=='0')}
    return urlparse.urlunsplit(('https','vl63.ru','/' if u.path=='/index.php' and not params else u.path,urlparse.urlencode(sorted(params.items())),''))


def local_path(url, is_page=False):
    u = urlparse.urlsplit(url)
    parts = []
    for part in u.path.split('/'):
        if not part:
            continue
        part = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', urlparse.unquote(part)).rstrip('. ')
        if part in ('.','..') or not part:
            raise ValueError('Invalid relative path')
        if len(part)>95:
            extension=Path(part).suffix[:8]
            part=part[:65]+'__'+hashlib.sha256(part.encode()).hexdigest()[:12]+extension
        if re.fullmatch(r'(?i)(con|prn|aux|nul|com\d|lpt\d)(\..*)?',part):
            part='_'+part
        parts.append(part)
    if not parts or u.path.endswith('/'):
        parts.append('index.html' if is_page else 'index')
    if is_page and not parts[-1].endswith('.html'):
        parts[-1] += '.html'
    if u.query:
        suffix=Path(parts[-1]).suffix
        stem=parts[-1][:-len(suffix)] if suffix else parts[-1]
        parts[-1]=stem+'__q_'+hashlib.sha256(u.query.encode()).hexdigest()[:10]+suffix
    if u.hostname!='vl63.ru':
        parts=['_external',u.hostname]+parts
        if u.hostname=='fonts.googleapis.com' and not parts[-1].endswith('.css'):
            parts[-1]+='.css'
    return '/'.join(parts)


def queue_asset(raw, base):
    value=absolute(raw,base)
    if value and urlparse.urlsplit(value).hostname in ASSET_HOSTS:
        asset_queue.add(value)
    return value


class SameScopeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urlparse.urlsplit(newurl).hostname not in ASSET_HOSTS:
            raise ValueError('Redirect outside archive scope')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch(url, kind):
    key=hashlib.sha256(url.encode()).hexdigest()
    cache=ROOT/'originals'/kind/(key+'.bin')
    meta=cache.with_suffix('.json')
    if cache.exists() and meta.exists():
        return url,cache.read_bytes(),json.loads(meta.read_text(encoding='utf-8')),None
    if offline_mode:
        return url,None,None,'not present in the cached snapshot'
    opener=urllib.request.build_opener(SameScopeRedirect())
    for attempt in range(2):
        try:
            time.sleep(.16)
            req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (compatible; VL63-PublicArchive/1.0)','Accept-Encoding':'identity'})
            with opener.open(req,timeout=25) as r:
                data=r.read(12_000_001)
                if len(data)>12_000_000:
                    raise ValueError('File exceeds 12 MB resource limit')
                info={'url':url,'final_url':r.url,'status':r.status,'content_type':r.headers.get_content_type(),'charset':r.headers.get_content_charset() or 'utf-8','downloaded_at':run_date,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
                cache.parent.mkdir(parents=True,exist_ok=True)
                cache.write_bytes(data)
                meta.write_text(json.dumps(info,ensure_ascii=False,indent=2),encoding='utf-8')
                return url,data,info,None
        except urllib.error.HTTPError as e:
            return url,None,None,f'HTTP {e.code}'
        except Exception as e:
            if attempt:
                return url,None,None,str(e)


def css_assets(source, base):
    for match in CSS_URL.finditer(source):
        queue_asset(match[2],base)
    for match in CSS_IMPORT.finditer(source):
        queue_asset(match[1],base)


def collect(source, url):
    soup=BeautifulSoup(source,'html.parser')
    base=soup.find('base',href=True)
    base_url=urlparse.urljoin(url,base['href']) if base else url
    links=[]
    for anchor in soup.find_all('a',href=True):
        full=absolute(anchor['href'],base_url)
        if full and Path(urlparse.urlsplit(full).path).suffix.lower() in ASSET_SUFFIXES:
            queue_asset(full,base_url)
        linked=page_url(anchor['href'],base_url)
        if linked:
            links.append(linked)
    for node in soup.find_all(True):
        for attr in ('src','poster','data-src','data-original','background'):
            if node.has_attr(attr) and node.name not in ('iframe','embed','object'):
                if not TRACKERS.search(str(node.get(attr))):
                    queue_asset(node[attr],base_url)
        if node.has_attr('srcset'):
            for candidate in node['srcset'].split(','):
                queue_asset(candidate.strip().split(' ')[0],base_url)
        if node.name=='link' and node.has_attr('href'):
            rel=' '.join(node.get('rel',[]))
            if 'stylesheet' in rel or 'icon' in rel:
                queue_asset(node['href'],base_url)
        if node.has_attr('style'):
            css_assets(node['style'],base_url)
    for style in soup.find_all('style'):
        css_assets(style.get_text(),base_url)
    return soup,base_url,list(dict.fromkeys(links))


def extract_content(soup,url,local,base):
    container=soup.select_one('.itemView') or soup.select_one('.item-page') or soup.select_one('.component') or soup.body
    clean=BeautifulSoup(str(container),'html.parser')
    for node in clean.select('script, style, form, .itemToolbar, .itemRatingBlock, .itemSocialSharing, .itemCommentsForm, .itemBackToTop'):
        node.decompose()
    title_node=clean.select_one('.itemTitle') or clean.find('h1') or clean.find('h2')
    title=title_node.get_text(' ',strip=True) if title_node else soup.title.get_text(' ',strip=True) if soup.title else url
    description=soup.find('meta',attrs={'name':re.compile('^description$',re.I)})
    keywords=soup.find('meta',attrs={'name':re.compile('^keywords$',re.I)})
    date=clean.select_one('.itemDateCreated') or clean.find('time')
    images=[]
    image_keys=set()
    def add_image(raw,role,alt='',title=''):
        src=absolute(raw,base)
        if src and (src,role) not in image_keys:
            image_keys.add((src,role))
            images.append({'url':src,'local_path':local_path(src),'alt':alt,'title':title,'role':role})
    for im in clean.find_all('img',src=True):
        if not im['src'].endswith('transparent.gif'):
            add_image(im['src'],'inline',im.get('alt',''),im.get('title',''))
    for node in clean.find_all(style=True):
        for match in CSS_URL.finditer(node['style']):
            add_image(match[2],'gallery-preview',node.get('alt',''),node.get('title',''))
    for node in clean.find_all('a',href=True):
        if Path(urlparse.urlsplit(node['href']).path).suffix.lower() in {'.jpg','.jpeg','.png','.webp','.gif'}:
            add_image(node['href'],'gallery-original',node.get('title',''))
            preview_node=node.find('img')
            if preview_node:
                match=CSS_URL.search(preview_node.get('style',''))
                preview=absolute(match[2] if match else preview_node.get('src',''),base)
                original=absolute(node['href'],base)
                for record in images:
                    if record['url']==original and record['role']=='gallery-original': record['preview_url']=preview
    item_match=re.search(r'/item/(\d+)',url)
    item_anchor=soup.find(id=re.compile(r'^startOfPageId\d+$'))
    source_id=int(item_match[1]) if item_match else int(re.search(r'\d+',item_anchor['id'])[0]) if item_anchor else None
    page_type='k2-item' if soup.select_one('.itemView') else 'joomla-article' if soup.select_one('.item-page') else 'listing-or-page'
    if url==ORIGIN+'/': page_type='homepage'
    intro=clean.select_one('.itemIntroText')
    full=clean.select_one('.itemFullText')
    body_text='\n\n'.join(n.get_text('\n',strip=True) for n in [intro,full] if n) if intro or full else clean.get_text('\n',strip=True)
    category=clean.select_one('.itemCategory a')
    tags=[n.get_text(' ',strip=True) for n in clean.select('.itemTags a')]
    return {'source_url':url,'local_path':local,'title':title,'page_type':page_type,'source_item_id':source_id,'published_text':date.get_text(' ',strip=True) if date else None,'category':category.get_text(' ',strip=True) if category else None,'tags':tags,'meta_description':description.get('content','') if description else '', 'meta_keywords':keywords.get('content','') if keywords else '', 'images':images,'intro_html':str(intro) if intro else '', 'full_html':str(full) if full else '', 'content_text':body_text,'content_html_original':str(clean),'downloaded_at':run_date}


def local_ref(raw,base,allow_page=True):
    if not raw or raw.startswith(('#','data:','blob:','mailto:','tel:','javascript:')):
        return raw
    full=absolute(raw,base)
    if not full:
        return raw
    fragment=urlparse.urlsplit(raw).fragment
    candidate=page_url(raw,base) if allow_page else None
    mapped=manifest.get(candidate or '') or manifest.get(full)
    if mapped:
        result='/'+mapped['local_path']
        return result+('#'+fragment if fragment else '')
    if urlparse.urlsplit(full).hostname=='vl63.ru':
        if candidate:
            return '/__archive_missing.html?source='+urlparse.quote(full,safe='')
        return '/'+local_path(full)
    return full


def rewrite_css(source,base):
    source=CSS_URL.sub(lambda m:'url("'+local_ref(m[2],base,False)+'")',source)
    return CSS_IMPORT.sub(lambda m:'@import "'+local_ref(m[1],base,False)+'"',source)


def rewrite_page(source,url):
    soup=BeautifulSoup(source,'html.parser')
    base_node=soup.find('base',href=True)
    base=urlparse.urljoin(url,base_node['href']) if base_node else url
    for node in soup.find_all('base'): node.decompose()
    for script in list(soup.find_all('script')):
        if TRACKERS.search(script.get('src','')+' '+script.get_text()):
            script.decompose()
    for node in list(soup.find_all(['iframe','object','embed'])):
        if node.attrs is None:
            continue
        remote=node.get('src') or node.get('data')
        if remote:
            link=soup.new_tag('a',href=urlparse.urljoin(base,remote),target='_blank',rel='noopener noreferrer')
            link.string='Открыть внешнее видео или виджет (нужен интернет)'
            node.replace_with(link)
        else: node.decompose()
    for link in list(soup.find_all('link')):
        if link.attrs is None:
            continue
        if 'alternate' in link.get('rel',[]) or 'canonical' in link.get('rel',[]):
            # Malformed legacy markup can make the parser nest later head
            # resources inside a void link element. Keep those resources.
            link.unwrap()
    for node in soup.find_all(True):
        for attr in ('href','src','poster','data-src','data-original','background'):
            if node.has_attr(attr):
                node[attr]=local_ref(node[attr],base,node.name=='a')
        if node.has_attr('srcset'):
            candidates=[]
            for candidate in node['srcset'].split(','):
                pieces=candidate.strip().split()
                if pieces:
                    pieces[0]=local_ref(pieces[0],base,False)
                    candidates.append(' '.join(pieces))
            node['srcset']=', '.join(candidates)
        if node.has_attr('style'): node['style']=rewrite_css(node['style'],base)
        if node.name=='form':
            node['action']='#'
            node['data-archive-form']='readonly'
        if node.name=='a' and node.get('href','').startswith('http'):
            node['target']='_blank'; node['rel']='noopener noreferrer'
    for style in soup.find_all('style'):
        style.string=rewrite_css(style.get_text(),base)
    for script in soup.find_all('script',src=False):
        value=script.get_text()
        value=re.sub(r'https?://(?:www\.)?vl63\.ru/', '/', value)
        script.string=value
    if soup.head:
        csp=soup.new_tag('meta',attrs={'http-equiv':'Content-Security-Policy','content':"default-src 'self' data: blob:; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self' data:; connect-src 'self'; frame-src 'none'; form-action 'none'; object-src 'none'; base-uri 'self'"})
        soup.head.insert(0,csp)
        charset=soup.new_tag('meta',charset='utf-8');soup.head.insert(0,charset)
        robots=soup.new_tag('meta',attrs={'name':'robots','content':'noindex,nofollow'});soup.head.insert(0,robots)
        runtime=soup.new_tag('script',src='/__archive-runtime.js');soup.head.insert(3,runtime)
    return str(soup)


def write_outputs():
    public=ROOT/'public'; public.mkdir(exist_ok=True)
    (ROOT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    for url,entry in manifest.items():
        raw=ROOT/entry['original_path']
        data=raw.read_bytes()
        dest=public/entry['local_path']; dest.parent.mkdir(parents=True,exist_ok=True)
        if entry['kind']=='pages':
            source=data.decode(entry['charset'],errors='replace')
            dest.write_text(rewrite_page(source,url),encoding='utf-8')
        elif entry['content_type']=='text/css' or urlparse.urlsplit(url).path.endswith('.css'):
            dest.write_text(rewrite_css(data.decode('utf-8',errors='replace'),url),encoding='utf-8')
        else: dest.write_bytes(data)
    (public/'__archive-runtime.js').write_text("document.addEventListener('submit',function(e){e.preventDefault();e.stopImmediatePropagation();alert('Это локальный архив. Отправка формы доступна только на действующем сайте.');},true);",encoding='utf-8')
    (public/'__archive_missing.html').write_text('<!doctype html><html lang="ru"><meta charset="utf-8"><title>Страница вне архива</title><body><h1>Страница не сохранена в архив</h1><p>Причина указана в отчёте архива. Вернитесь к сохранённым материалам.</p><p><a href="/">Главная</a> · <a href="/archive-index.html">Список сохранённых страниц</a></p></body></html>',encoding='utf-8')
    content=ROOT/'content'; content.mkdir(exist_ok=True)
    for record in pages:
        for im in record['images']:
            im['downloaded']=im['url'] in manifest
        record['content_html_local']=rewrite_page(record['content_html_original'],record['source_url'])
        key=hashlib.sha256(record['source_url'].encode()).hexdigest()[:16]
        record['text_file']='articles/'+key+'.md'
        out=content/record['text_file'];out.parent.mkdir(exist_ok=True)
        out.write_text('# '+record['title']+'\n\nИсточник: '+record['source_url']+'\n\n'+record['content_text']+'\n',encoding='utf-8')
    (content/'pages.json').write_text(json.dumps(pages,ensure_ascii=False,indent=2),encoding='utf-8')
    with (content/'pages.csv').open('w',encoding='utf-8-sig',newline='') as handle:
        fields=['source_url','local_path','title','page_type','source_item_id','published_text','meta_description','text_file']
        writer=csv.DictWriter(handle,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(pages)
    associations={}
    for record in pages:
        for im in record['images']:
            associations.setdefault(im['url'],[]).append(record['source_url'])
    images=[]
    for url,entry in manifest.items():
        if entry['content_type'].startswith('image/'):
            images.append({'source_url':url,'local_path':entry['local_path'],'bytes':entry['bytes'],'sha256':entry['sha256'],'used_in_content':associations.get(url,[])})
    (content/'images.json').write_text(json.dumps(images,ensure_ascii=False,indent=2),encoding='utf-8')
    with (content/'images.csv').open('w',encoding='utf-8-sig',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=['source_url','local_path','bytes','sha256']);writer.writeheader();writer.writerows({k:v for k,v in row.items() if k!='used_in_content'} for row in images)
    with (content/'redirect-map.csv').open('w',encoding='utf-8-sig',newline='') as handle:
        writer=csv.writer(handle);writer.writerow(['old_url','archive_path','new_url','decision'])
        writer.writerows([r['source_url'],r['local_path'],'','review'] for r in pages)
    listing=''.join('<li><a href="/'+html.escape(r['local_path'])+'">'+html.escape(r['title'])+'</a> <small>'+html.escape(r['page_type'])+'</small></li>' for r in pages)
    (public/'archive-index.html').write_text('<!doctype html><html lang="ru"><meta charset="utf-8"><title>VL63 — локальный архив</title><style>body{font:17px/1.6 Arial;max-width:1000px;margin:40px auto;padding:0 24px}li{margin:12px 0}small{color:#555}input{font:inherit;padding:10px;width:100%;box-sizing:border-box}a{color:#164b68}</style><h1>VL63 — локальный архив</h1><p>Публичные материалы для редизайна. <a href="/">Открыть главную сайта</a></p><p>'+str(len(pages))+' страниц · '+str(len(images))+' изображений</p><label for="search">Найти материал по названию</label><input id="search" type="search"><ul>'+listing+'</ul><script>document.getElementById("search").addEventListener("input",function(){var q=this.value.toLocaleLowerCase();document.querySelectorAll("li").forEach(function(li){li.hidden=!li.textContent.toLocaleLowerCase().includes(q);});});</script></html>',encoding='utf-8')
    (ROOT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    summary={'created_at':run_date,'source':ORIGIN,'pages':len(pages),'assets':sum(e['kind']=='assets' for e in manifest.values()),'images':len(images),'downloaded_bytes':sum(e['bytes'] for e in manifest.values()),'page_types':{t:sum(r['page_type']==t for r in pages) for t in sorted(set(r['page_type'] for r in pages))},'failures':failures,'skipped':skipped,'sitemap_used':False,'scope':'Linked public pages and their assets; no database, server PHP, private administration, or submitted forms.'}
    (ROOT/'crawl-report.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print('DONE '+json.dumps({k:v for k,v in summary.items() if k not in ('failures','skipped')},ensure_ascii=False),flush=True)
    print(f'Failures: {len(failures)}; skipped: {len(skipped)}',flush=True)


def main():
    global total_bytes, manifest, failures, skipped, offline_mode
    parser=argparse.ArgumentParser();parser.add_argument('--max-pages',type=int,default=420);parser.add_argument('--max-assets',type=int,default=3500);parser.add_argument('--max-mb',type=int,default=600);parser.add_argument('--rebuild',action='store_true');parser.add_argument('--offline',action='store_true',help='Build only from cached responses, with no network access')
    args=parser.parse_args()
    offline_mode=args.offline
    if args.rebuild:
        manifest=json.loads((ROOT/'manifest.json').read_text(encoding='utf-8'))
        old_report=json.loads((ROOT/'crawl-report.json').read_text(encoding='utf-8'))
        failures=old_report['failures'];skipped=old_report['skipped']
        for url,entry in manifest.items():
            if entry['kind']=='pages':
                source=(ROOT/entry['original_path']).read_bytes().decode(entry['charset'],errors='replace')
                soup,base,_=collect(source,url)
                pages.append(extract_content(soup,url,entry['local_path'],base))
        write_outputs()
        return
    queue=deque([ORIGIN+'/']); seen=set()
    with ThreadPoolExecutor(max_workers=3) as pool:
        while queue and len(pages)<args.max_pages:
            batch=[]
            while queue and len(batch)<3 and len(pages)+len(batch)<args.max_pages:
                url=queue.popleft()
                if url not in seen: seen.add(url);batch.append(url)
            if not batch: continue
            for url,data,info,error in pool.map(lambda u:fetch(u,'pages'),batch):
                if error: failures.append({'url':url,'kind':'page','error':error});continue
                if info['content_type']!='text/html': skipped.append({'url':url,'reason':'not-html'});continue
                source=data.decode(info['charset'],errors='replace')
                soup,base,links=collect(source,url)
                if len(soup.get_text(' ',strip=True))<100:
                    failures.append({'url':url,'kind':'page','error':'empty/challenge page'});continue
                local=local_path(url,True)
                info.update({'local_path':local,'kind':'pages','original_path':'originals/pages/'+hashlib.sha256(url.encode()).hexdigest()+'.bin'})
                manifest[url]=info;total_bytes+=len(data)
                record=extract_content(soup,url,local,base);pages.append(record)
                for link in links:
                    if link not in seen: queue.append(link)
            if len(pages)%15<3: print(f'Pages {len(pages)}; queued {len(set(queue)-seen)}; asset references {len(asset_queue)}',flush=True)
        skipped.extend({'url':u,'reason':'page-limit'} for u in sorted(set(queue)-seen))
        attempted=set()
        while asset_queue-attempted and len(attempted)<args.max_assets and total_bytes<args.max_mb*1_000_000:
            todo=sorted(asset_queue-attempted,key=lambda u:(Path(urlparse.urlsplit(u).path).suffix not in {'.css','.js','.woff','.woff2','.ttf','.eot'},u))[:min(30,args.max_assets-len(attempted))]
            attempted.update(todo)
            for url,data,info,error in pool.map(lambda u:fetch(u,'assets'),todo):
                if error:failures.append({'url':url,'kind':'asset','error':error});continue
                if info['content_type']=='text/html':failures.append({'url':url,'kind':'asset','error':'HTML instead of asset'});continue
                info.update({'local_path':local_path(url),'kind':'assets','original_path':'originals/assets/'+hashlib.sha256(url.encode()).hexdigest()+'.bin'})
                manifest[url]=info;total_bytes+=len(data)
                if info['content_type']=='text/css' or urlparse.urlsplit(url).path.endswith('.css'):
                    css_assets(data.decode('utf-8',errors='replace'),url)
            print(f'Assets {len(attempted)}/{len(asset_queue)}; {total_bytes/1_000_000:.1f} MB',flush=True)
        skipped.extend({'url':u,'reason':'asset-or-byte-limit'} for u in sorted(asset_queue-attempted))
    write_outputs()


if __name__=='__main__': main()
