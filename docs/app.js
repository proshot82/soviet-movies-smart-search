// Страница поиска: интерфейс, ключ OpenAI, обращения к API. Сам поиск по каталогу — в worker.js (engine.js).
import { EMBEDDING_MODEL, RERANK_MODEL, TOP_RESULTS, fusionWeights, fallbackOrder, rerankPrompt, parseRerank } from './engine.js';

const KEY_STORAGE = 'gff-openai-key';
const TOP_NO_KEY = 10;          // без реранкера пометок нет — показываем список подлиннее
let dims = 1024;

const $ = id => document.getElementById(id);
const q = $('q');

// ─── Ключ ────────────────────────────────────────────────────────────
let memKey = '';   // если хранилище браузера недоступно (приватный режим) — ключ живёт до закрытия вкладки
function getKey() { try { return localStorage.getItem(KEY_STORAGE) || memKey; } catch { return memKey; } }
function setKey(k) {
  memKey = k;
  try { k ? localStorage.setItem(KEY_STORAGE, k) : localStorage.removeItem(KEY_STORAGE); } catch { /* приватный режим */ }
}
// Ключ из закладки «…/#key=sk-…»: запоминается в этом браузере и сразу убирается из адреса (и из истории).
// Часть адреса после # браузер на сервер не отправляет — ключ уходит только в api.openai.com.
(function keyFromHash() {
  const m = location.hash.match(/(?:^#|&)key=([^&]+)/);
  if (!m) return;
  setKey(decodeURIComponent(m[1]).trim());
  history.replaceState(null, '', location.pathname + location.search);
})();
function renderKey() {
  const k = getKey();
  $('key-unset').hidden = !!k;
  $('key-set').hidden = !k;
  $('key-mask').textContent = k ? '…' + k.slice(-4) : '';
}
// Проверка ключа перед сохранением. На неверный ключ OpenAI отвечает 401 без CORS-заголовков,
// поэтому браузер видит не 401, а сетевую ошибку — отличить «ключ не тот» от «нет связи» нельзя.
$('key-save').addEventListener('click', async () => {
  const k = $('key-input').value.trim();
  const msg = $('key-msg');
  if (!k) { $('key-input').focus(); return; }
  $('key-save').disabled = true;
  msg.textContent = 'Проверяю ключ…';
  try {
    const r = await fetch('https://api.openai.com/v1/models/' + EMBEDDING_MODEL, { headers: { 'Authorization': 'Bearer ' + k } });
    if (!r.ok) throw new Error((r.status + ' ' + r.statusText).trim());
    setKey(k); $('key-input').value = ''; msg.textContent = ''; renderKey();
  } catch (e) {
    msg.textContent = 'OpenAI не принял ключ или не отвечает (' + e.message + '). Проверь ключ и подключение.';
  } finally {
    $('key-save').disabled = false;
  }
});
$('key-input').addEventListener('keydown', e => { if (e.key === 'Enter') $('key-save').click(); });
$('key-change').addEventListener('click', () => { $('key-unset').hidden = false; $('key-set').hidden = true; $('key-input').focus(); });
$('key-forget').addEventListener('click', () => { setKey(''); renderKey(); });
renderKey();

// ─── Воркер с каталогом ──────────────────────────────────────────────
const worker = new Worker('worker.js', { type: 'module' });
const pending = new Map();
let seq = 0, loadError = null, readyResolve;
const ready = new Promise(r => { readyResolve = r; });

worker.onmessage = ({ data }) => {
  if (data.type === 'progress') {
    $('status').className = 'status';
    $('status').textContent = `Загружаю каталог… ${(data.loaded / 1e6).toFixed(1)} из ${(data.total / 1e6).toFixed(0)} МБ`;
  } else if (data.type === 'ready') {
    const m = data.manifest;
    dims = m.dims;
    $('statsText').textContent = `${m.films} фильмов ${m.year_min}–${m.year_max} годов`;
    $('yearsText').textContent = `${m.year_min}–${m.year_max}`;
    $('rerankModel').textContent = m.rerank_model || RERANK_MODEL;
    if ($('status').textContent.startsWith('Загружаю')) $('status').textContent = '';
    readyResolve();
  } else if (data.type === 'error') {
    loadError = data.message;
    readyResolve();
  } else if (pending.has(data.id)) {
    const { resolve, reject } = pending.get(data.id);
    pending.delete(data.id);
    data.error ? reject(new Error(data.error)) : resolve(data.result);
  }
};
function call(msg) {
  return new Promise((resolve, reject) => {
    const id = ++seq;
    pending.set(id, { resolve, reject });
    worker.postMessage({ ...msg, id });
  });
}

// ─── OpenAI ──────────────────────────────────────────────────────────
class ApiError extends Error {
  constructor(message, status) { super(message); this.status = status; }
}
const sleep = ms => new Promise(r => setTimeout(r, ms));

// 3 попытки, как в film_search.py; ошибки, которые повтором не лечатся (ключ, модель, запрос), — сразу
async function openai(path, body, key) {
  let last;
  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      const r = await fetch('https://api.openai.com/v1/' + path, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + key },
        body: JSON.stringify(body),
      });
      if (r.ok) return await r.json();
      let msg = r.status + ' ' + r.statusText;
      try { msg = (await r.json()).error?.message || msg; } catch { /* не JSON */ }
      last = new ApiError(msg, r.status);
      if (r.status !== 429 && r.status < 500) throw last;
    } catch (e) {
      if (e instanceof ApiError && e.status !== 429 && e.status < 500) throw e;
      last = e;
    }
    if (attempt < 2) await sleep(1000);
  }
  throw last;
}

