#!/usr/bin/env python3
"""
py-depgraph: Analyze Python import dependencies across a project.

Builds an import graph using Python's ast module, then:
- Detects circular imports (death spirals)
- Finds god modules (highest in-degree — everything imports them)
- Finds isolated modules (no imports, not imported)
- Outputs JSON data + ASCII report
"""

import ast
import os
import sys
import json
import argparse
from pathlib import Path
from collections import defaultdict, deque


def find_python_files(root: str) -> list[str]:
    """Recursively find all .py files under root."""
    root_path = Path(root)
    return [
        str(p.relative_to(root_path))
        for p in root_path.rglob("*.py")
        if not any(part.startswith(".") or part in ("__pycache__", "node_modules", "venv", ".venv", "env")
                   for part in p.parts)
    ]


def extract_imports(filepath: str) -> list[str]:
    """Parse a Python file and extract all imported module names."""
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            source = f.read()
        tree = ast.parse(source, filename=filepath)
    except SyntaxError:
        return []

    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module.split(".")[0])
    return list(set(imports))


def module_name_from_path(filepath: str) -> str:
    """Convert a file path like src/utils/parser.py to src.utils.parser."""
    return filepath.replace(os.sep, ".").replace("/", ".").removesuffix(".py")


def build_graph(root: str) -> dict:
    """
    Build import dependency graph for a Python project.
    
    Returns:
        {
          "nodes": {module_name: {"file": path, "imports": [...], "imported_by": [...]}},
          "edges": [[from, to], ...],
          "project_modules": set of internal module names
        }
    """
    py_files = find_python_files(root)
    
    # Map short module names (last component) and full dotted names to files
    nodes = {}
    for filepath in py_files:
        mod = module_name_from_path(filepath)
        nodes[mod] = {"file": filepath, "imports": [], "imported_by": []}
    
    project_mods = set(nodes.keys())
    # Also map simple names (last segment) for resolution
    short_to_full = {}
    for mod in project_mods:
        short = mod.split(".")[-1]
        short_to_full.setdefault(short, []).append(mod)
    
    edges = []
    for mod, data in nodes.items():
        full_path = os.path.join(root, data["file"])
        raw_imports = extract_imports(full_path)
        
        resolved = set()
        for imp in raw_imports:
            # Check if it's a direct project module
            if imp in project_mods:
                resolved.add(imp)
            # Check if short name maps to a project module
            elif imp in short_to_full:
                for candidate in short_to_full[imp]:
                    resolved.add(candidate)
        
        # Remove self-imports
        resolved.discard(mod)
        
        data["imports"] = sorted(resolved)
        for dep in resolved:
            edges.append([mod, dep])
            nodes[dep]["imported_by"].append(mod)
    
    # Deduplicate imported_by
    for data in nodes.values():
        data["imported_by"] = sorted(set(data["imported_by"]))
    
    return {"nodes": nodes, "edges": edges, "project_modules": sorted(project_mods)}


def find_cycles(nodes: dict) -> list[list[str]]:
    """
    Find all cycles in the import graph using DFS.
    Returns list of cycles (each cycle is a list of module names).
    """
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {m: WHITE for m in nodes}
    cycles = []
    path = []
    
    def dfs(node):
        color[node] = GRAY
        path.append(node)
        for dep in nodes[node]["imports"]:
            if dep not in color:
                continue
            if color[dep] == GRAY:
                # Found a cycle — extract it
                cycle_start = path.index(dep)
                cycles.append(path[cycle_start:] + [dep])
            elif color[dep] == WHITE:
                dfs(dep)
        path.pop()
        color[node] = BLACK
    
    for node in nodes:
        if color[node] == WHITE:
            dfs(node)
    
    return cycles


def compute_metrics(graph: dict) -> dict:
    """Compute per-module and global metrics."""
    nodes = graph["nodes"]
    
    metrics = {}
    for mod, data in nodes.items():
        in_degree = len(data["imported_by"])
        out_degree = len(data["imports"])
        metrics[mod] = {
            "in_degree": in_degree,    # how many modules import this
            "out_degree": out_degree,  # how many modules this imports
            "coupling": in_degree + out_degree,
        }
    
    cycles = find_cycles(nodes)
    
    # God modules: top N by in_degree
    god_modules = sorted(
        [(m, metrics[m]["in_degree"]) for m in metrics if metrics[m]["in_degree"] > 0],
        key=lambda x: -x[1]
    )
    
    # Isolated modules: no imports AND not imported by anyone
    isolated = [m for m in metrics if metrics[m]["coupling"] == 0]
    
    return {
        "metrics": metrics,
        "cycles": cycles,
        "god_modules": god_modules[:10],
        "isolated_modules": isolated,
    }


def render_ascii_report(graph: dict, analysis: dict, root: str) -> str:
    """Render a human-readable ASCII report."""
    nodes = graph["nodes"]
    metrics = analysis["metrics"]
    cycles = analysis["cycles"]
    god_modules = analysis["god_modules"]
    isolated = analysis["isolated_modules"]
    
    lines = []
    lines.append("=" * 60)
    lines.append(f"  py-depgraph Report: {os.path.basename(os.path.abspath(root))}")
    lines.append("=" * 60)
    lines.append(f"  Total modules   : {len(nodes)}")
    lines.append(f"  Total edges     : {len(graph['edges'])}")
    lines.append(f"  Circular imports: {len(cycles)}")
    lines.append(f"  God modules     : {len(god_modules)}")
    lines.append(f"  Isolated modules: {len(isolated)}")
    lines.append("")
    
    # God modules
    if god_modules:
        lines.append("🏛  GOD MODULES (most imported):")
        lines.append(f"  {'Module':<40} {'In':>4} {'Out':>4} {'Total':>6}")
        lines.append(f"  {'-'*40} {'-'*4} {'-'*4} {'-'*6}")
        for mod, in_deg in god_modules[:15]:
            m = metrics[mod]
            lines.append(f"  {mod:<40} {m['in_degree']:>4} {m['out_degree']:>4} {m['coupling']:>6}")
        lines.append("")
    
    # Circular imports
    if cycles:
        lines.append("⚠️  CIRCULAR IMPORTS:")
        for i, cycle in enumerate(cycles[:10], 1):
            lines.append(f"  {i}. {' → '.join(cycle)}")
        if len(cycles) > 10:
            lines.append(f"  ... and {len(cycles) - 10} more")
        lines.append("")
    else:
        lines.append("✅  No circular imports detected")
        lines.append("")
    
    # Top coupled modules
    top_coupled = sorted(metrics.items(), key=lambda x: -x[1]["coupling"])[:10]
    if top_coupled:
        lines.append("🔗  MOST COUPLED MODULES:")
        lines.append(f"  {'Module':<40} {'Coupling':>8}")
        lines.append(f"  {'-'*40} {'-'*8}")
        for mod, m in top_coupled:
            if m["coupling"] > 0:
                lines.append(f"  {mod:<40} {m['coupling']:>8}")
        lines.append("")
    
    lines.append("=" * 60)
    return "\n".join(lines)


def analyze(root: str = ".", output_json: str | None = None, quiet: bool = False) -> dict:
    """Main analysis function."""
    root = os.path.abspath(root)
    
    if not os.path.isdir(root):
        raise ValueError(f"Not a directory: {root}")
    
    graph = build_graph(root)
    analysis = compute_metrics(graph)
    
    report = render_ascii_report(graph, analysis, root)
    if not quiet:
        print(report)
    
    result = {
        "root": root,
        "summary": {
            "total_modules": len(graph["nodes"]),
            "total_edges": len(graph["edges"]),
            "circular_imports": len(analysis["cycles"]),
            "god_modules": analysis["god_modules"],
            "isolated_modules": analysis["isolated_modules"],
        },
        "modules": graph["nodes"],
        "cycles": analysis["cycles"],
        "metrics": analysis["metrics"],
    }
    
    if output_json:
        with open(output_json, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
        if not quiet:
            print(f"\nJSON written to: {output_json}")
    
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Analyze Python import dependency graph",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python depgraph.py .
  python depgraph.py /path/to/project --json deps.json
  python depgraph.py . --quiet --json deps.json
"""
    )
    parser.add_argument("root", nargs="?", default=".", help="Project root directory (default: .)")
    parser.add_argument("--json", "-j", dest="output_json", default=None, help="Write JSON output to file")
    parser.add_argument("--quiet", "-q", action="store_true", help="Suppress ASCII report")
    args = parser.parse_args()
    
    try:
        analyze(args.root, args.output_json, args.quiet)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
