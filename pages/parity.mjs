// Запускается из pages/check_parity.py: читает задания из stdin (JSON), гоняет их через docs/engine.js
// на собранных данных docs/data и печатает ответы в stdout (JSON).
import { readFileSync } from 'node:fs';
import { gunzipSync } from 'node:zlib';
import { Engine, parseLemmas, parseVectors } from '../docs/engine.js';

const dataDir = new URL('../docs/data/', import.meta.url);
const manifest = JSON.parse(readFileSync(new URL('manifest.json', dataDir), 'utf8'));
const read = key => gunzipSync(readFileSync(new URL(manifest.files[key].file, dataDir)));

const vbuf = read('vectors');
const engine = new Engine({
  films: JSON.parse(read('films').toString('utf8')),
  fts: JSON.parse(read('fts').toString('utf8')),
  lemmas: parseLemmas(read('lemmas').toString('utf8')),
  vectors: parseVectors(vbuf.buffer.slice(vbuf.byteOffset, vbuf.byteOffset + vbuf.byteLength), manifest.chunks, manifest.dims),
});

const tasks = JSON.parse(readFileSync(0, 'utf8'));
const id = d => engine.films[d][0];
const out = {
  lemmas: tasks.lemmas.map(t => engine.lemmatize(t).join(' ')),
  fts: tasks.fts.map(t => engine.ftsSearch(t.query, t.limit, t.filters || {}).map(id)),
  sem: tasks.sem.map(t => engine.semanticSearch([Float32Array.from(t.vec)], t.limit, t.filters || {})
    .map(([d, s]) => [id(d), s])),
  hybrid: tasks.hybrid.map(t => engine.hybrid(t.query, t.vec ? [Float32Array.from(t.vec)] : null,
    { limit: 50, filters: t.filters || {}, ftsWeight: t.w[0], semWeight: t.w[1] })
    .map(c => [c.film_id, c.fts_rank, c.sem_rank])),
};
process.stdout.write(JSON.stringify(out));
