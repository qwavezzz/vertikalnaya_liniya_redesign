import json
import re
import sys
import urllib.request
import urllib.error
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
root = Path(__file__).resolve().parents[1]
evidence = root / 'evidence'
evidence.mkdir(parents=True, exist_ok=True)
report = []
for name, url in [('home', 'https://vl63.ru/'), ('robots', 'https://vl63.ru/robots.txt'), ('sitemap', 'https://vl63.ru/sitemap.xml')]:
    try:
        request = urllib.request.Request(url, headers={'User-Agent':'VL63-LocalArchive/1.0 (public content research)'})
        with urllib.request.urlopen(request, timeout=35) as response:
            data = response.read(8_000_000)
            charset = response.headers.get_content_charset() or 'utf-8'
            page = data.decode(charset, errors='replace')
            (evidence / f'{name}.source.txt').write_text(page, encoding='utf-8')
            headers = {k:v for k,v in response.headers.items() if k.lower() not in ('set-cookie',)}
            entry = {'name':name,'url':url,'final_url':response.url,'status':response.status,'headers':headers,'bytes':len(data)}
            if name == 'home':
                entry['meta'] = re.findall(r'<meta\b[^>]+>', page, re.I)
                entry['scripts'] = re.findall(r'<script\b[^>]*src=[\"\x27]([^\"\x27]+)', page, re.I)
                entry['stylesheets'] = re.findall(r'<link\b[^>]+>', page, re.I)
                entry['links'] = list(dict.fromkeys(re.findall(r'href=[\"\x27]([^\"\x27]+)',page,re.I)))[:130]
            else:
                entry['body_excerpt'] = page[:9000]
            report.append(entry)
    except Exception as error:
        report.append({'name':name,'url':url,'error':str(error)})
(evidence / 'http-inspection.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(report, ensure_ascii=False, indent=2))
