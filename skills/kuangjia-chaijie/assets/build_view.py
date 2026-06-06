#!/usr/bin/env python3
"""Build view.html from a kuangjia-chaijie topic directory.

Usage: python build_view.py <topic_dir>
"""
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

PLACEHOLDER = "/*__DATA_PLACEHOLDER__*/"

VERIFY_CATEGORIES = [
    ("passed", ["✅ 通过的声明", "✅ Confirmed", "通过的声明", "Confirmed"]),
    ("warnings", ["⚠️ 轻度偏差", "⚠️ Warnings", "轻度偏差", "Warnings"]),
    ("blockers", ["🔴 实质错误", "🔴 Critical", "实质错误", "Critical"]),
    ("needs_verify", ["🔍 可疑/未能验证", "🔍 Observation", "可疑/未能验证", "Observation"]),
    ("backfill", ["反向 amend 建议", "Backfill"]),
]

TAG_PATTERNS = {
    "blocker": re.compile(r"\[BLOCKER\]"),
    "must_fix": re.compile(r"\[MUST-FIX\]"),
    "optional": re.compile(r"\[OPTIONAL\]"),
    "needs_verify": re.compile(r"\[NEEDS-MANUAL-VERIFY\]|\[NEEDS-VERIFY\]"),
}


def parse_sections(text: str, level: int = 2) -> dict:
    """Split markdown by heading level. H3+ stays in body when level=2."""
    prefix = "#" * level + " "
    sections = {}
    current = None
    lines = []
    for line in text.splitlines():
        if line.startswith(prefix) and not line.startswith(prefix + "#"):
            if current is not None:
                sections[current] = "\n".join(lines).strip()
            current = line[len(prefix):].strip()
            lines = []
        else:
            lines.append(line)
    if current is not None:
        sections[current] = "\n".join(lines).strip()
    return sections


def parse_sections_smart(text: str) -> dict:
    """Try H2 first; if doc has ≤1 H2 section, fall back to H3 (verification reports)."""
    h2 = parse_sections(text, level=2)
    if len(h2) >= 2:
        return h2
    # Combine H2 preamble + H3 sections
    h3 = parse_sections(text, level=3)
    return h3 if h3 else h2


def find_section(sections: dict, variants) -> str:
    """Return first section whose key contains any variant string."""
    for v in variants:
        for k, body in sections.items():
            if v in k:
                return body
    return ""


def extract_top_bullets(text: str) -> list:
    """Extract top-level '- ' bullets, joining continuation lines (2+ spaces indented)."""
    items = []
    current = None
    for line in text.splitlines():
        if line.startswith("- "):
            if current is not None:
                items.append(current.rstrip())
            current = line[2:]
        elif current is not None and (line.startswith("  ") or line.startswith("\t")):
            current += "\n" + line
        elif current is not None and line.strip() == "":
            current += "\n"
        else:
            if current is not None:
                items.append(current.rstrip())
                current = None
    if current is not None:
        items.append(current.rstrip())
    return [b.strip() for b in items if b.strip()]


def extract_mermaid_blocks(text: str) -> list:
    """Extract ```mermaid code blocks."""
    return re.findall(r"```mermaid\n(.*?)\n```", text, flags=re.DOTALL)


def extract_tables(text: str) -> list:
    """Parse markdown tables into list of {headers: [...], rows: [[...], ...]}."""
    tables = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("|") and "|" in line[1:]:
            # potential table header
            if i + 1 < len(lines) and re.match(r"^\|[\s\-:|]+\|$", lines[i + 1].strip()):
                headers = [c.strip() for c in line.strip("|").split("|")]
                rows = []
                j = i + 2
                while j < len(lines) and lines[j].strip().startswith("|"):
                    cells = [c.strip() for c in lines[j].strip().strip("|").split("|")]
                    rows.append(cells)
                    j += 1
                tables.append({"headers": headers, "rows": rows})
                i = j
                continue
        i += 1
    return tables


def parse_verification(filename: str, sections: dict) -> dict:
    result = {"filename": filename, "summary": find_section(sections, ["总结", "Summary"])}
    for key, variants in VERIFY_CATEGORIES:
        body = find_section(sections, variants)
        result[key] = extract_top_bullets(body) if body else []
    return result


def parse_card(filename: str, sections: dict) -> dict:
    """Phase 2 card: extract 7 elements + lifecycle + tradeoff + review."""
    slug = filename[3:-3]  # 02-{slug}.md
    elements = {}
    for name in [
        "涉及文件",
        "生产",
        "消费",
        "存储",
        "分层",
        "提供方式",
        "运行时形态",
        "设计取舍",
    ]:
        elements[name] = find_section(sections, [name])

    lifecycle = find_section(sections, ["数据生命周期图", "生命周期图"])
    review = find_section(sections, ["回顾"])

    return {
        "filename": filename,
        "slug": slug,
        "elements": elements,
        "lifecycle_diagram": extract_mermaid_blocks(lifecycle)[:1],
        "review": review,
    }


def parse_panorama(filename: str, sections: dict) -> dict:
    result = {"filename": filename, "raw_sections": sections}
    rel = find_section(sections, ["子模块关系图"])
    own = find_section(sections, ["文件归属图"])
    result["relations_diagram"] = extract_mermaid_blocks(rel)[:1]
    result["ownership_diagram"] = extract_mermaid_blocks(own)[:1]

    subsystems_body = find_section(sections, ["候选子模块"])
    subs = []
    pattern = re.compile(r"^###\s+(S\d+)[:\s\-]*(.+?)$", re.MULTILINE)
    for m in pattern.finditer(subsystems_body):
        subs.append({"id": m.group(1), "name": m.group(2).strip()})
    result["subsystems"] = subs

    result["v0"] = find_section(sections, ["核心抽象草稿", "v0"])
    result["coverage"] = find_section(sections, ["反向覆盖"])
    result["blindspots"] = find_section(sections, ["候选盲点", "盲点检阅"])
    result["assumptions"] = find_section(sections, ["假设"])
    result["decisions"] = find_section(sections, ["决议", "差异"])
    return result


