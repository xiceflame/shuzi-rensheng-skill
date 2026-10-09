#!/usr/bin/env node
/** MCP transport delegates ALL retrieval to vaultq.py, including privacy gates. */
import { execFile, execFileSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const sdk = process.env.MCP_SDK_DIR || path.join(
  execFileSync("npm", ["root", "-g"], { encoding: "utf8", timeout: 10000 }).trim(),
  "@miguelarios/qkb/node_modules/@modelcontextprotocol/sdk/dist/esm"
);
const { Server } = await import(pathToFileURL(path.join(sdk, "server/index.js")).href);
const { StdioServerTransport } = await import(pathToFileURL(path.join(sdk, "server/stdio.js")).href);
const { ListToolsRequestSchema, CallToolRequestSchema } = await import(pathToFileURL(path.join(sdk, "types.js")).href);

function search(query, k, candidates) {
  if (typeof query !== "string" || !query.trim() || query.length > 8000 ||
      !Number.isInteger(k) || !Number.isInteger(candidates) || k < 1 || candidates < k || candidates > 200) {
    throw new Error("Expected nonempty query and 1 <= k <= candidates <= 200");
  }
  return new Promise((resolve, reject) => {
    execFile(process.env.SHUZI_PYTHON || "python3",
      [path.join(here, "vaultq.py"), "-k", String(k), "-n", String(candidates), "--", query],
      { timeout: 130000, maxBuffer: 1024 * 1024 },
      (error, stdout) => error ? reject(new Error("Retrieval failed; check local service health")) : resolve(stdout.trim()));
  });
}

const server = new Server({ name: "vault-search-rerank", version: "0.2.0" }, { capabilities: { tools: {} } });
server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [{
    name: "vault_search",
    description: "检索授权范围内的知识库；排除 private、隐藏路径与符号链接。空结果不等于资料不存在。",
    inputSchema: {
      type: "object",
      properties: {
        query: { type: "string", minLength: 1, maxLength: 8000 },
        k: { type: "integer", minimum: 1, maximum: 200 },
        candidates: { type: "integer", minimum: 1, maximum: 200 },
      },
      required: ["query"], additionalProperties: false,
    },
  }],
}));
server.setRequestHandler(CallToolRequestSchema, async (req) => {
  try {
    if (req.params.name !== "vault_search") throw new Error("Unknown tool");
    const { query, k = 5, candidates = 30 } = req.params.arguments ?? {};
    return { content: [{ type: "text", text: await search(query, k, candidates) }] };
  } catch (error) {
    return { content: [{ type: "text", text: String(error.message) }], isError: true };
  }
});
await server.connect(new StdioServerTransport());
