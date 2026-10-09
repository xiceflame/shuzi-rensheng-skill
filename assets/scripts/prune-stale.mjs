import { loadConfig } from '/opt/homebrew/lib/node_modules/@miguelarios/qkb/dist/config.js';
import { connect } from '/opt/homebrew/lib/node_modules/@miguelarios/qkb/dist/db/schema.js';
import { Storage } from '/opt/homebrew/lib/node_modules/@miguelarios/qkb/dist/db/storage.js';
import { existsSync } from 'node:fs';
import { join } from 'node:path';

const cfg = loadConfig();
const conn = connect(cfg.dbPath, cfg.embeddingDim);
const storage = new Storage(conn, cfg.vaultName);

const rows = conn.prepare('SELECT id, file_path FROM documents').all();
let pruned = 0;
const sample = [];
for (const r of rows) {
  if (!existsSync(join(cfg.vaultPath, r.file_path))) {
    storage.delete(r.id);
    pruned++;
    if (sample.length < 8) sample.push(r.file_path);
  }
}
console.log('vault:', cfg.vaultPath);
console.log('scanned docs:', rows.length);
console.log('pruned (file missing):', pruned);
console.log('sample:', sample.join(' | '));
conn.close();
