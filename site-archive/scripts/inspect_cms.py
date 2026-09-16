import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
root=Path(__file__).resolve().parents[1]
report=[]
for name,path in [('joomla-manifest','/administrator/manifests/files/joomla.xml'),('template-manifest','/templates/ot_print/templateDetails.xml'),('admin-login','/administrator/')]:
    url='https://vl63.ru'+path
    try:
        with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'VL63-LocalArchive/1.0'}),timeout=25) as r:
            source=r.read(1_000_000).decode('utf-8',errors='replace')
            (root/'evidence'/f'{name}.source.txt').write_text(source,encoding='utf-8')
            report.append({'url':url,'status':r.status,'excerpt':source[:4500] if 'manifest' in name else re.findall(r'<title>.*?</title>|<meta[^>]+>|<form[^>]+>|<input[^>]+>',source,re.I)[:15]})
    except Exception as e:
        report.append({'url':url,'error':str(e)})
sitemap=ET.fromstring((root/'evidence'/'sitemap.source.txt').read_text(encoding='utf-8'))
urls=[e.text for e in sitemap.iter() if e.tag.endswith('}loc')]
report.append({'sitemap_urls':len(urls),'triple_slash':sum('vl63.ru///' in u for u in urls),'examples':urls[:5]})
(root/'evidence'/'cms-inspection.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2))
