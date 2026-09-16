import json
import sys
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlsplit, unquote

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'.deps'))
from bs4 import BeautifulSoup

manifest=json.loads((root/'manifest.json').read_text(encoding='utf-8'))
pages=json.loads((root/'content/pages.json').read_text(encoding='utf-8'))
paths=defaultdict(list)
missing_files=[]
for url,item in manifest.items():
    paths[item['local_path'].casefold()].append({'url':url,'sha256':item['sha256']})
    for base,key in [('public','local_path'),('','original_path')]:
        if not (root/base/item[key]).is_file():missing_files.append(item[key])
collisions={p:entries for p,entries in paths.items() if len({e['sha256'] for e in entries})>1}
broken_links=defaultdict(set)
missing_assets=defaultdict(set)
external_assets=defaultdict(set)
for page in pages:
    source=(root/'public'/page['local_path']).read_text(encoding='utf-8')
    soup=BeautifulSoup(source,'html.parser')
    for node in soup.find_all(True):
        pairs=[]
        if node.name=='a' and node.get('href'):pairs.append(('link',node['href']))
        if node.name in ('img','script','source') and node.get('src'):pairs.append(('asset',node['src']))
        if node.name=='link' and 'stylesheet' in node.get('rel',[]):pairs.append(('asset',node['href']))
        for kind,value in pairs:
            if value.startswith('/'):
                parsed=urlsplit(value)
                destination=root/'public'/unquote(parsed.path.lstrip('/'))
                if destination.is_dir():destination=destination/'index.html'
                if not destination.is_file():
                    (broken_links if kind=='link' else missing_assets)[value].add(page['source_url'])
            elif kind=='asset' and value.startswith(('https:','http:','//')):
                external_assets[value].add(page['source_url'])
report={'pages':len(pages),'manifest_files':len(manifest),'missing_files':missing_files,'case_collisions':collisions,'broken_local_links':{u:sorted(v) for u,v in broken_links.items()},'unavailable_local_assets':{u:sorted(v) for u,v in missing_assets.items()},'external_active_assets':{u:sorted(v) for u,v in external_assets.items()},'empty_text_records':[p['source_url'] for p in pages if not p['content_text'].strip()]}
(root/'file-audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:len(v) if isinstance(v,(dict,list)) else v for k,v in report.items()}))
