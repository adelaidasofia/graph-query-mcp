"""Smoke integration test for graph-query-mcp.

Bare script. `python3 tests/integration/test_smoke.py` from repo root.
Exits 0 on full pass.

Covers:
  1. Server imports without error
  2. Server starts with no graphs configured (graceful degradation)
  3. Loads a tiny synthetic graph + queries it end-to-end
  4. No personal data in committable source
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def step(name: str) -> None:
    print(f"  ✓ {name}")


def fail(step_name: str, msg: str) -> None:
    print(f"  ✗ FAIL at step: {step_name}")
    print(f"    {msg}")
    sys.exit(1)


def main() -> int:
    print("graph-query-mcp smoke")

    # Step 1: imports
    name = "imports"
    try:
        # Point env at temp paths so server import doesn't try to load real graphs
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["GRAPH_JSON_PATH"] = str(Path(tmp) / "nope.json")
            os.environ["SECONDARY_GRAPH_JSON_PATH"] = str(Path(tmp) / "nope2.json")
            import server  # noqa: F401
        step(name)
    except Exception as e:  # noqa: BLE001
        fail(name, f"import failed: {e}")

    # Step 2: graceful degradation when graph file missing
    name = "graceful degradation when graph file missing"
    try:
        import server
        from importlib import reload
        # Force reload so cached _graphs reset
        reload(server)
        g, err = server._get_graph("personal")
        if g is not None:
            fail(name, f"expected None for missing graph, got {type(g)}")
        if "not found" not in err.lower():
            fail(name, f"expected 'not found' error, got: {err}")
        step(name)
    except Exception as e:  # noqa: BLE001
        fail(name, str(e))

    # Step 3: load a tiny synthetic graph + query end-to-end
    name = "load + query a synthetic NetworkX node-link graph"
    try:
        import networkx as nx
        G = nx.Graph()
        G.add_node("alpha", community=1)
        G.add_node("beta", community=1)
        G.add_node("gamma", community=2)
        G.add_edges_from([("alpha", "beta"), ("beta", "gamma")])
        # Server uses edges="links" — write the fixture with the same key.
        data = nx.node_link_data(G, edges="links")
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            json.dump(data, f)
            tmp_path = f.name
        os.environ["GRAPH_JSON_PATH"] = tmp_path
        import server
        from importlib import reload
        reload(server)
        # search_nodes
        result = server.search_nodes("alpha", "personal", 5)
        if "alpha" not in result:
            fail(name, f"search_nodes didn't find 'alpha': {result}")
        # get_top_nodes
        result = server.get_top_nodes("personal", 3)
        if "beta" not in result:  # beta has degree 2
            fail(name, f"get_top_nodes didn't surface beta: {result}")
        # find_path
        result = server.find_path("alpha", "gamma", "personal")
        if "alpha -> beta -> gamma" not in result:
            fail(name, f"find_path didn't return expected path: {result}")
        os.unlink(tmp_path)
        step(name)
    except Exception as e:  # noqa: BLE001
        fail(name, str(e))

    # Step 4: no personal data in committable source
    name = "no third-party personal names in committable source"
    try:
        import re
        BANNED = re.compile(
            r"\b(Sergio|Diana|Paola|Beverly|Natalia|Silvia|Accenture|Centre415|vinitos)\b"
            r"|High-Rise|After the Shock|tech@onde|🚀 Onde Team|adelaidadiaz-roa|/Adelaida Notes/"
        )
        hits = []
        for ext in ("*.py", "*.md", "*.toml"):
            for path in ROOT.rglob(ext):
                if any(part in {".venv", "__pycache__", "tests"} for part in path.parts):
                    continue
                try:
                    text = path.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue
                for m in BANNED.finditer(text):
                    hits.append(f"{path.relative_to(ROOT)}: {m.group()}")
        if hits:
            fail(name, f"personal data hits: {hits[:5]}")
        step(name)
    except Exception as e:  # noqa: BLE001
        fail(name, str(e))

    print("\nPASSED — graph-query-mcp smoke (4 steps green)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
