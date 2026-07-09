"""Build ESI's brain graph — nodes and links from three sources:

1. Folders/vaults you configure in esi_config.json (markdown [[wikilinks]]
   become edges, like Obsidian)
2. The installed skill arsenal (.claude/skills, agents, commands + vendor
   toolkits)
3. ESI's long-term memory (~/.jarvis/memory.md)
"""

import re
import time
from pathlib import Path

from memory import MEMORY_PATH

REPO = Path(__file__).parent
WIKILINK = re.compile(r"\[\[([^\]|#]+)")
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".obsidian", ".venv", "venv"}
TEXT_EXT = {".md", ".txt"}
MAX_NODES = 3000
PREVIEW_CHARS = 700


class _Graph:
    def __init__(self):
        self.nodes = {}
        self.links = []

    def add(self, nid, name, ntype, content=""):
        if nid not in self.nodes:
            self.nodes[nid] = {"id": nid, "name": name, "type": ntype, "content": content}
        return nid

    def link(self, a, b):
        if a != b and a in self.nodes and b in self.nodes:
            self.links.append({"source": a, "target": b})


def _preview(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:PREVIEW_CHARS]
    except OSError:
        return ""


def _add_skills(g: _Graph, core: str):
    # Which toolkit did each skill come from? (vendor submodules, if present)
    origin = {}
    vendor = REPO / "vendor"
    if vendor.is_dir():
        for tk in sorted(vendor.iterdir()):
            if (tk / "skills").is_dir() or tk.name in ("ruflo", "open-design", "voicebox"):
                g.add(f"toolkit:{tk.name}", tk.name, "toolkit", _preview(tk / "README.md"))
                g.link(f"toolkit:{tk.name}", core)
            skills_dir = tk / "skills"
            if skills_dir.is_dir():
                for d in skills_dir.iterdir():
                    origin[d.name] = f"toolkit:{tk.name}"

    for kind, sub in (("skill", "skills"), ("agent", "agents"), ("command", "commands")):
        base = REPO / ".claude" / sub
        if not base.is_dir():
            continue
        for entry in sorted(base.iterdir()):
            name = entry.stem
            doc = entry / "SKILL.md" if entry.is_dir() else entry
            nid = g.add(f"{kind}:{name}", name, kind, _preview(doc) if doc.is_file() else "")
            hub = origin.get(entry.name) or origin.get(name) or "toolkit:ECC"
            g.link(nid, hub if hub in g.nodes else core)


def _add_memory(g: _Graph, core: str):
    if not MEMORY_PATH.exists():
        return
    hub = g.add("memory", "Memory", "hub", f"ESI's long-term memory ({MEMORY_PATH})")
    g.link(hub, core)
    for i, line in enumerate(MEMORY_PATH.read_text(encoding="utf-8").splitlines()):
        line = line.strip().lstrip("- ")
        if line:
            nid = g.add(f"mem:{i}", line[:60], "memory", line)
            g.link(nid, hub)


def _add_folder(g: _Graph, core: str, root: Path, max_files: int):
    root = root.expanduser()
    if not root.is_dir():
        return
    root_id = g.add(f"dir:{root}", root.name, "hub", str(root))
    g.link(root_id, core)
    notes = {}  # lowercase stem -> node id, for wikilink resolution
    count = 0
    for path in sorted(root.rglob("*")):
        if count >= max_files or len(g.nodes) >= MAX_NODES:
            break
        if any(p in SKIP_DIRS or p.startswith(".") for p in path.relative_to(root).parts):
            continue
        parent_id = f"dir:{path.parent}" if path.parent != root else root_id
        if path.is_dir():
            g.add(f"dir:{path}", path.name, "folder", str(path))
            g.link(f"dir:{path}", parent_id if parent_id in g.nodes else root_id)
            continue
        count += 1
        if path.suffix.lower() in TEXT_EXT:
            nid = g.add(f"note:{path}", path.stem, "note", _preview(path))
            notes[path.stem.lower()] = nid
        else:
            nid = g.add(f"file:{path}", path.name, "file", str(path))
        g.link(nid, parent_id if parent_id in g.nodes else root_id)

    # second pass: markdown wikilinks between notes
    for stem, nid in notes.items():
        path = Path(nid[5:])
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for target in WIKILINK.findall(text):
            tid = notes.get(target.strip().lower())
            if tid:
                g.link(nid, tid)


def build_graph(config: dict) -> dict:
    brain = config.get("brain", {})
    g = _Graph()
    core = g.add("core", config.get("name", "ESI"), "core",
                 config.get("tagline", "Enhanced Synthetic Intelligence"))

    if brain.get("include_skills", True):
        _add_skills(g, core)
    if brain.get("include_memory", True):
        _add_memory(g, core)
    for folder in brain.get("folders", []):
        _add_folder(g, core, Path(folder), brain.get("max_files_per_folder", 400))

    # node size = connection count (capped)
    degree = {}
    for l in g.links:
        degree[l["source"]] = degree.get(l["source"], 0) + 1
        degree[l["target"]] = degree.get(l["target"], 0) + 1
    for n in g.nodes.values():
        n["val"] = min(20, 1 + degree.get(n["id"], 0) * 0.6)

    return {"nodes": list(g.nodes.values()), "links": g.links,
            "built_at": time.time()}
