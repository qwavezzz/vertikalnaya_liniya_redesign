"""Build three offline prototypes and three conventional static multipage sites.

Run from any directory: python redesign/build.py
No packages or network required; all source assets live next to this file.
"""
from __future__ import annotations
import base64
import html
import json
import re
import shutil
from pathlib import Path
from content import SERVICES, PROJECTS, ARTICLES, STEPS, VARIANTS

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
MANIFEST = json.loads((HERE / 'asset-manifest.json').read_text(encoding='utf-8'))
ASSETS = {item['id']: item for item in MANIFEST['images']}
PAGE_SOURCES = {}
ESC = html.escape

def href(route='index', query=''):
    return f'{route}.html' + (f'?{query}' if query else '')

def link(route, text, cls='', query=''):
    return f'<a href="{href(route, query)}" class="{cls}">{ESC(text)}</a>'

def image(asset, cls='', eager=False, alt=None):
    item = ASSETS[asset]
    return (f'<img src="{item["file"]}" data-asset="{asset}" class="{cls}" '
            f'width="{item["width"]}" height="{item["height"]}" alt="{ESC(alt or item["alt"], quote=True)}" '
            + ('fetchpriority="high" loading="eager"' if eager else 'loading="lazy"') + ' decoding="async">')

def lightbox(asset, label='Увеличить фотографию'):
    return f'<button type="button" class="image-button" data-lightbox="{asset}" aria-label="{ESC(label)}">{image(asset)}<span class="zoom-label">Увеличить</span></button>'

def brand(cls=''):
    return f'<a class="wordmark {cls}" href="index.html" aria-label="Вертикальная линия — главная"><span>ВЕРТИКАЛЬНАЯ</span><span>ЛИНИЯ</span></a>'

def header(route):
    active = 'solutions' if route.startswith('ceiling-') else 'projects' if route.startswith('project-') else 'journal' if route.startswith('article-') else route
    def nav(dest, label, cls=''):
        current = ' aria-current="page"' if active == dest else ''
        return f'<a href="{href(dest)}" class="{cls}"{current}>{label}</a>'
    links = [('solutions','Решения'),('projects','Проекты'),('about','О компании'),('journal','Полезное'),('partners','Дизайнерам'),('contacts','Контакты')]
    return f'''<a class="skip-link" href="#main">К содержанию</a>
<header class="site-header"><div class="wrap header-grid">
<nav class="nav-group" aria-label="Решения и проекты">{nav('solutions','Решения')}{nav('projects','Проекты')}</nav>
{brand()}
<nav class="nav-group right" aria-label="Компания и контакты">{nav('about','О компании')}{nav('contacts','Контакты')}{nav('contacts','Обсудить проект','button outline')}</nav>
<button class="menu-toggle" type="button" data-open-menu aria-haspopup="dialog" aria-controls="mobile-menu">Меню</button>
</div></header>
<dialog class="mobile-menu" id="mobile-menu" aria-label="Навигация по сайту"><div class="menu-top">{brand()}<button class="dialog-close" type="button" data-close-dialog autofocus>Закрыть</button></div>
<nav>{''.join(nav(r,t) for r,t in links)}</nav><div class="menu-contact"><p>Тольятти · Самара · Сызрань</p><a href="tel:+78482503206">+7 (8482) 503-206</a><a href="mailto:potolok63@yandex.ru">potolok63@yandex.ru</a></div></dialog>'''

def cta():
    return f'''<section class="contact-band"><div class="wrap"><div><h2>Обсудим ваше пространство</h2><p>Расскажите, какой потолок вы представляете. Начнём с задачи, света и деталей интерьера.</p></div>{link('contacts','Обсудить проект','button white')}</div></section>'''

