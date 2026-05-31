# 🔗 py-depgraph

![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![No dependencies](https://img.shields.io/badge/dependencies-none-brightgreen)

**Understand your Python codebase's import graph — find circular imports, god modules, and hidden coupling.**

`py-depgraph` uses Python's built-in `ast` module to parse every `.py` file in your project and build a dependency graph. No external tools, no pip installs. Point it at any Python project and instantly see who depends on whom.

## Why it matters

Large Python codebases accumulate invisible coupling over time. A "utils" module that started as a helper ends up imported by 40 files. A subtle circular import causes mysterious ImportError at runtime. `py-depgraph` surfaces these problems before they bite you.

## Features

- 🔍 Parses imports using `ast` — `no execution required
- ♻�️ Detects **circular imports** (the cycles that cause mysterious `ImportError`)
- 🏛 Identifies **god modules** (most-imported files — your hidden single points of failure)
- 🔗 Ranks modules by **coupling score** (in-degree + out-degree)
- 🏝 Finds **isolated modules** (dead code candidates)
- 📤 Outputs structured **JSON** for CI integration
- 🚫 Zero external dependencies — stdlib only

## Installation

```bash
git clone https://github.com/sushii15/py-depgraph
cd py-depgraph
# No pip install needed — pure Python stdlib
```

## Usage

```bash
# Analyze the current directory
python depgraph.py .

# Analyze a project, save JSON output
python depgraph.py /path/to/myproject --json deps.json

# Quiet mode (JSON only, no terminal output)
python depgraph.py . --quiet --json deps.json
```

### Example output

```
============================================================
  py-depgraph Report: myproject
============================================================
  Total modules   : 47
  Total edges     : 89
  Circular imports: 2
  God modules     : 8
  Isolated modules: 3

🏛  GOD MODULES (most imported):
  Module                                   In   Out  Total
  ---------------------------------------- ---- ---- ------
  utils                                     22    3     25
  config                                    18    1     19
  models.base                               14    5     19

⚛  CIRCULAR IMPORTS:
  1. auth.session → auth.user → auth.session
  2. core.engine → core.pipeline → core.engine

🔗  MOST COUPLED MODULES
  Module                                   Coupling
  ---------------------------------------- --------
  utils                                          25
  config                                         19
============================================================
```

## JSON output format

```json
{
  "summary": {
    "total_modules": 47,
    "total_edges": 89,
    "circular_imports": 2,
    "god_modules": [["utils", 22], ...],
    "isolated_modules": ["scratch", "old_test"]
  },
  "modules": {
    "utils": {
      "file": "utils.py",
      "imports": ["os", "sys"],
      "imported_by": ["main", "auth", ...]
    }
  },
  "cycles": [["auth.session", "auth.user", "auth.session"]],
  "metrics": {
    "utils": {"in_degree": 22, "out_degree": 3, "coupling": 25}
  }
}
```

## Running tests

```bash
python test_depgraph.py
```

## Contributing

Contributions welcome! Please open an issue first.

1. Fork the repo
2. Create a branch (`git checkout -b feature/my-feature`)
3. Commit and open a PR

## License

MIT License — Copyright (c) 2026 sushii15
