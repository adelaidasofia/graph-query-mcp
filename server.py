#!/usr/bin/env python3
"""Graph Query MCP: surgical queries against a vault knowledge graph.

Loads graph.json (NetworkX node-link format) once at startup and answers
targeted queries without requiring Claude to read the full GRAPH_REPORT.md.

Designed to pair with `graphify` (the graph-building skill in ai-brain-starter).
Supports two scopes by default, configurable via env vars: a "primary"
scope (your personal vault) and a "secondary" scope (a team or project vault).
The scope names "personal" and "onde" are accepted as historical aliases for
"primary" and "secondary" \u2014 useful when migrating from older configs.

Tools:
  search_nodes          - find nodes by name (fuzzy)
  get_neighbors         - get connected nodes up to N hops
  find_path             - shortest path between two concepts
  get_top_nodes         - most connected nodes by degree
  query_subgraph        - subgraph around a list of concepts
  get_node_info         - all metadata for a specific node
  get_community_members - all nodes in the same community as a given node
"""

import json
import os
from pathlib import Path
from typing import Optional

import networkx as nx
from fastmcp import FastMCP

# --- CONFIG -------------------------------------------------------------------
# Primary graph: your personal vault. Override with GRAPH_JSON_PATH env var.
PERSONAL_GRAPH = Path(
    os.environ.get(
        "GRAPH_JSON_PATH",
        str(Path.home() / "Documents" / "Vault" / "Meta" / "graphify-out" / "graph.json"),
    )
)
# Secondary graph: a team or project vault. Override with SECONDARY_GRAPH_JSON_PATH
# (preferred) or ONDE_GRAPH_JSON_PATH (historical alias for backward compat).
ONDE_GRAPH = Path(
    os.environ.get(
        "SECONDARY_GRAPH_JSON_PATH",
        os.environ.get(
            "ONDE_GRAPH_JSON_PATH",
            str(Path.home() / "Documents" / "Vault" / "Team" / "Meta" / "graphify-out" / "graph.json"),
        ),
    )
)

# --- GRAPH LOADING (cached at startup) ----------------------------------------
_graphs: dict = {}


def _load_graph(path: Path, name: str) -> Optional[nx.Graph]:
    if not path.exists():
        return None
    try:
        with open(path) as f:
            data = json.load(f)
        return nx.node_link_graph(data, edges="links")
    except Exception as e:
        print(f"[graph-query-mcp] Failed to load {name}: {e}")
        return None


def _get_graph(scope: str):
    """Return (graph, error_str). scope: 'personal' or 'onde'."""
    if scope not in _graphs:
        path = PERSONAL_GRAPH if scope == "personal" else ONDE_GRAPH
        g = _load_graph(path, scope)
        if g is None:
            return None, f"Graph '{scope}' not found at {path}"
        _graphs[scope] = g
    return _graphs[scope], ""


def _fuzzy_match(G: nx.Graph, query: str, limit: int) -> list:
    q = query.lower()
    exact, starts, contains = [], [], []
    for n in G.nodes():
        nl = str(n).lower()
        if nl == q:
            exact.append(n)
        elif nl.startswith(q):
            starts.append(n)
        elif q in nl:
            contains.append(n)
    return (exact + starts + contains)[:limit]


def _node_summary(G: nx.Graph, node_id: str) -> dict:
    data = dict(G.nodes[node_id]) if node_id in G.nodes else {}
    degree = G.degree(node_id) if node_id in G.nodes else 0
    neighbors = list(G.neighbors(node_id)) if node_id in G.nodes else []
    return {
        "id": node_id,
        "degree": degree,
        "top_neighbors": sorted(neighbors, key=lambda n: G.degree(n), reverse=True)[:10],
        "metadata": {k: v for k, v in data.items() if k != "id"},
    }


# --- MCP SERVER ---------------------------------------------------------------
mcp = FastMCP("graph-query")


@mcp.tool()
def search_nodes(query: str, scope: str = "personal", limit: int = 20) -> str:
    """Find nodes by name (fuzzy match). scope: 'personal' or 'onde'."""
    G, err = _get_graph(scope)
    if err:
        return err
    matches = _fuzzy_match(G, query, limit)
    if not matches:
        return f"No nodes found matching '{query}' in {scope} graph."
    rows = [f"{n} (degree={G.degree(n)})" for n in matches]
    return f"Found {len(matches)} match(es) for '{query}' in {scope} graph:\n" + "\n".join(rows)


@mcp.tool()
def get_neighbors(node_id: str, scope: str = "personal", max_hops: int = 1, limit: int = 30) -> str:
    """Get nodes connected to node_id within max_hops, sorted by degree."""
    G, err = _get_graph(scope)
    if err:
        return err
    if node_id not in G.nodes:
        matches = _fuzzy_match(G, node_id, 1)
        if not matches:
            return f"Node '{node_id}' not found in {scope} graph."
        node_id = matches[0]
    if max_hops == 1:
        neighbors = list(G.neighbors(node_id))
    else:
        ego = nx.ego_graph(G, node_id, radius=max_hops)
        neighbors = [n for n in ego.nodes() if n != node_id]
    top = sorted(neighbors, key=lambda n: G.degree(n), reverse=True)[:limit]
    rows = [f"{n} (degree={G.degree(n)})" for n in top]
    return (
        f"Node '{node_id}' (degree={G.degree(node_id)}) -- {len(neighbors)} neighbor(s) within {max_hops} hop(s).\n"
        f"Top {len(top)}:\n" + "\n".join(rows)
    )


