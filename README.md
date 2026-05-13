# graph-query-mcp

Surgical queries against an Obsidian / vault knowledge graph. Loads a `graph.json` (NetworkX node-link format) once at startup and answers targeted questions without making Claude read a 50K-line graph report.

Designed to pair with [`graphify`](https://github.com/adelaidasofia/ai-brain-starter) (the graph-building skill in ai-brain-starter), but the server accepts any graph in NetworkX node-link JSON. Supports up to two scopes (primary + secondary, e.g. personal + team).

## Why use this

If you've already run `graphify` on a vault, you've got a `graph.json` and a `GRAPH_REPORT.md`. Reading the full report into Claude burns thousands of tokens for every question. This MCP loads the graph once at startup, answers in <50ms, and never spills the whole graph into context.

## Tools

| Tool | What it does |
|---|---|
| `search_nodes(query, scope, limit)` | Fuzzy match against node names. Returns node IDs ranked by exact / starts-with / contains. |
| `get_neighbors(node_id, scope, max_hops, limit)` | Connected nodes within N hops, sorted by degree. |
| `find_path(source, target, scope)` | Shortest path between two concepts. Auto-fuzzy-matches both ends. |
| `get_top_nodes(scope, n)` | Highest-degree nodes (the "god nodes"). |
| `query_subgraph(concepts, scope, max_hops, limit)` | Subgraph around a list of concepts; reports node + edge counts. |
| `get_node_info(node_id, scope)` | Full metadata + top neighbors for one node. |
| `get_community_members(node_id, scope, limit)` | All nodes in the same community-detection cluster. |

Scope defaults to `personal`; pass `scope="onde"` (or whatever secondary scope name you've configured) for the second graph.

## Configuration

Two env vars, both optional:

| Env var | Default | Use for |
|---|---|---|
| `GRAPH_JSON_PATH` | `~/Documents/Vault/Meta/graphify-out/graph.json` | Primary graph (the `personal` scope) |
| `SECONDARY_GRAPH_JSON_PATH` | `~/Documents/Vault/Team/Meta/graphify-out/graph.json` | Secondary graph (the `onde` scope, historical name) |

`ONDE_GRAPH_JSON_PATH` is also accepted as a backward-compat alias for `SECONDARY_GRAPH_JSON_PATH`.

If a path doesn't exist at startup, the server logs a warning and the tools return a friendly error when that scope is queried. The server still starts — a missing secondary graph never blocks the primary.

## Install

Open Claude Code, paste:

    /plugin marketplace add adelaidasofia/graph-query-mcp
    /plugin install graph-query-mcp@graph-query-mcp

<details><summary>Legacy install</summary>

```bash
git clone https://github.com/adelaidasofia/graph-query-mcp.git ~/.claude/graph-query-mcp
cd ~/.claude/graph-query-mcp
pip3 install --break-system-packages -r requirements.txt
```

Register in your project `.mcp.json`:

```json
{
  "mcpServers": {
    "graph-query": {
      "type": "stdio",
      "command": "fastmcp",
      "args": ["run", "/Users/YOU/.claude/graph-query-mcp/server.py"],
      "env": {
        "GRAPH_JSON_PATH": "/path/to/your/vault/Meta/graphify-out/graph.json"
      }
    }
  }
}
```

Restart Claude Code, then `claude mcp list` should show `graph-query` connected.

</details>

## Generating the graph

This MCP doesn't build the graph; it queries one. Use [`graphify`](https://github.com/adelaidasofia/ai-brain-starter) (a skill in ai-brain-starter) to produce a `graph.json` from your vault, or any other NetworkX-compatible builder. The expected format is the output of `networkx.node_link_data(G)`.

## Verification

```bash
python3 tests/integration/test_smoke.py
# expected: PASSED — graph-query-mcp smoke (4 steps green)
```

## Architecture

FastMCP, stdio transport, Python 3.10+. Graphs are loaded once at startup and cached in memory. No daemons, no listeners, no external services. NetworkX in-memory for query primitives.

## Related MCPs

Same author, same architecture pattern (FastMCP, draft+confirm on writes where applicable, vault auto-export, MIT):

- [slack-mcp](https://github.com/adelaidasofia/slack-mcp) — multi-workspace Slack
- [imessage-mcp](https://github.com/adelaidasofia/imessage-mcp) — macOS iMessage
- [whatsapp-mcp](https://github.com/adelaidasofia/whatsapp-mcp) — WhatsApp via whatsmeow
- [apollo-mcp](https://github.com/adelaidasofia/apollo-mcp) — Apollo.io CRM + sequences
- [google-workspace-mcp](https://github.com/adelaidasofia/google-workspace-mcp) — Gmail / Calendar / Drive / Docs / Sheets
- [substack-mcp](https://github.com/adelaidasofia/substack-mcp) — Substack writing + analytics
- [parse-mcp](https://github.com/adelaidasofia/parse-mcp) — markitdown / Docling / LlamaParse router
- [luma-mcp](https://github.com/adelaidasofia/luma-mcp) — lu.ma events
- [graph-autotagger-mcp](https://github.com/adelaidasofia/graph-autotagger-mcp) — wikilink suggestions from the same graph format


## Telemetry

This plugin sends a single anonymous install signal to `myceliumai.co` the first time it loads in a Claude Code session on a given machine.

**What is sent:**
- Plugin name (e.g. `slack-mcp`)
- Plugin version (e.g. `0.1.0`)

**What is NOT sent:**
- No user identifiers, names, emails, tokens, or API keys
- No file paths, message content, or anything from your work
- No IP address is stored after dedup processing

**Why:** Helps the maintainer know which plugins people actually install, so attention goes to the ones that get used.

**Opt out:** Set the environment variable `MYCELIUM_NO_PING=1` before launching Claude Code. The hook will skip the network call entirely. Already-pinged installs leave a sentinel at `~/.mycelium/onboarded-<plugin>` — delete it if you want to reset state.

## License

MIT. See [LICENSE](LICENSE).

---

Built by Adelaida Diaz-Roa. Full install or team version at [diazroa.com](https://diazroa.com).
