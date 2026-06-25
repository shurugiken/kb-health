#!/usr/bin/env python3
"""
kb_health_check.py — an LLM-powered health check for a Markdown knowledge base.

Point it at a folder of Markdown notes (an Obsidian vault, a docs/ tree, a wiki)
and it asks a language model to audit them, then writes a Markdown report listing:

  * contradictions between or within notes
  * unsourced factual claims
  * orphan notes (no links in or out)
  * concepts mentioned often but missing their own note
  * stale claims superseded by newer notes
  * suggested new cross-links
  * candidate new notes
  * the biggest gaps relative to the base's own themes
  * writing-style flags (optional, against a rules file)

Zero third-party dependencies — Python 3.9+ standard library only (urllib).
Needs an Anthropic API key in the ANTHROPIC_API_KEY environment variable.

Usage:
    export ANTHROPIC_API_KEY=sk-ant-...
    python kb_health_check.py ./my-vault
    python kb_health_check.py ./docs --output report.md --model claude-sonnet-4-6

Run the bundled demo:
    python kb_health_check.py examples/vault
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

DEFAULT_MODEL = "claude-sonnet-4-6"
DEFAULT_MAX_CHARS = 220_000  # ~55k input tokens; keeps a single run cheap
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"


def collect_notes(vault: Path, pattern: str, max_chars: int, report_name: str):
    """Gather Markdown notes under `vault`, concatenated and capped at max_chars.

    Files are read in sorted order so runs are deterministic. The output report
    is skipped so a previous run never audits itself.
    """
    blobs, total, count = [], 0, 0
    for path in sorted(vault.rglob(pattern)):
        if not path.is_file() or path.name == report_name:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel = path.relative_to(vault).as_posix()
        chunk = f"\n\n===== FILE: {rel} =====\n{text}"
        if total + len(chunk) > max_chars:
            chunk = chunk[: max(0, max_chars - total)] + "\n[...truncated...]"
            blobs.append(chunk)
            count += 1
            break
        blobs.append(chunk)
        total += len(chunk)
        count += 1
    return "".join(blobs), count


def build_prompt(corpus: str, writing_rules: str) -> str:
    rules_block = ""
    if writing_rules:
        rules_block = (
            "\n\nWRITING-STYLE RULES (flag any prose that violates these):\n"
            + writing_rules[:6000]
        )
    return (
        "You are a librarian auditing a Markdown knowledge base (an Obsidian vault, "
        "a docs/ tree, or a wiki). Audit the notes below and produce a tight, "
        "actionable health-check report in Markdown. Be specific and cite note "
        "filenames. Do not pad.\n\n"
        "Cover these sections (use ## headings):\n"
        "1. Contradictions - factual or claim inconsistencies between or within "
        "notes (prefix each with `> WARNING:`).\n"
        "2. Unsourced claims - specific factual claims stated without a source that "
        "should have one.\n"
        "3. Orphans - notes with no links (wiki-style [[links]] or relative Markdown "
        "links) pointing in or out.\n"
        "4. Missing pages - concepts mentioned repeatedly but lacking their own note.\n"
        "5. Stale or superseded - claims likely outdated or contradicted by newer notes.\n"
        "6. Suggested new links - meaningful connections between notes not yet drawn "
        "(name both notes and why).\n"
        "7. New-note candidates - 3-5 notes worth creating.\n"
        "8. Biggest knowledge gaps - the 3-5 largest gaps relative to the themes the "
        "knowledge base itself is about.\n"
        "9. Writing-style flags - prose that reads as machine-generated or promotional "
        "per the rules below (only if rules are provided).\n\n"
        "End with a one-line '## TL;DR' naming the top 3 things to fix.\n"
        f"{rules_block}\n\n"
        f"===== KNOWLEDGE-BASE NOTES =====\n{corpus}"
    )


def call_anthropic(prompt: str, model: str, max_tokens: int) -> str:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        sys.exit("ERROR: set ANTHROPIC_API_KEY in your environment.")
    body = json.dumps({
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }).encode("utf-8")
    req = urllib.request.Request(
        ANTHROPIC_URL,
        data=body,
        headers={
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        sys.exit(f"ERROR: Anthropic API returned HTTP {e.code}: {detail}")
    except urllib.error.URLError as e:
        sys.exit(f"ERROR: could not reach the Anthropic API: {e.reason}")
    return "".join(part.get("text", "") for part in data.get("content", []))


def find_writing_rules(arg_path: str | None) -> str:
    """Load a writing-rules file. Falls back to writing-rules.md next to this script."""
    candidates = []
    if arg_path:
        candidates.append(Path(arg_path))
    candidates.append(Path(__file__).parent / "writing-rules.md")
    for c in candidates:
        if c.exists():
            return c.read_text(encoding="utf-8", errors="replace")
    return ""


def parse_args(argv):
    p = argparse.ArgumentParser(
        description="LLM-powered health check for a Markdown knowledge base.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("vault", help="path to the folder of Markdown notes to audit")
    p.add_argument("-o", "--output", default="kb-health-report.md",
                   help="where to write the report")
    p.add_argument("-m", "--model", default=DEFAULT_MODEL,
                   help="Anthropic model id")
    p.add_argument("--glob", default="*.md",
                   help="filename pattern to match (recursive)")
    p.add_argument("--max-chars", type=int, default=DEFAULT_MAX_CHARS,
                   help="max characters of notes to send in one request")
    p.add_argument("--max-tokens", type=int, default=4096,
                   help="max tokens for the model's reply")
    p.add_argument("--writing-rules", default=None,
                   help="path to an anti-AI-slop writing-rules file "
                        "(defaults to the bundled writing-rules.md)")
    p.add_argument("--no-writing-rules", action="store_true",
                   help="skip the writing-style check")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    vault = Path(args.vault).expanduser()
    if not vault.is_dir():
        sys.exit(f"ERROR: not a directory: {vault}")

    report_path = Path(args.output).expanduser()
    corpus, n = collect_notes(vault, args.glob, args.max_chars, report_path.name)
    if not corpus.strip():
        sys.exit(f"No notes matched {args.glob!r} under {vault}.")

    writing_rules = "" if args.no_writing_rules else find_writing_rules(args.writing_rules)
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"[kb-health] auditing {n} notes ({len(corpus):,} chars) via {args.model}...")
    report_body = call_anthropic(build_prompt(corpus, writing_rules),
                                 args.model, args.max_tokens)

    header = (
        f"# Knowledge-Base Health Check - {stamp}\n\n"
        f"_Generated by kb_health_check.py over {n} notes in `{vault}`. "
        f"Review, then fold the fixes back into your notes._\n\n"
    )
    report_path.write_text(header + report_body.strip() + "\n", encoding="utf-8")
    print(f"[kb-health] wrote {report_path}")


if __name__ == "__main__":
    main()
