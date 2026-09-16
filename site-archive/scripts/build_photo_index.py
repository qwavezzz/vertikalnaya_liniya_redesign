"""Create a local, deduplicated photo selection index from downloaded public material."""
import html
import json
from pathlib import Path

root=Path(__file__).resolve().parents[1]
manifest=json.loads((root/'manifest.json').read_text(encoding='utf-8'))
pages=json.loads((root/'content/pages.json').read_text(encoding='utf-8'))
selected={}
for page in pages:
    for image in page['images']:
        item=manifest.get(image['url'])
        if not item or not item['content_type'].startswith('image/') or item['bytes']<10000:
            continue
        if image.get('role') not in ('gallery-original','inline'):
            continue
        if not item['local_path'].startswith(('images/','media/k2/')):
            continue
        key=item['sha256']
        preview=manifest.get(image.get('preview_url',''))
        if key not in selected:
            selected[key]={'source_url':image['url'],'local_path':item['local_path'],'preview_path':preview['local_path'] if preview else item['local_path'],'bytes':item['bytes'],'sha256':key,'alt':image.get('alt',''),'pages':[]}
        entry={'title':page['title'],'url':page['source_url'],'local_path':page['local_path']}
        if entry not in selected[key]['pages']: selected[key]['pages'].append(entry)

photos=list(selected.values())
(root/'content/photo-selection.json').write_text(json.dumps(photos,ensure_ascii=False,indent=2),encoding='utf-8')
cards=[]
for photo in photos:
    original='/'+photo['local_path']
    preview='/'+photo['preview_path']
    label=photo['pages'][0]['title']
    context=' '.join(p['title'] for p in photo['pages'])
    cards.append('<figure data-search="'+html.escape(context.lower(),quote=True)+'"><a href="'+html.escape(original,quote=True)+'" target="_blank"><img loading="lazy" src="'+html.escape(preview,quote=True)+'" alt="'+html.escape(photo['alt'] or label,quote=True)+'"></a><figcaption><a href="/'+html.escape(photo['pages'][0]['local_path'],quote=True)+'">'+html.escape(label)+'</a><small>'+html.escape(photo['local_path'])+' · '+str(round(photo['bytes']/1024))+' KB</small><a class="download" href="'+html.escape(original,quote=True)+'" download>Скачать фото</a></figcaption></figure>')
document='''<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"><title>Фотографии VL63 для редизайна</title><style>body{font:16px/1.5 Arial;margin:32px auto;max-width:1380px;padding:0 24px;color:#192126}a{color:#164b68}header{max-width:850px}input{box-sizing:border-box;font:inherit;width:100%;padding:12px;margin:12px 0 24px;border:1px solid #7a858c}main{display:grid;grid-template-columns:repeat(auto-fill,minmax(270px,1fr));gap:24px}figure{margin:0}img{display:block;width:100%;aspect-ratio:4/3;object-fit:cover;background:#eee}figcaption{padding:10px 0}small{display:block;color:#526068;font-size:12px;overflow-wrap:anywhere}.download{display:inline-block;margin-top:8px}figure[hidden]{display:none}</style><header><h1>Фотографии для редизайна</h1><p>Доступные оригиналы и иллюстрации из содержимого vl63.ru, без одинаковых по содержимому файлов. Это кандидаты для отбора: принадлежность к реальному проекту проверяется по связанной статье.</p><p><a href="/">Сайт</a> · <a href="/archive-index.html">Статьи и разделы</a></p><p id="count"></p><label for="filter">Поиск по названию материала</label><input type="search" id="filter" placeholder="Например: бассейн, световые, кухня"></header><main>'''+''.join(cards)+'''</main><script>var cards=[...document.querySelectorAll('figure')];function filter(){var q=document.getElementById('filter').value.toLocaleLowerCase();cards.forEach(function(c){c.hidden=!c.dataset.search.includes(q)});document.getElementById('count').textContent='Показано '+cards.filter(c=>!c.hidden).length+' из '+cards.length+' файлов'}document.getElementById('filter').addEventListener('input',filter);filter();</script></html>'''
(root/'public/photo-index.html').write_text(document,encoding='utf-8')
print(f'Photo selection: {len(photos)} distinct files')