def footer():
    initial_photo = image('hero').replace('<img ', '<img id="enlarged-photo" ', 1)
    return f'''<footer class="site-footer"><div class="wrap"><div class="footer-top">
<div class="footer-brand-block">{brand('footer-brand')}<p>Натяжные потолки и освещение.<br>Тольятти · Самара · Сызрань</p></div>
<nav class="footer-links" aria-label="Решения в подвале">{link('solutions','Все решения')}{link('ceiling-floating','Парящие потолки')}{link('ceiling-luminous','Световые потолки')}{link('projects','Проекты')}</nav>
<nav class="footer-links" aria-label="Информация о компании">{link('about','О компании')}{link('journal','Полезные материалы')}{link('partners','Дизайнерам и архитекторам')}{link('materials','Материалы и документы')}{link('contacts','Контакты')}</nav>
<div class="footer-contact"><a href="tel:+78482503206">+7 (8482) 503-206</a><a href="mailto:potolok63@yandex.ru">potolok63@yandex.ru</a><p>Тольятти, ул. Ворошилова, 32а</p></div>
</div><div class="footer-bottom"><span>© Вертикальная линия</span>{link('privacy','Конфиденциальность')}</div></div></footer>
<dialog class="photo-dialog" id="photo-dialog" aria-label="Просмотр фотографии"><div class="dialog-top"><strong>Детали пространства</strong><button class="dialog-close" type="button" data-close-dialog autofocus>Закрыть</button></div>{initial_photo}<p class="photo-caption" id="photo-caption"></p></dialog>'''

def crumbs(label, parent=None):
    middle = link(*parent) if parent else ''
    return f'<nav class="wrap breadcrumbs" aria-label="Хлебные крошки">{link("index","Главная")}<span aria-hidden="true">/</span>{middle + "<span aria-hidden=\"true\">/</span>" if middle else ""}<span aria-current="page">{ESC(label)}</span></nav>'

def heading(title, lead='', label=None):
    return crumbs(label or title) + f'<div class="wrap page-heading"><h1 tabindex="-1">{ESC(title)}</h1>{f"<p class=\"lead\">{ESC(lead)}</p>" if lead else ""}</div>'

def section_head(title, dest=None, label=None):
    return f'<div class="section-head"><h2>{ESC(title)}</h2>{link(dest,label,"text-link") if dest else ""}</div>'

def project_card(project, filterable=False):
    attrs = f' data-filter-item data-category="{project["type"]}" data-search="{ESC(project["title"] + " " + project["lead"], quote=True)}"' if filterable else ''
    return f'''<a href="{href('project-'+project['slug'])}" class="project-preview"{attrs}>
{image(project['image'])}<p class="project-meta">{project['type_label']}</p><h3>{ESC(project['title'])}</h3></a>'''

def solution_row(service, number):
    asset = 'beauty' if service['slug'] == 'luminous' else service['image']
    return f'''<article class="solution-row"><a class="solution-image" href="{href('ceiling-'+service['slug'])}" aria-label="{ESC(service['title'])}">{image(asset)}</a>
<div class="solution-copy"><p class="solution-no">{number:02d} / {ESC(service['title']).upper()}</p><h3>{ESC(service['short'])}</h3><p class="muted">{ESC(service['lead'])}</p><ul class="spec-list">{''.join(f'<li>{ESC(x)}</li>' for x in service['features'][:3])}</ul>{link('ceiling-'+service['slug'],'Подробнее о решении','text-link')}</div></article>'''

def steps():
    return '<div class="steps">' + ''.join(f'<article class="step"><span class="step-number">0{i}</span><h3>{title}</h3><p>{desc}</p></article>' for i,(title,desc) in enumerate(STEPS,1)) + '</div>'