async function embedQuery(query, key) {
  const data = await openai('embeddings', { model: EMBEDDING_MODEL, input: [query], dimensions: dims }, key);
  return Float32Array.from(data.data[0].embedding);
}

async function rerank(query, candidates, key) {
  const data = await openai('chat/completions', {
    model: RERANK_MODEL,
    messages: [{ role: 'user', content: rerankPrompt(query, candidates, TOP_RESULTS) }],
    reasoning_effort: 'none',
    max_completion_tokens: 1000,
  }, key);
  return parseRerank(data.choices[0].message.content || '', candidates, TOP_RESULTS);
}

const keyProblem = e => e instanceof ApiError && (e.status === 401 || e.status === 403);

// ─── Поиск ───────────────────────────────────────────────────────────
function setQ(t) { q.value = t; doSearch(); }
q.addEventListener('keydown', e => { if (e.key === 'Enter') doSearch(); });
$('btn').addEventListener('click', () => doSearch());
document.querySelectorAll('.ex[data-q]').forEach(el => el.addEventListener('click', () => setQ(el.dataset.q)));

let ticker = null;
function setBusy(on, withAi) {
  const btn = $('btn');
  btn.disabled = on;
  btn.textContent = on ? 'Ищу…' : 'Найти';
  $('progress').classList.toggle('on', on);
  $('stages').classList.toggle('on', on);
  if (on) $('stages').innerHTML = withAi
    ? '<b>Идёт поиск</b> · отбор по словам и смыслу → перечитывание кандидатов · обычно 2–5 с'
    : '<b>Идёт поиск</b> · отбор по словам';
}
function ensureVisible(el) {
  const r = el.getBoundingClientRect();
  if (r.top < 0 || r.top > window.innerHeight - 60) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
}