def parse_synthesis(filename: str, sections: dict) -> dict:
    v1_body = find_section(sections, ["核心抽象 v1", "核心抽象"])
    arch_body = find_section(sections, ["架构总图"])
    patterns_body = find_section(sections, ["跨子模块模式归纳", "跨子模块模式"])
    conflicts_body = find_section(sections, ["跨卡矛盾收敛", "跨卡矛盾"])
    backfill_body = find_section(sections, ["上游回填决议", "上游回填"])
    rejected_body = find_section(sections, ["Rejected verifier findings", "Rejected"])

    # Parse patterns into structured cards (### 模式 N)
    pattern_blocks = re.split(r"^###\s+", patterns_body, flags=re.MULTILINE)
    patterns = []
    for block in pattern_blocks[1:]:
        first_line, _, rest = block.partition("\n")
        patterns.append({"title": first_line.strip(), "body": rest.strip()})

    return {
        "filename": filename,
        "v1": v1_body,
        "architecture_diagram": extract_mermaid_blocks(arch_body)[:1],
        "patterns": patterns,
        "conflicts": conflicts_body,
        "backfill_tables": extract_tables(backfill_body),
        "backfill_raw": backfill_body,
        "rejected": rejected_body,
    }


def count_tags(text: str, health: dict) -> None:
    for k, pat in TAG_PATTERNS.items():
        health[k] += len(pat.findall(text))


def categorize_file(name: str) -> str:
    if name == "00-seed.md":
        return "seed"
    if name == "01-panorama.md":
        return "panorama"
    if "panorama" in name and "verification" in name:
        return "panorama_verification"
    if "panorama-amendments" in name or "panorama_amendments" in name:
        return "panorama_amendments"
    if name.startswith("02-") and "verification" in name:
        return "card_verification"
    if name.startswith("02-"):
        return "card"
    if name.startswith("03-") and "verification" in name:
        return "synthesis_verification"
    if name.startswith("03-"):
        return "synthesis"
    return "other"


def collect_data(topic_dir: Path) -> dict:
    data = {
        "topic": topic_dir.name,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "phases": {
            "phase0": {"seed": None},
            "phase1": {"panorama": None, "verifications": [], "amendments": []},
            "phase2": {"cards": [], "verifications": []},
            "phase3": {"synthesis": None, "verifications": []},
        },
        "subsystems": [],
        "health": {"blocker": 0, "must_fix": 0, "optional": 0, "needs_verify": 0},
        "files": [],
    }

    md_files = sorted(topic_dir.glob("*.md"))
    for md_path in md_files:
        name = md_path.name
        text = md_path.read_text(encoding="utf-8")
        kind = categorize_file(name)
        # verification reports use H3 as section level; others use H2
        if "verification" in kind:
            sections = parse_sections_smart(text)
        else:
            sections = parse_sections(text, level=2)
        data["files"].append({"filename": name, "kind": kind, "bytes": len(text)})

        if kind in ("panorama_verification", "card_verification", "synthesis_verification"):
            count_tags(text, data["health"])

        if kind == "seed":
            data["phases"]["phase0"]["seed"] = {
                "filename": name,
                "sections": sections,
            }
        elif kind == "panorama":
            pano = parse_panorama(name, sections)
            data["phases"]["phase1"]["panorama"] = pano
            data["subsystems"] = pano["subsystems"]
        elif kind == "panorama_verification":
            data["phases"]["phase1"]["verifications"].append(
                parse_verification(name, sections)
            )
        elif kind == "panorama_amendments":
            data["phases"]["phase1"]["amendments"].append(
                {"filename": name, "sections": sections}
            )
        elif kind == "card":
            data["phases"]["phase2"]["cards"].append(parse_card(name, sections))
        elif kind == "card_verification":
            data["phases"]["phase2"]["verifications"].append(
                parse_verification(name, sections)
            )
        elif kind == "synthesis":
            data["phases"]["phase3"]["synthesis"] = parse_synthesis(name, sections)
        elif kind == "synthesis_verification":
            data["phases"]["phase3"]["verifications"].append(
                parse_verification(name, sections)
            )

    return data


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python build_view.py <topic_dir>", file=sys.stderr)
        return 1

    topic_dir = Path(sys.argv[1]).resolve()
    if not topic_dir.is_dir():
        print(f"error: {topic_dir} is not a directory", file=sys.stderr)
        return 1

    skill_dir = Path(__file__).resolve().parent
    template_path = skill_dir / "template.html"
    if not template_path.exists():
        print(f"error: template not found at {template_path}", file=sys.stderr)
        return 1

    output = topic_dir / "view.html"
    if output.exists():
        shutil.copy(output, topic_dir / "view.html.bak")

    data = collect_data(topic_dir)
    template = template_path.read_text(encoding="utf-8")
    payload = json.dumps(data, ensure_ascii=False, indent=2)
    html = template.replace(PLACEHOLDER, payload)
    output.write_text(html, encoding="utf-8")
    print(
        f"✓ {output}  ({len(html):,} bytes, "
        f"{len(data['files'])} md files, "
        f"health: 🔴{data['health']['blocker']} ⚠️{data['health']['must_fix']} "
        f"🔍{data['health']['needs_verify']})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
