// Ядро поиска для статической версии (GitHub Pages) — перенос логики film_search.py в браузер.
// Не зависит от DOM: тот же модуль работает в веб-воркере и в node (pages/parity.mjs сверяет его с Python).
//
// Каналы те же, что у сервера:
//   FTS       — bm25 по лемматизированному индексу, формула и статистика как у SQLite FTS5 (k1=1.2, b=0.75),
//               префиксный поиск «лемма*», сначала AND по всем словам, затем добор OR (fts_search)
//   семантика — максимум косинуса по чанкам фильма (semantic_search); векторы 1024D × 4 бита
//   слияние   — RRF k=60 с весами fusion_weights(), FTS-топ-20 всегда доходит до реранкера (hybrid_search)
//   реранкер  — тот же промпт и разбор ответа, что у rerank()

export const EMBEDDING_MODEL = 'text-embedding-3-large';
export const RERANK_MODEL = 'gpt-5.5';
export const TOP_RESULTS = 5;
export const RERANK_ANN_CHARS = 1500;
const FTS_WEIGHT_RERANK = 0.3;
const FTS_WEIGHT_NORERANK = 0.8;
const RRF_K = 60;
const BM25_K1 = 1.2;
const BM25_B = 0.75;

const RU_STOP = new Set((
  'а без будто бы быть в ваш весь вот всё вы да даже для до если есть ещё её ' +
  'же и из или к как когда который кто ли либо лишь между мы на над наш не ' +
  'неужели ни но о он она они оно от по под потому при про разве с сам свой ' +
  'себя стать также такой тоже только тот ты у уже хотя чей через что чтобы ' +
  'это этот я').split(' '));
const FTS_KEYWORDS = new Set(['AND', 'OR', 'NOT', 'NEAR']);
const NON_WORD = /[^\p{L}\p{N}]+/u;   // Python: re.sub(r'[_\W]+', ' ', …)

export function fusionWeights(doRerank) {
  const w = doRerank ? FTS_WEIGHT_RERANK : FTS_WEIGHT_NORERANK;
  return [w, 1 - w];
}

// ─── Разбор файлов данных (форматы — pages/build_site.py) ───────────────────

export function parseLemmas(text) {
  const map = new Map();
  for (const line of text.split('\n')) {
    if (!line) continue;
    const parts = line.split('\t');
    const lemma = parts[0];
    for (let i = 1; i < parts.length; i++) map.set(parts[i], lemma);
  }
  return map;
}

export function parseVectors(buf, nChunks, dims) {
  // buf: ArrayBuffer = scales float32[n] + film uint16[n] + int4 packed[n*dims/2]
  const scales = new Float32Array(buf, 0, nChunks);
  const filmOf = new Uint16Array(buf, nChunks * 4, nChunks);
  const packed = new Uint8Array(buf, nChunks * 6, nChunks * dims / 2);
  const vals = new Int8Array(nChunks * dims);
  for (let i = 0, j = 0; i < packed.length; i++, j += 2) {
    const b = packed[i];
    const lo = b & 15, hi = b >> 4;
    vals[j] = lo >= 8 ? lo - 16 : lo;
    vals[j + 1] = hi >= 8 ? hi - 16 : hi;
  }
  return { scales, filmOf, vals, dims, n: nChunks };
}

// ─── Движок ────────────────────────────────────────────────────────────────

export class Engine {
  constructor({ films, fts, lemmas, vectors }) {
    // films: [[film_id, title, genre, year, studio, director, annotation], …] по возрастанию film_id
    this.films = films;
    this.nDocs = films.length;
    this.lemmas = lemmas;
    this.terms = fts.terms;
    this.offsets = Uint32Array.from(fts.offsets);
    this.postDocs = Uint16Array.from(fts.docs);
    this.postTfs = Uint16Array.from(fts.tfs);
    this.docLen = Float64Array.from(fts.doclen);
    let total = 0;
    for (const l of fts.doclen) total += l;
    this.avgDl = total / this.nDocs;
    this.vectors = vectors || null;
    this.studioLc = films.map(f => f[4].toLowerCase());
    this.genreLc = films.map(f => f[2].toLowerCase());
  }

  film(idx) {
    const f = this.films[idx];
    return { idx, film_id: f[0], title: f[1], genre: f[2], year: f[3], studio: f[4], director: f[5], annotation: f[6] };
  }

  // Фильтры как в fts_search/semantic_search: десятилетие, подстрока студии и жанра (без учёта регистра)
  makeFilter({ year, studio, genre } = {}) {
    if (!year && !studio && !genre) return null;
    const decade = year ? Math.floor(year / 10) * 10 : 0;
    const s = studio ? studio.toLowerCase() : null;
    const g = genre ? genre.toLowerCase() : null;
    return idx => {
      if (year) {
        const y = this.films[idx][3];
        if (y == null || y < decade || y > decade + 9) return false;
      }
      if (s && !this.studioLc[idx].includes(s)) return false;
      if (g && !this.genreLc[idx].includes(g)) return false;
      return true;
    };
  }

