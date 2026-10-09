#!/usr/bin/env node
/**
 * vault-search-rerank — MCP 版「数字人生」检索：qkb 召回 + 4090 reranker 重排。
 *
 * 与 `qkb mcp`（纯检索）并列，供 OpenClaw agents / Claude Code 调用。
 * 复用随 qkb 一起安装的 @modelcontextprotocol/sdk（绝对路径 import，免依赖安装）。
 *
 * 工具：vault_search({ query, k?, candidates? }) → 文本结果（Top-k）。
 * reranker 不可用时自动回退 qkb 排序。
 */
import { spawn } from "node:child_process";

const SDK = "/opt/homebrew/lib/node_modules/@miguelarios/qkb/node_modules/@modelcontextprotocol/sdk/dist/esm";
const { Server } = await import(`${SDK}/server/index.js`);
const { StdioServerTransport } = await import(`${SDK}/server/stdio.js`);
const { ListToolsRequestSchema, CallToolRequestSchema } = await import(`${SDK}/types.js`);

const QKB = process.env.QKB_BIN || "/opt/homebrew/bin/qkb";
const RERANK_URL = process.env.RERANK_URL || "http://127.0.0.1:8081/rerank";

function qkbQuery(query, n) {
  return new Promise((resolve) => {
    const p = spawn(QKB, ["query", query, "--limit", String(n), "--json"]);
    let out = "";
    p.stdout.on("data", (d) => (out += d));
    p.on("close", () => {
      const i = out.indexOf("[");
      if (i < 0) return resolve([]);
      try { resolve(JSON.parse(out.slice(i))); } catch { resolve([]); }
    });
  });
}

async function rerank(query, docs) {
  const r = await fetch(RERANK_URL, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ query, documents: docs }),
    signal: AbortSignal.timeout(60000),
  });
  if (!r.ok) throw new Error(`rerank HTTP ${r.status}`);
  return (await r.json()).results;
}

async function search(query, k, candidates) {
  const cands = await qkbQuery(query, candidates);
  if (!cands.length) return "（无结果）";
  let ranked = cands.map((c) => ({ score: c.score ?? 0, c, reranked: false }));
  try {
    const rs = await rerank(query, cands.map((c) => c.matched_text || c.title || ""));
    ranked = rs.sort((a, b) => b.relevance_score - a.relevance_score)
               .map((r) => ({ score: r.relevance_score, c: cands[r.index], reranked: true }));
  } catch { /* 回退 qkb 排序 */ }
  return ranked.slice(0, k).map((r, i) =>
    `${i + 1}. [${r.reranked ? r.score.toFixed(3) : "qkb " + r.score}] ${r.c.title} — ${r.c.file_path}`
  ).join("\n");
}

const server = new Server(
  { name: "vault-search-rerank", version: "0.1.0" },
  { capabilities: { tools: {} } }
);

server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [{
    name: "vault_search",
    description: "检索「数字人生」知识库（qkb 混合召回 + 4090 bge-reranker 重排）。适合关系型/概念型问题，如『张三和我的关系』。",
    inputSchema: {
      type: "object",
      properties: {
        query: { type: "string", description: "检索问题（自然语言或关键词）" },
        k: { type: "integer", description: "返回条数，默认 5" },
        candidates: { type: "integer", description: "初筛候选数，默认 30" },
      },
      required: ["query"],
    },
  }],
}));

server.setRequestHandler(CallToolRequestSchema, async (req) => {
  const { query, k = 5, candidates = 30 } = req.params.arguments ?? {};
  try {
    const text = await search(String(query), Number(k), Number(candidates));
    return { content: [{ type: "text", text }] };
  } catch (e) {
    return { content: [{ type: "text", text: `检索失败：${e}` }], isError: true };
  }
});

await server.connect(new StdioServerTransport());