async function doSearch() {
  const query = q.value.trim();
  if (!query) { q.focus(); return; }
  if ($('btn').disabled) return;
  const statusEl = $('status'), noticeEl = $('notice'), resultsEl = $('results');
  const key = getKey();
  resultsEl.innerHTML = '';
  noticeEl.hidden = true; noticeEl.textContent = '';
  statusEl.className = 'status busy';
  setBusy(true, !!key);
  ensureVisible(statusEl);

  const filters = {
    year: parseInt($('f-year').value) || null,
    studio: $('f-studio').value.trim() || null,
    genre: $('f-genre').value.trim() || null,
    kind: $('f-kind').value || null,
  };

  try {
    await ready;
    if (loadError) throw new Error('каталог не загрузился: ' + loadError);

    const t0 = performance.now();
    statusEl.textContent = 'Ищу… 0.0 с';
    if (ticker) clearInterval(ticker);
    ticker = setInterval(() => { statusEl.textContent = 'Ищу… ' + ((performance.now() - t0) / 1000).toFixed(1) + ' с'; }, 100);

    const degraded = [];
    let keyError = null;    // OpenAI ответил «ключ не принят» (401/403 с CORS-заголовками — редкость)
    let noAnswer = false;   // ответа нет вовсе: нет связи или неверный ключ (401 приходит без CORS-заголовков)
    let qvec = null;
    if (key) {
      try { qvec = await embedQuery(query, key); } catch (e) {
        degraded.push('semantic');
        if (keyProblem(e)) keyError = e;
        else if (!(e instanceof ApiError)) noAnswer = true;
        console.warn('эмбеддинг запроса:', e);
      }
    }
    const doRerank = !!key && !keyError && !noAnswer;
    const candidates = await call({ type: 'hybrid', query, qvec, filters, weights: fusionWeights(doRerank) });

    let results;
    if (doRerank && candidates.length) {
      try { results = await rerank(query, candidates, key); } catch (e) {
        degraded.push('rerank');
        if (keyProblem(e)) keyError = e;
        console.warn('реранкер:', e);
        results = fallbackOrder(candidates).slice(0, TOP_RESULTS);
      }
    } else {
      results = fallbackOrder(candidates).slice(0, doRerank ? TOP_RESULTS : TOP_NO_KEY);
    }

    let notice = null;
    if (keyError) {
      notice = `OpenAI не принял ключ (${keyError.message}) — найдено только по совпадению слов. Проверь ключ: «заменить» под полем поиска.`;
    } else if (noAnswer) {
      notice = 'OpenAI не отвечает — нет связи, или ключ больше не действует (тогда «заменить» под полем поиска). Найдено только по совпадению слов.';
    } else if (!key) {
      notice = 'Поиск без ключа OpenAI — только по совпадению слов, без пометок уверенности. С ключом (поле под строкой поиска) ищется и по смыслу.';
    } else if (degraded.includes('rerank')) {
      notice = 'Сервис переоценки (ИИ) сейчас недоступен — показан список по совпадению слов'
        + (!degraded.includes('semantic') ? ' и смысла' : '') + ', без пометок уверенности. Повтори запрос через минуту.';
    } else if (degraded.includes('semantic')) {
      notice = 'Смысловой поиск сейчас недоступен — найдено только по совпадению слов.';
    }

    clearInterval(ticker); ticker = null;
    const elapsed = ((performance.now() - t0) / 1000).toFixed(1);
    setBusy(false);
    statusEl.className = 'status';
    const n = results.length;
    const word = n % 10 === 1 && n % 100 !== 11 ? 'результат' : (n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 10 || n % 100 >= 20) ? 'результата' : 'результатов');
    statusEl.textContent = `${n} ${word} · ${elapsed} с`;
    if (notice) { noticeEl.textContent = notice; noticeEl.hidden = false; }
    render(results);
    ensureVisible(statusEl);
  } catch (e) {
    clearInterval(ticker); ticker = null;
    setBusy(false);
    statusEl.className = 'status err';
    statusEl.textContent = 'Ошибка: ' + e.message;
  }
}

function render(results) {
  const confBadge = c => {
    if (!c) return '';
    const cls = c === 'наиболее вероятно' ? 'conf-high' : c === 'маловероятно' ? 'conf-low' : 'conf-mid';
    return '<span class="conf ' + cls + '">' + esc(c) + '</span>';
  };
  let html = '';
  results.forEach((r, i) => {
    const ann = r.annotation || '';
    const needCollapse = ann.length > 250;
    const meta = [r.genre, r.studio, r.director ? 'реж. ' + r.director : ''].filter(Boolean).join(' · ');
    html += '<div class="result">' +
      '<div class="result-header">' +
        '<div class="result-title"><span class="rank-badge">' + (i + 1) + '</span>' +
          esc(r.title || '?') + ' (' + esc(String(r.year ?? '?')) + ')' + confBadge(r.confidence) + '</div>' +
      '</div>' +
      (meta ? '<div class="result-meta">' + esc(meta) + '</div>' : '') +
      '<div class="result-ann' + (needCollapse ? ' collapsed' : '') + '" id="ann-' + i + '">' + esc(ann) + '</div>' +
      (needCollapse ? '<span class="toggle-ann" data-i="' + i + '">показать</span>' : '') +
      (r.source ? '<div class="result-src"><a href="' + esc(r.source).replace(/"/g, '&quot;') + '" target="_blank" rel="noopener">источник</a></div>' : '') +
    '</div>';
  });
  const el = $('results');
  el.innerHTML = html || '<div class="empty">Ничего не нашлось. Попробуй другую деталь сюжета, убери сомнительные подробности или сними фильтры.</div>';
  el.querySelectorAll('.toggle-ann').forEach(t => t.addEventListener('click', () => {
    const a = $('ann-' + t.dataset.i);
    a.classList.toggle('collapsed');
    t.textContent = a.classList.contains('collapsed') ? 'показать' : 'свернуть';
  }));
}

function esc(s) { const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }
