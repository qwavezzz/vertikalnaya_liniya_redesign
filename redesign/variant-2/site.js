(() => {
  'use strict';
  const dataNode = document.getElementById('site-data');
  const data = dataNode ? JSON.parse(dataNode.textContent) : null;
  const app = document.getElementById('app');
  let lastFocus = null;
  let scrollPending = false;
  let filters = { category: 'all', search: '' };

  function hydrateImages(root = app) {
    if (!data) return;
    root.querySelectorAll('img[data-asset]').forEach(img => {
      const asset = data.assets[img.dataset.asset];
      if (asset) img.src = asset.src;
    });
  }

  function routeInfo() {
    if (data) {
      const route = location.hash.startsWith('#/') ? location.hash.slice(2) : 'index';
      const split = route.indexOf('?');
      return { route: split < 0 ? route : route.slice(0, split), query: new URLSearchParams(split < 0 ? '' : route.slice(split + 1)) };
    }
    return { route: document.body.dataset.page, query: new URLSearchParams(location.search) };
  }

  function closeDialog(dialog) {
    if (dialog && dialog.open) dialog.close();
    document.body.classList.remove('modal-open');
    if (lastFocus && lastFocus.isConnected) lastFocus.focus({ preventScroll: true });
  }

  function initPage() {
    hydrateImages();
    filters = { category: 'all', search: '' };
    updateFilter();
    const selected = document.getElementById('client-solution');
    const requested = routeInfo().query.get('solution');
    if (selected && requested && [...selected.options].some(o => o.value === requested)) selected.value = requested;
    app.querySelectorAll('dialog').forEach(dialog => {
      dialog.addEventListener('close', () => document.body.classList.remove('modal-open'));
      dialog.addEventListener('click', event => {
        if (event.target !== dialog) return;
        const box = dialog.getBoundingClientRect();
        if (event.clientX < box.left || event.clientX > box.right || event.clientY < box.top || event.clientY > box.bottom) closeDialog(dialog);
      });
    });
    updateHeader();
  }

  function navigate(focus = true) {
    if (!data) return;
    const info = routeInfo();
    const route = Object.hasOwn(data.titles, info.route) ? info.route : '404';
    const template = document.getElementById(`page-${route}`);
    document.body.classList.remove('modal-open');
    app.replaceChildren(template.content.cloneNode(true));
    document.body.dataset.page = route;
    document.body.classList.toggle('home', route === 'index');
    document.title = `${data.titles[route]} — Вертикальная линия`;
    initPage();
    window.scrollTo(0, 0);
    if (focus) (app.querySelector('h1') || app.querySelector('main')).focus({ preventScroll: true });
  }

  function updateHeader() {
    const header = app.querySelector('.site-header');
    const hero = app.querySelector('.hero');
    if (header) header.classList.toggle('is-stuck', !!hero && window.scrollY > hero.offsetHeight - header.offsetHeight);
  }

  function updateFilter() {
    const scope = app.querySelector('[data-filter-scope]');
    if (!scope) return;
    const items = [...scope.querySelectorAll('[data-filter-item]')];
    let count = 0;
    const query = filters.search.trim().toLocaleLowerCase('ru');
    items.forEach(item => {
      const matchesCategory = filters.category === 'all' || item.dataset.category === filters.category;
      const matchesSearch = !query || item.dataset.search.toLocaleLowerCase('ru').includes(query);
      item.hidden = !(matchesCategory && matchesSearch);
      if (!item.hidden) count += 1;
    });
    scope.querySelectorAll('[data-filter]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.filter === filters.category)));
    scope.querySelector('[data-count]').textContent = `Показано: ${count} из ${items.length}`;
    scope.querySelector('[data-empty]').hidden = count !== 0;
  }

  function openPhoto(button) {
    const assetId = button.dataset.lightbox;
    const source = button.querySelector('img');
    const dialog = document.getElementById('photo-dialog');
    const photo = document.getElementById('enlarged-photo');
    photo.src = data ? data.assets[assetId].src : source.src;
    photo.alt = source.alt;
    document.getElementById('photo-caption').textContent = source.alt;
    lastFocus = button;
    document.body.classList.add('modal-open');
    dialog.showModal();
  }

  function prepareEnquiry(form) {
    const contact = form.elements.contact;
    const value = contact.value.trim();
    const error = document.getElementById('contact-error');
    const digits = value.replace(/\D/g, '');
    const isEmail = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
    const isPhone = /^[+\d\s()\-]+$/.test(value) && digits.length >= 10 && digits.length <= 15;
    const preview = document.getElementById('mail-preview');
    if (!isEmail && !isPhone) {
      error.textContent = value ? 'Укажите email в формате name@example.ru или телефон — от 10 до 15 цифр.' : 'Оставьте телефон или email, чтобы мы могли ответить.';
      error.hidden = false;
      contact.setAttribute('aria-invalid', 'true');
      preview.hidden = true;
      contact.focus();
      return;
    }
    error.hidden = true;
    contact.removeAttribute('aria-invalid');
    const solution = form.elements.solution;
    const lines = [
      'Здравствуйте! Хочу обсудить потолок и освещение.',
      '',
      `Имя: ${form.elements.name.value.trim() || 'не указано'}`,
      `Контакт: ${value}`,
      `Город: ${form.elements.city.value}`,
      `Решение: ${solution.options[solution.selectedIndex].text}`,
      '',
      form.elements.message.value.trim() || 'Подробности готов(а) обсудить при обращении.'
    ];
    const body = lines.join('\n');
    document.getElementById('mail-body').textContent = body;
    document.getElementById('mail-link').href = `mailto:potolok63@yandex.ru?subject=${encodeURIComponent('Обсуждение потолка и освещения')}&body=${encodeURIComponent(body)}`;
    preview.hidden = false;
    preview.querySelector('h3').focus({ preventScroll: true });
    preview.scrollIntoView({ block: 'nearest' });
  }

  document.addEventListener('click', event => {
    const target = event.target.closest('button, a');
    if (!target || !app.contains(target)) return;
    if (target.hasAttribute('data-open-menu')) {
      lastFocus = target;
      document.body.classList.add('modal-open');
      document.getElementById('mobile-menu').showModal();
      return;
    }
    if (target.hasAttribute('data-close-dialog')) {
      closeDialog(target.closest('dialog'));
      return;
    }
    if (target.hasAttribute('data-lightbox')) {
      openPhoto(target);
      return;
    }
    if (target.hasAttribute('data-filter')) {
      filters.category = target.dataset.filter;
      updateFilter();
      return;
    }
    if (target.hasAttribute('data-reset-filter')) {
      filters = { category: 'all', search: '' };
      app.querySelector('input[data-search]').value = '';
      updateFilter();
      app.querySelector('input[data-search]').focus();
      return;
    }
    if (target.tagName !== 'A' || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    const url = target.getAttribute('href') || '';
    // In-page article links preserve the portable document's page route.
    if (url.startsWith('#') && !url.startsWith('#/')) {
      const anchor = app.querySelector(`#${CSS.escape(url.slice(1))}`);
      if (anchor) {
        event.preventDefault();
        anchor.scrollIntoView({ block: 'start' });
        if (anchor.id === 'main') anchor.focus({ preventScroll: true });
      }
    }
    if (data && url.startsWith('#/')) {
      const dialog = target.closest('dialog');
      if (dialog) closeDialog(dialog);
      if (url === location.hash) {
        event.preventDefault();
        navigate();
      }
    }
  });

  document.addEventListener('input', event => {
    if (event.target.matches('input[data-search]')) {
      filters.search = event.target.value;
      updateFilter();
    }
    if (event.target.id === 'client-contact' && event.target.hasAttribute('aria-invalid')) {
      event.target.removeAttribute('aria-invalid');
      document.getElementById('contact-error').hidden = true;
    }
    if (event.target.closest('#contact-form') && !event.target.closest('#mail-preview')) {
      document.getElementById('mail-preview').hidden = true;
    }
  });
  document.addEventListener('change', event => {
    if (event.target.closest('#contact-form')) document.getElementById('mail-preview').hidden = true;
  });
  document.addEventListener('submit', event => {
    if (event.target.id !== 'contact-form') return;
    event.preventDefault();
    prepareEnquiry(event.target);
  });
  window.addEventListener('hashchange', () => {
    if (data) navigate();
  });
  window.addEventListener('scroll', () => {
    if (!scrollPending) {
      scrollPending = true;
      requestAnimationFrame(() => { updateHeader(); scrollPending = false; });
    }
  }, { passive: true });
  if (data) navigate(false);
  else initPage();
})();