def home(number):
    variant = VARIANTS[number]
    primary = 'button white' if number == 2 else 'button'
    secondary = 'secondary-action' if number == 2 else 'button outline'
    hero = f'''<section class="hero">{image('hero','hero-photo',True)}<div class="hero-content">
<p class="hero-label">НАТЯЖНЫЕ ПОТОЛКИ И ОСВЕЩЕНИЕ</p><h1 tabindex="-1">Пространство<br>начинается со света</h1><p class="lead">Потолок и освещение, продуманные вместе с вашим интерьером</p><div class="actions">{link('contacts','Обсудить проект',primary)}{link('solutions','Выбрать решение',secondary)}</div></div><p class="hero-place">Тольятти · Самара · Сызрань</p></section>'''
    intro_title = ESC(variant['intro']).replace('\n','<br>')
    detail = f'<div class="detail-crop">{image("hero")}</div>'
    if number == 1:
        intro = f'<section class="wrap intro-album"><p class="intro-label">ПАРЯЩИЕ ПОТОЛКИ</p><h2>{intro_title}</h2>{detail}</section>'
    elif number == 2:
        intro = f'<section class="intro-geometry"><div class="intro-copy"><h2>{intro_title}</h2></div><div class="detail-crop">{image("hero")}<p class="detail-caption">Подсветка по периметру</p></div></section>'
    else:
        intro = f'<section class="wrap intro-space"><p class="intro-label">ПОТОЛОК. СВЕТ. ПРОСТРАНСТВО.</p><div><h2>{intro_title}</h2><p class="lead">Натяжные потолки и освещение, которые гармонично дополняют интерьер. Решения для дома, квартиры и коммерческих пространств.</p></div></section>'
    services = [SERVICES[1], SERVICES[0], SERVICES[2]]
    categories = '<nav class="category-nav" aria-label="Направления">' + ''.join(link('ceiling-'+s['slug'],s['title']) for s in SERVICES) + '</nav>'
    extra = '<div class="more-solutions">' + ''.join(f'<a href="{href("ceiling-"+s["slug"])}"><h3>{s["title"]}</h3><p>{s["lead"]}</p></a>' for s in SERVICES[3:]) + '</div>'
    catalogue = f'<section class="wrap section home-solutions"><div class="section-head"><h2>Решения для вашего пространства</h2></div>{categories}{"".join(solution_row(s,i) for i,s in enumerate(services,1))}{extra}</section>'
    story = f'''<section class="blue-story">{image('installation')}<div class="story-copy"><h2>Красивый результат.<br>Продуманная конструкция.</h2><p>Профиль, полотно, свет и примыкания работают вместе. Важно заранее учесть расположение светильников, ниш и коммуникаций.</p>{link('article-before-installation','Что продумать до монтажа','text-link')}</div></section>'''
    projects = f'''<section class="section home-projects"><div class="wrap">{section_head('Проекты и интерьеры','projects','Смотреть все проекты')}<div class="projects-highlight">{project_card(PROJECTS[1])}<div class="project-stack">{project_card(PROJECTS[0])}{project_card(PROJECTS[3])}</div></div></div></section>'''
    process = f'<section class="section soft"><div class="wrap">{section_head("От идеи до готового потолка")}{steps()}</div></section>'
    journal = f'<section class="wrap section">{section_head("Полезно до начала ремонта","journal","Все материалы")}<div class="journal-list">{"".join(article_card(a) for a in ARTICLES[:3])}</div></section>'
    return hero + intro + catalogue + story + projects + process + journal + cta()

def solutions():
    body = heading('Решения для вашего пространства','От спокойной матовой поверхности до светового потолка. Выберите направление, чтобы рассмотреть детали и примеры.','Решения')
    return body + '<section class="wrap section" style="padding-top:0">' + ''.join(solution_row(s,i) for i,s in enumerate(SERVICES,1)) + '</section>' + cta()