@mcp.tool()
def find_path(source: str, target: str, scope: str = "personal") -> str:
    """Find shortest path between two concepts. Auto-fuzzy-matches node names."""
    G, err = _get_graph(scope)
    if err:
        return err
    s_matches = _fuzzy_match(G, source, 1)
    t_matches = _fuzzy_match(G, target, 1)
    if not s_matches:
        return f"Source '{source}' not found."
    if not t_matches:
        return f"Target '{target}' not found."
    s, t = s_matches[0], t_matches[0]
    try:
        path = nx.shortest_path(G, s, t)
        return f"Path from '{s}' to '{t}' ({len(path)-1} hops):\n" + " -> ".join(path)
    except nx.NetworkXNoPath:
        return f"No path between '{s}' and '{t}'."
    except nx.NodeNotFound as e:
        return f"Node not found: {e}"


@mcp.tool()
def get_top_nodes(scope: str = "personal", n: int = 20) -> str:
    """Get the most connected nodes (god nodes) by degree."""
    G, err = _get_graph(scope)
    if err:
        return err
    top = sorted(G.degree(), key=lambda x: x[1], reverse=True)[:n]
    rows = [f"{i+1}. {node} (degree={deg})" for i, (node, deg) in enumerate(top)]
    return f"Top {n} nodes in {scope} graph ({G.number_of_nodes()} total):\n" + "\n".join(rows)


@mcp.tool()
def query_subgraph(concepts: list, scope: str = "personal", max_hops: int = 1, limit: int = 40) -> str:
    """Get the subgraph connecting a list of concepts."""
    G, err = _get_graph(scope)
    if err:
        return err
    resolved = []
    for c in concepts:
        matches = _fuzzy_match(G, c, 1)
        resolved.append(matches[0] if matches else c)
    subgraph_nodes = set()
    for node in resolved:
        if node in G.nodes:
            ego = nx.ego_graph(G, node, radius=max_hops)
            subgraph_nodes.update(ego.nodes())
    if not subgraph_nodes:
        return f"None of the concepts found in {scope} graph: {concepts}"
    sub = G.subgraph(subgraph_nodes)
    top_nodes = sorted(sub.degree(), key=lambda x: x[1], reverse=True)[:limit]
    rows = [f"{node} (degree={deg})" for node, deg in top_nodes]
    return (
        f"Subgraph for {resolved} ({max_hops} hop radius): "
        f"{sub.number_of_nodes()} nodes, {sub.number_of_edges()} edges.\n"
        f"Top connected nodes:\n" + "\n".join(rows)
    )


@mcp.tool()
def get_node_info(node_id: str, scope: str = "personal") -> str:
    """Get full metadata and top neighbors for a specific node."""
    G, err = _get_graph(scope)
    if err:
        return err
    matches = _fuzzy_match(G, node_id, 3)
    if not matches:
        return f"Node '{node_id}' not found in {scope} graph."
    node_id = matches[0]
    info = _node_summary(G, node_id)
    lines = [
        f"Node: {info['id']}",
        f"Degree: {info['degree']}",
        f"Top neighbors: {', '.join(info['top_neighbors'])}",
    ]
    if info["metadata"]:
        lines.append(f"Metadata: {json.dumps(info['metadata'], indent=2)}")
    if len(matches) > 1:
        lines.append(f"Also matched: {', '.join(matches[1:])}")
    return "\n".join(lines)


@mcp.tool()
def get_community_members(node_id: str, scope: str = "personal", limit: int = 30) -> str:
    """Get all nodes in the same community as the given node, sorted by degree."""
    G, err = _get_graph(scope)
    if err:
        return err
    matches = _fuzzy_match(G, node_id, 1)
    if not matches:
        return f"Node '{node_id}' not found in {scope} graph."
    node_id = matches[0]
    node_data = dict(G.nodes[node_id])
    community_id = node_data.get("community")
    if community_id is None:
        return f"Node '{node_id}' has no community attribute."
    members = [n for n in G.nodes() if G.nodes[n].get("community") == community_id]
    top = sorted(members, key=lambda n: G.degree(n), reverse=True)[:limit]
    rows = [f"{n} (degree={G.degree(n)})" for n in top]
    return (
        f"Community {community_id}: {len(members)} members. '{node_id}' is here.\n"
        f"Top {len(top)} by degree:\n" + "\n".join(rows)
    )


if __name__ == "__main__":
    for scope, path in [("personal", PERSONAL_GRAPH), ("onde", ONDE_GRAPH)]:
        if path.exists():
            g = _load_graph(path, scope)
            if g:
                _graphs[scope] = g
                print(f"[graph-query-mcp] Loaded {scope}: {g.number_of_nodes()} nodes, {g.number_of_edges()} edges")
    mcp.run()
