// Веб-воркер: загружает данные каталога и выполняет поиск, чтобы страница не подвисала.
// Сообщения: из страницы {id, type: 'hybrid', query, qvec, filters, weights};
// в страницу {type: 'progress', loaded, total}, {type: 'ready', manifest}, {type: 'error', message}, {id, result}.
import { Engine, parseLemmas, parseVectors } from './engine.js';

let engine = null;
const ready = load().catch(e => { postMessage({ type: 'error', message: String(e && e.message || e) }); throw e; });

async function load() {
  const resp = await fetch('data/manifest.json', { cache: 'no-cache' });
  if (!resp.ok) throw new Error('нет data/manifest.json (' + resp.status + ')');
  const manifest = await resp.json();
  const files = manifest.files;
  const total = Object.values(files).reduce((s, f) => s + f.bytes, 0);
  let loaded = 0;
  const tick = n => { loaded += n; postMessage({ type: 'progress', loaded, total }); };

  const fetchGz = async key => {
    const r = await fetch('data/' + files[key].file);
    if (!r.ok) throw new Error('не загрузился ' + files[key].file + ' (' + r.status + ')');
    const counted = r.body.pipeThrough(new TransformStream({
      transform(chunk, ctl) { tick(chunk.byteLength); ctl.enqueue(chunk); },
    }));
    return new Response(counted.pipeThrough(new DecompressionStream('gzip')));
  };

  const [films, fts, lemmas, vbuf] = await Promise.all([
    fetchGz('films').then(r => r.json()),
    fetchGz('fts').then(r => r.json()),
    fetchGz('lemmas').then(r => r.text()),
    fetchGz('vectors').then(r => r.arrayBuffer()),
  ]);
  engine = new Engine({
    films, fts,
    lemmas: parseLemmas(lemmas),
    vectors: parseVectors(vbuf, manifest.chunks, manifest.dims),
  });
  postMessage({ type: 'ready', manifest });
}

onmessage = async ({ data }) => {
  const { id, type } = data;
  try {
    await ready;
    if (type === 'hybrid') {
      const result = engine.hybrid(data.query, data.qvec ? [data.qvec] : null, {
        limit: 50, filters: data.filters, ftsWeight: data.weights[0], semWeight: data.weights[1],
      });
      postMessage({ id, result });
    }
  } catch (e) {
    postMessage({ id, error: String(e && e.message || e) });
  }
};