def service_page(s):
    heroasset = 'beauty' if s['slug'] == 'luminous' else 'glossy' if s['slug'] == 'shapes' else s['image']
    body = crumbs(s['title'],('solutions','Решения')) + f'''<section class="wrap service-hero"><div class="service-title"><h1 tabindex="-1">{s['title']}</h1><p class="lead">{s['lead']}</p><div class="actions">{link('contacts','Обсудить решение','button','solution='+s['slug'])}{link('projects','Смотреть проекты','text-link')}</div></div>{image(heroasset,'service-photo',True)}</section>'''
    body += f'''<section class="section soft"><div class="wrap reading-layout"><div><h2 class="aside-title">{ESC(s['short'])}</h2><nav class="aside-links" aria-label="Другие решения">{''.join(link('ceiling-'+x['slug'],x['title'],'text-link') for x in SERVICES if x['slug']!=s['slug'])}</nav></div><div class="prose">{''.join('<p>'+ESC(p)+'</p>' for p in s['paragraphs'])}<div class="features">{''.join('<span>'+ESC(f)+'</span>' for f in s['features'])}</div></div></div></section>'''
    detailasset = s['image'] if s['image'] != heroasset else 'installation'
    body += f'<section class="wrap section">{section_head("Решение в деталях")}<div class="gallery">{lightbox(heroasset)}{lightbox(detailasset)}</div><p class="note">{s["note"]}</p></section>'
    body += f'<section class="wrap section" style="padding-top:0">{section_head("Частые вопросы")}<div class="faq">' + ''.join(f'<details><summary>{q}</summary><p>{a}</p></details>' for q,a in s['faq']) + '</div></section>'
    PAGE_SOURCES['ceiling-'+s['slug']] = s['source']
    return body + cta()

def filter_controls(kind):
    if kind == 'projects':
        filters = [('all','Все проекты'),('home','Жилые'),('business','Для бизнеса'),('public','Общественные')]
        noun = 'проектам'
    else:
        filters = [('all','Все материалы'),('Подготовка','Подготовка'),('Выбор решения','Выбор решения'),('Освещение','Освещение'),('Эксплуатация','Эксплуатация')]
        noun = 'материалам'
    return '<div class="filters" aria-label="Фильтр">' + ''.join(f'<button type="button" class="filter-button" data-filter="{key}" aria-pressed="{str(key=="all").lower()}">{text}</button>' for key,text in filters) + f'</div><div class="search-row"><div class="search-field"><label for="content-search">Поиск по {noun}</label><input id="content-search" type="search" data-search placeholder="Введите название или слово"></div><p class="results-count" data-count aria-live="polite"></p></div>'

def empty_state():
    return '<div class="empty-state" data-empty hidden><h2>Ничего не найдено</h2><p>Попробуйте другое слово или посмотрите все материалы.</p><button class="button outline" type="button" data-reset-filter>Сбросить фильтры</button></div>'

def projects():
    return heading('Проекты и интерьеры','Жилые комнаты, рестораны, гостиницы и общественные пространства. Посмотрите, как разные решения работают в интерьере.','Проекты') + f'<section class="wrap section" style="padding-top:0" data-filter-scope>{filter_controls("projects")}<div class="projects-grid">{"".join(project_card(p,True) for p in PROJECTS)}</div>{empty_state()}</section>' + cta()

def project_page(p):
    body = crumbs(p['title'],('projects','Проекты')) + f'<div class="wrap page-heading"><h1 tabindex="-1">{p["title"]}</h1><p class="lead">{p["lead"]}</p></div><div class="wrap">{image(p["image"],"project-cover" + (" compact" if p["slug"]=="pool" else ""),True)}</div>'
    details = ''.join(f'<dt>{key}</dt><dd>{val}</dd>' for key,val in p['details'])
    body += f'<section class="wrap section" style="padding-top:0"><div class="project-details"><dl>{details}</dl><div class="prose"><p>{p["text"]}</p><div class="actions">{link("ceiling-"+p["solution"],"О потолочном решении","button outline")}{link("contacts","Обсудить похожую задачу","text-link","solution="+p["solution"])}</div></div></div>'
    pics = [p['image']]
    # Only a photograph from the same known project can be an additional project view.
    if p['secondary'] in ASSETS and p['slug'] == 'sushka':
        pics.append(p['secondary'])
    body += f'<div class="gallery {"single" if len(pics)==1 else ""}">{"".join(lightbox(a) for a in pics)}</div></section>'
    others = [x for x in PROJECTS if x['slug'] != p['slug']][:2]
    body += f'<section class="section soft"><div class="wrap">{section_head("Другие пространства","projects","Все проекты")}<div class="projects-grid">{"".join(project_card(x) for x in others)}</div></div></section>'
    PAGE_SOURCES['project-'+p['slug']] = p['source']
    return body + cta()

def article_card(a, filterable=False):
    attrs = f' data-filter-item data-category="{a["category"]}" data-search="{ESC(a["title"] + " " + a["lead"],quote=True)}"' if filterable else ''
    return f'<a class="article-card" href="{href("article-"+a["slug"])}"{attrs}>{image(a["image"])}<p class="article-category">{a["category"]}</p><h2>{a["title"]}</h2><p>{a["lead"]}</p></a>'

def journal():
    return heading('До, во время и после ремонта','Понятно о выборе потолка, освещении, подготовке помещения и уходе.','Полезные материалы') + f'<section class="wrap section" style="padding-top:0" data-filter-scope>{filter_controls("journal")}<div class="journal-list">{"".join(article_card(a,True) for a in ARTICLES)}</div>{empty_state()}</section>' + cta()

def article_page(a):
    sections = ''.join(f'<section id="part-{i}"><h2>{title}</h2><p>{body}</p></section>' for i,(title,body) in enumerate(a['sections'],1))
    toc = ''.join(f'<a href="#part-{i}">{title}</a>' for i,(title,_) in enumerate(a['sections'],1))
    PAGE_SOURCES['article-'+a['slug']] = a['source']
    return crumbs(a['category'],('journal','Полезные материалы')) + f'<div class="wrap page-heading"><h1 tabindex="-1">{a["title"]}</h1><p class="lead">{a["lead"]}</p></div><div class="wrap">{image(a["image"],"article-lead-image",True)}</div><div class="wrap article-layout"><nav class="article-toc" aria-label="В этой статье"><h2>В этой статье</h2>{toc}</nav><article class="prose">{sections}<p class="source-note">По материалам компании «Вертикальная линия». Особенности конкретного помещения и актуальные условия работ уточняйте при обращении.</p>{link("journal","Все полезные материалы","text-link")}</article></div>' + cta()

def about():
    return heading('Потолок — часть целого','Помогаем связать поверхность, свет и детали в одном пространстве.','О компании') + f'''<section class="wrap about-intro">{image('restaurant','',True)}<div><h2>«Вертикальная линия»</h2><p class="lead">Компания работает с натяжными потолками в Тольятти, Самаре и Сызрани.</p><p>Тольяттинская компания под брендом «Вертикальная линия» появилась в 2005 году. В материалах сайта — жилые интерьеры, рестораны, гостиницы и общественные пространства.</p><p>Для нас потолок связан с остальным интерьером: его геометрией, светильниками, шторами и деталями отделки. Поэтому обсуждение начинается с пространства целиком.</p><div class="about-links">{link('projects','Посмотреть проекты','text-link')}{link('materials','Материалы и документы','text-link')}</div></div></section><section class="wrap section">{section_head('Как строится работа')}{steps()}</section><section class="section soft"><div class="wrap reading-layout"><h2>Вместе с дизайнером</h2><div class="prose"><p>Сотрудничаем с архитекторами, дизайнерами и специалистами по отделке. Технические детали потолка и освещения удобно обсудить на этапе проектирования.</p>{link('partners','Условия сотрудничества','text-link')}</div></div></section>''' + cta()

def partners():
    return heading('Для дизайнеров и архитекторов','Обсудим конструкцию потолка на языке вашего проекта.','Сотрудничество') + f'''<div class="wrap">{image('glossy','project-cover',True)}</div><section class="wrap section reading-layout"><h2>От замысла к деталям</h2><div class="prose"><p>Приглашаем к сотрудничеству дизайнеров, архитекторов и специалистов, работающих с внутренней отделкой помещений.</p><p>Техническую консультацию можно начать с плана, разрезов, схемы освещения и визуальных ориентиров. Вместе уточним фактуру, конструкцию, примыкания и доступ к оборудованию.</p><h2>Что подготовить</h2><ul><li>План помещения и основные размеры.</li><li>Схему света, карнизов и встроенного оборудования.</li><li>Разрезы сложных узлов и высотные отметки.</li><li>Фотографии объекта и примеры желаемого результата.</li></ul><p>Каталоги, образцы и условия взаимодействия уточняйте в офисе компании.</p><div class="actions">{link('contacts','Обсудить сотрудничество','button')}{link('projects','Посмотреть проекты','text-link')}</div></div></section>''' + cta()

def materials():
    return heading('Материалы и документы','Фактуру, цвет и конструкцию выбирают вместе с задачей помещения.','Материалы') + f'''<section class="wrap reading-layout"><h2>Выбор поверхности</h2><div class="prose"><p>В материалах компании представлены матовые, сатиновые и глянцевые плёнки, цветные и светопропускающие поверхности. Образцы помогают сравнить отражения и характер света.</p><p>Наличие конкретных материалов и действующие документы для выбранного полотна уточняются при заказе.</p>{link('ceiling-classic','Натяжные потолки и фактуры','text-link')}</div></section><section class="wrap section"><h2>Документы из архива</h2><p class="lead" style="margin-top:24px">Сканы, опубликованные на исходном сайте. Для заказа запросите актуальные документы на выбранный материал.</p><div class="document-grid"><figure>{lightbox('certificate-germany','Открыть архивный сертификат на немецкую плёнку')}<figcaption><h3>Немецкая плёнка</h3><p class="muted small">Архивная копия</p></figcaption></figure><figure>{lightbox('certificate-msd','Открыть архивный документ MSD')}<figcaption><h3>Материал MSD</h3><p class="muted small">Архивная копия</p></figcaption></figure></div></section>''' + cta()

def contacts():
    options = ''.join(f'<option value="{s["slug"]}">{s["title"]}</option>' for s in SERVICES)
    return heading('Обсудим ваше пространство','Расскажите о задаче, пришлите план или фотографии. Подберём направление и уточним детали.','Контакты') + f'''<div class="wrap contact-layout"><div class="contact-info"><div><h2>Связаться с нами</h2><a class="phone" href="tel:+78482503206">+7 (8482) 503-206</a><a class="email" href="mailto:potolok63@yandex.ru">potolok63@yandex.ru</a><div class="city-list"><span>Тольятти</span><span>Самара</span><span>Сызрань</span></div><h2>Основной офис</h2><address>Тольятти, ул. Ворошилова, 32а</address><a class="text-link" href="https://yandex.ru/maps/?text=%D0%A2%D0%BE%D0%BB%D1%8C%D1%8F%D1%82%D1%82%D0%B8%20%D0%92%D0%BE%D1%80%D0%BE%D1%88%D0%B8%D0%BB%D0%BE%D0%B2%D0%B0%2032%D0%B0" target="_blank" rel="noopener noreferrer">Открыть на карте</a><p class="small muted" style="margin-top:16px">Перед визитом уточните время работы по телефону.</p></div><div><h2>Дополнительные офисы</h2><div class="office"><h3>ТЦ «МегаСТРОЙ»</h3><p>Тольятти, ул. Громовой, 33</p><a class="text-link" href="tel:+78482408330">+7 (8482) 408-330</a></div><div class="office"><h3>ТЦ «МегаСВЕТ»</h3><p>Тольятти, Автозаводское шоссе, 10</p><a class="text-link" href="tel:+78482408303">+7 (8482) 408-303</a></div><p class="small muted">ООО «Вертикальная линия-Т»<br>ИНН 6321153257 · ОГРН 1056320184656</p></div></div>
<section class="form-panel"><h2>С чего начнём?</h2><p>Подготовьте обращение — затем откройте его в своей почте и добавьте файлы проекта.</p><form id="contact-form" novalidate>
<div class="field"><label for="client-name">Ваше имя <span>— необязательно</span></label><input id="client-name" name="name" autocomplete="name" maxlength="100" placeholder="Как к вам обращаться"></div>
<div class="field"><label for="client-contact">Телефон или email</label><input id="client-contact" name="contact" autocomplete="email" required maxlength="160" aria-describedby="contact-error" placeholder="+7 или name@example.ru"><p class="field-error" id="contact-error" hidden></p></div>
<div class="field-pair"><div class="field"><label for="client-city">Город</label><select id="client-city" name="city"><option>Тольятти</option><option>Самара</option><option>Сызрань</option><option>Другой населённый пункт</option></select></div><div class="field"><label for="client-solution">Решение</label><select id="client-solution" name="solution"><option value="">Пока выбираю</option>{options}</select></div></div>
<div class="field"><label for="client-message">О вашем пространстве <span>— необязательно</span></label><textarea id="client-message" name="message" maxlength="2000" placeholder="Например: гостиная, 24 м², хочется подсветку по периметру"></textarea></div>
<button class="button" type="submit">Подготовить обращение</button><p class="form-help">Данные остаются в этом окне до отправки из вашей почтовой программы. {link('privacy','О конфиденциальности')}</p>
<div class="mail-preview" id="mail-preview" hidden aria-live="polite"><h3 tabindex="-1">Письмо готово к проверке</h3><pre id="mail-body"></pre><a class="button" id="mail-link" href="mailto:potolok63@yandex.ru">Открыть почтовую программу</a><p class="form-help">Добавьте фотографии или план и отправьте письмо из своей почты. Здесь письмо ещё не отправлено.</p></div></form></section></div>'''

def privacy():
    return heading('Конфиденциальность','Как работает обращение через эту версию сайта.') + '''<article class="wrap prose legal-text section" style="padding-top:0"><h2>Подготовка обращения</h2><p>Введённые в форму имя, контакт и описание задачи используются в вашем браузере для подготовки текста письма. Форма не отправляет их на сервер и не сохраняет после закрытия страницы.</p><h2>Отправка по электронной почте</h2><p>Кнопка «Открыть почтовую программу» передаёт текст установленному почтовому приложению. Письмо будет отправлено компании только после вашего действия в этой программе. При необходимости можно написать напрямую на potolok63@yandex.ru.</p><h2>Локальное хранение и аналитика</h2><p>В этой версии не используются аналитические счётчики, рекламные системы, cookies или постоянное хранение введённых данных. Переход к карте открывает внешний сервис по вашему действию.</p><h2>Вопросы об обращении</h2><p>Получатель письма — ООО «Вертикальная линия-Т». По вопросам, связанным с обращением, можно связаться с компанией по адресу potolok63@yandex.ru или телефону +7 (8482) 503-206.</p></article>'''

def all_pages(number):
    pages = {
        'index': ('Натяжные потолки и освещение', home(number)),
        'solutions': ('Решения', solutions()),
        'projects': ('Проекты', projects()),
        'about': ('О компании', about()),
        'partners': ('Дизайнерам и архитекторам', partners()),
        'journal': ('Полезные материалы', journal()),
        'materials': ('Материалы и документы', materials()),
        'contacts': ('Контакты', contacts()),
        'privacy': ('Конфиденциальность', privacy()),
        '404': ('Страница не найдена', '<section class="wrap not-found"><h1 tabindex="-1">Такой страницы нет</h1><p>Вернитесь к решениям или начните с главной.</p><div class="actions">'+link('index','На главную','button')+link('solutions','Выбрать решение','button outline')+'</div></section>')
    }
    pages.update({'ceiling-'+s['slug']: (s['title'], service_page(s)) for s in SERVICES})
    pages.update({'project-'+p['slug']: (p['title'], project_page(p)) for p in PROJECTS})
    pages.update({'article-'+a['slug']: (a['title'], article_page(a)) for a in ARTICLES})
    return pages

def contract(number):
    return f'''<!-- THESIS: Variant {number}, {VARIANTS[number]['name']}: real ceiling imagery leads a usable multipage company website.
OWN-WORLD: Source Sans 3, white and cool gray, graphite, deep blue; square photographs and precise low-radius controls.
STORY: See the interior, choose a ceiling, inspect a project, understand preparation, compose an enquiry.
FIRST VIEWPORT: Centered wordmark with split navigation; full-width original room photograph; lower centered headline and enquiry action. Variant-specific next section follows the selected comp.
FORM: Architecture portfolio; explicitly selected by the user's request to implement all three existing concepts, 2026-09-21.
FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, and DESIGN.md -->'''

def shell(route, title, content):
    return header(route) + f'<main id="main" tabindex="-1">{content}</main>' + footer()

def document(number, route, title, body, css, js, tail=''):
    theme = VARIANTS[number]['theme']
    classes = f'theme-{theme}' + (' home' if route=='index' else '')
    return f'''<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="color-scheme" content="light"><meta name="description" content="Натяжные потолки и освещение. Компания Вертикальная линия. Тольятти, Самара, Сызрань."><title>{ESC(title)} — Вертикальная линия</title>{css}</head><body class="{classes}" data-page="{route}" data-variant="{number}">{contract(number)}<div id="app">{body}</div>{tail}{js}</body></html>'''

def portable_body(body):
    body = re.sub(r'href="([a-z0-9-]+)\.html(\?[^"<>]*)?"', lambda m: 'href="#/'+m[1]+(m[2] or '')+'"', body)
    body = re.sub(r' src="assets/[^"]+"(?= data-asset=)', '', body)
    return body

def build():
    css = (HERE / 'styles.css').read_text(encoding='utf-8')
    js = (HERE / 'site.js').read_text(encoding='utf-8')
    shutil.copyfile(HERE / 'launch.html', ROOT / 'redesign-options.html')
    image_data = {a['id']: {'src': 'data:image/jpeg;base64,' + base64.b64encode((HERE/a['file']).read_bytes()).decode('ascii'), 'alt': a['alt']} for a in MANIFEST['images']}
    font_path = HERE / 'assets/source-sans-3-variable.woff2'
    portable_css = css.replace("url('assets/source-sans-3-variable.woff2')", "url('data:font/woff2;base64,"+base64.b64encode(font_path.read_bytes()).decode('ascii')+"')")
    outputs = []
    for number in VARIANTS:
        pages = all_pages(number)
        dest = HERE / f'variant-{number}'
        dest.mkdir(exist_ok=True)
        assetsdir = dest / 'assets'
        assetsdir.mkdir(exist_ok=True)
        for item in MANIFEST['images']:
            shutil.copyfile(HERE / item['file'], assetsdir / Path(item['file']).name)
        for name in ['source-sans-3-variable.woff2','Source-Sans-3-LICENSE.md']:
            shutil.copyfile(HERE / 'assets' / name, assetsdir / name)
        (dest/'styles.css').write_text(css,encoding='utf-8')
        (dest/'site.js').write_text(js,encoding='utf-8')
        for route,(title,content) in pages.items():
            html_doc = document(number,route,title,shell(route,title,content),'<link rel="stylesheet" href="styles.css">','<script src="site.js"></script>')
            (dest/(route+'.html')).write_text(html_doc,encoding='utf-8')
        titles = {route:title for route,(title,_) in pages.items()}
        templates = ''.join(f'<template id="page-{route}">{portable_body(shell(route,title,content))}</template>' for route,(title,content) in pages.items())
        config = json.dumps({'titles':titles,'assets':image_data},ensure_ascii=False).replace('<','\\u003c')
        tail = templates + '<script id="site-data" type="application/json">'+config+'</script><noscript><p>Для переходов между страницами этого файла включите JavaScript в браузере. Также доступна обычная версия сайта с отдельными HTML-страницами.</p></noscript>'
        standalone = document(number,'index',pages['index'][0],portable_body(shell('index',pages['index'][0],pages['index'][1])),f'<style>{portable_css}</style>',f'<script>{js}</script>',tail)
        target = ROOT / f'variant-{number}.html'
        target.write_text(standalone,encoding='utf-8')
        outputs.append({'variant':number,'name':VARIANTS[number]['name'],'standalone':target.name,'bytes':target.stat().st_size,'pages':len(pages),'entry':f'redesign/variant-{number}/index.html','routes':list(pages)})
    (HERE/'build-manifest.json').write_text(json.dumps({'outputs':outputs,'sources':PAGE_SOURCES},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(outputs,ensure_ascii=False,indent=2))

if __name__ == '__main__':
    build()