  // lemmatize_text(): нижний регистр, слова, начальная форма (словарь собран тем же pymorphy3)
  lemmatize(text) {
    return text.toLowerCase().split(NON_WORD).filter(Boolean).map(w => this.lemmas.get(w) || w);
  }

  queryTokens(query) {
    return this.lemmatize(query).filter(t => t.length >= 2 && !RU_STOP.has(t) && !FTS_KEYWORDS.has(t.toUpperCase()));
  }

  // Диапазон термов с префиксом p в отсортированном словаре
  _prefixRange(p) {
    const terms = this.terms;
    let lo = 0, hi = terms.length;
    while (lo < hi) { const m = (lo + hi) >> 1; if (terms[m] < p) lo = m + 1; else hi = m; }
    let end = lo;
    while (end < terms.length && terms[end].startsWith(p)) end++;
    return [lo, end];
  }

  // Частоты «фразы» t* по документам и число документов с ней (как считает FTS5 для префиксного запроса)
  _phrase(token) {
    const tf = new Float64Array(this.nDocs);
    const [a, b] = this._prefixRange(token);
    let nHit = 0;
    for (let t = a; t < b; t++) {
      for (let k = this.offsets[t]; k < this.offsets[t + 1]; k++) {
        const d = this.postDocs[k];
        if (tf[d] === 0) nHit++;
        tf[d] += this.postTfs[k];
      }
    }
    let idf = Math.log((this.nDocs - nHit + 0.5) / (nHit + 0.5));
    if (idf <= 0) idf = 1e-6;
    return { tf, idf };
  }

  // Документы, подходящие под AND (все фразы) или OR (любая), по убыванию bm25; ничьи — по film_id
  _bm25(phrases, mode, limit, filter) {
    const out = [];
    for (let d = 0; d < this.nDocs; d++) {
      let hits = 0, score = 0;
      const norm = BM25_K1 * (1 - BM25_B + BM25_B * this.docLen[d] / this.avgDl);
      for (const p of phrases) {
        const f = p.tf[d];
        if (f > 0) { hits++; score += p.idf * (f * (BM25_K1 + 1)) / (f + norm); }
      }
      if (mode === 'and' ? hits < phrases.length : hits === 0) continue;
      if (filter && !filter(d)) continue;
      out.push([d, score]);
    }
    out.sort((x, y) => y[1] - x[1] || x[0] - y[0]);
    return out.slice(0, limit);
  }

  ftsSearch(query, limit = 20, filters = {}) {
    const tokens = this.queryTokens(query);
    if (!tokens.length) return [];
    const filter = this.makeFilter(filters);
    const phrases = tokens.map(t => this._phrase(t));
    let results = [];
    if (tokens.length >= 2) {
      results = this._bm25(phrases, 'and', limit, filter).map(([d]) => d);
      if (results.length >= limit) return results;
    }
    const seen = new Set(results);
    for (const [d] of this._bm25(phrases, 'or', limit * 2, filter)) {
      if (!seen.has(d)) {
        results.push(d); seen.add(d);
        if (results.length >= limit) break;
      }
    }
    return results;
  }

  // qvecs: массив Float32Array длины dims (вектор запроса и, при расширении, его вариантов)
  semanticSearch(qvecs, limit = 20, filters = {}) {
    const V = this.vectors;
    if (!V) return [];
    const { vals, scales, filmOf, dims, n } = V;
    const best = new Float64Array(this.nDocs).fill(-Infinity);
    for (const q0 of qvecs) {
      let norm = 0;
      for (let j = 0; j < dims; j++) norm += q0[j] * q0[j];
      norm = Math.sqrt(norm);
      if (norm === 0) continue;
      const q = new Float32Array(dims);
      for (let j = 0; j < dims; j++) q[j] = q0[j] / norm;
      for (let c = 0, off = 0; c < n; c++, off += dims) {
        let s = 0;
        for (let j = 0; j < dims; j++) s += q[j] * vals[off + j];
        s *= scales[c];
        const f = filmOf[c];
        if (s > best[f]) best[f] = s;
      }
    }
    const filter = this.makeFilter(filters);
    const scored = [];
    for (let d = 0; d < this.nDocs; d++) {
      if (best[d] > 0 && (!filter || filter(d))) scored.push([d, best[d]]);
    }
    scored.sort((x, y) => y[1] - x[1] || x[0] - y[0]);
    return scored.slice(0, limit);
  }

  // hybrid_search(): кандидаты для реранкера с местами в каналах (fts_rank / sem_rank)
  hybrid(query, qvecs, { limit = 50, filters = {}, ftsWeight = 0.3, semWeight = 0.7 } = {}) {
    const fts = this.ftsSearch(query, limit * 3, filters);
    const sem = qvecs ? this.semanticSearch(qvecs, limit, filters) : [];
    const rrf = new Map(), ftsRank = new Map(), semRank = new Map(), semScore = new Map();
    fts.forEach((d, r) => { rrf.set(d, (rrf.get(d) || 0) + ftsWeight / (RRF_K + r + 1)); ftsRank.set(d, r + 1); });
    sem.forEach(([d, s], r) => {
      rrf.set(d, (rrf.get(d) || 0) + semWeight / (RRF_K + r + 1)); semRank.set(d, r + 1); semScore.set(d, s);
    });
    const ranked = [...rrf.entries()].sort((a, b) => b[1] - a[1]).slice(0, limit);
    const inRanked = new Set(ranked.map(([d]) => d));
    for (const d of fts.slice(0, 20)) {
      if (!inRanked.has(d)) { ranked.push([d, rrf.get(d) || 0]); inRanked.add(d); }
    }
    return ranked.map(([d, score]) => ({
      ...this.film(d),
      rrf_score: score,
      fts_rank: ftsRank.get(d) ?? null,
      sem_rank: semRank.get(d) ?? null,
      sem_score: semScore.get(d) ?? null,
    }));
  }
}

// fallback_order(): порядок без реранкера — слияние пересчитывается весом FTS_WEIGHT_NORERANK
export function fallbackOrder(candidates) {
  const [wF, wS] = fusionWeights(false);
  const score = c => {
    const fr = c.fts_rank, sr = c.sem_rank;
    if (!fr && !sr) return c.rrf_score || 0;
    return (fr ? wF / (RRF_K + fr) : 0) + (sr ? wS / (RRF_K + sr) : 0);
  };
  return candidates.map((c, i) => [c, score(c), i]).sort((a, b) => b[1] - a[1] || a[2] - b[2]).map(x => x[0]);
}

// ─── Реранкер ──────────────────────────────────────────────────────────────

export function clipAnnotation(text, limit = RERANK_ANN_CHARS) {
  text = (text || '').trim();
  if (text.length <= limit) return text;
  let cut = text.lastIndexOf('. ', limit - 2);
  if (cut < Math.floor(limit / 2)) cut = text.lastIndexOf(' ', limit - 1);
  if (cut <= 0) return text.slice(0, limit) + '…';
  return text.slice(0, cut + 1).trimEnd() + ' …';
}

export function rerankPrompt(query, candidates, topK = TOP_RESULTS) {
  const lines = candidates.map((c, i) => `[${i}] «${c.title || '?'}» (${c.year ?? '?'}): ${clipAnnotation(c.annotation)}`);
  return `Пользователь ищет фильм по описанию: "${query}"

Внимательно прочитай аннотации всех ${lines.length} фильмов-кандидатов. Определи, какие из них по СЮЖЕТУ соответствуют запросу. Обращай внимание на:
- Кто совершает действие (субъект), кто объект
- Конкретные сюжетные события, а не просто тематическое сходство
- Воспоминания неточны: роли могут быть перепутаны, связи упрощены, одна деталь (вид спорта, причина события, родство) может быть названа неверно — фильм, совпадающий по остальным событиям, включай в список
- Суди только по тексту аннотации: известность фильма — не довод. Если запрос называет литературный источник (автора, пьесу, роман), подходят и фильмы, у которых аннотация состоит из одной ссылки на этот источник

Верни до ${topK} самых подходящих фильмов по убыванию релевантности. Каждому проставь уверенность совпадения с запросом — одно из: "наиболее вероятно", "возможно", "маловероятно".
Слабые и сомнительные совпадения НЕ отбрасывай — включай их с пометкой "маловероятно". Пустой массив [] возвращай только если ни один фильм не подходит даже отдалённо.
Формат — JSON-массив объектов по убыванию релевантности, без пояснений: [{"i": 0, "p": "наиболее вероятно"}, {"i": 5, "p": "возможно"}]

ФИЛЬМЫ:

` + lines.join('\n');
}

const CONFIDENCE = new Set(['наиболее вероятно', 'возможно', 'маловероятно']);

// Разбор ответа реранкера. Ответ не в виде JSON-массива — ошибка (бросаем), чтобы сработал запасной порядок,
// а не «ничего не нашлось».
export function parseRerank(text, candidates, topK = TOP_RESULTS) {
  const items = JSON.parse(text.trim().replaceAll('```json', '').replaceAll('```', '').trim());
  if (!Array.isArray(items)) throw new Error('реранкер вернул не массив');
  const out = [], seen = new Set();
  for (const it of items) {
    let idx, conf;
    if (it && typeof it === 'object') {
      idx = it.i ?? it.index;
      conf = String(it.p || it.conf || '').trim().toLowerCase();
    } else {
      idx = it; conf = '';
    }
    if (!CONFIDENCE.has(conf)) conf = 'возможно';
    idx = Number.parseInt(idx, 10);
    if (!Number.isInteger(idx)) continue;
    if (idx >= 0 && idx < candidates.length && !seen.has(idx)) {
      seen.add(idx);
      out.push({ ...candidates[idx], confidence: conf });
    }
    if (out.length >= topK) break;
  }
  return out;
}
