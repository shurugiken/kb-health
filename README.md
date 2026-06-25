# kb-health

An LLM-powered health check for a Markdown knowledge base. Point it at a folder
of notes and it returns a report of contradictions, orphans, stale claims,
missing pages, and weak writing.

Works on any folder of Markdown: an [Obsidian](https://obsidian.md) vault, a
project's `docs/` tree, or a wiki.

## What it does

`kb_health_check.py` reads every `.md` file under a folder, sends them to an
Anthropic model in one request, and writes a Markdown report covering:

- Contradictions between or within notes
- Unsourced factual claims
- Orphan notes with no links in or out
- Concepts mentioned often but missing their own note
- Stale claims superseded by newer notes
- Suggested new cross-links and candidate new notes
- The biggest gaps relative to the base's own themes
- Writing-style flags against an anti-AI-slop rules file (optional)

## Install

No third-party dependencies. Python 3.9+ standard library only.

```bash
git clone https://github.com/shurugiken/kb-health
cd kb-health
export ANTHROPIC_API_KEY=sk-ant-...   # Windows: set ANTHROPIC_API_KEY=...
```

## Usage

```bash
python kb_health_check.py ./my-vault
python kb_health_check.py ./docs --output report.md --model claude-sonnet-4-6
python kb_health_check.py ./notes --no-writing-rules
```

Try it on the bundled demo vault (it has a planted contradiction, an orphan, and
a missing-page concept):

```bash
python kb_health_check.py examples/vault
```

See [examples/sample-report.md](examples/sample-report.md) for the report that
command produces.

### Options

| Flag | Default | Meaning |
|---|---|---|
| `vault` | — | folder of Markdown notes to audit (required) |
| `-o`, `--output` | `kb-health-report.md` | where to write the report |
| `-m`, `--model` | `claude-sonnet-4-6` | Anthropic model id |
| `--glob` | `*.md` | filename pattern to match (recursive) |
| `--max-chars` | `220000` | max characters of notes sent in one request |
| `--max-tokens` | `4096` | max tokens for the model's reply |
| `--writing-rules` | bundled `writing-rules.md` | path to your own style-rules file |
| `--no-writing-rules` | off | skip the writing-style check |

## How it works

1. Glob the vault for `*.md`, in sorted order, skipping the output report.
2. Concatenate the notes into one prompt, capped at `--max-chars`.
3. Make one Anthropic API call (stdlib `urllib`, no SDK).
4. Write the model's report to disk.

A run over roughly 40 notes (~220k characters) costs about $0.30–0.50 on Sonnet.
For a larger base, lower `--max-chars` and run it over subfolders, or raise it on
a model with a bigger context window.

## Writing-style check

The bundled `writing-rules.md` is an anti-AI-slop style guide: a set of banned
patterns (puffery, significance inflation, "not just X but Y", em-dash overuse,
vague attribution) with rewrite rules. When present, the linter flags note prose
that violates it. Pass `--no-writing-rules` to skip it, or `--writing-rules
PATH` to supply your own.

## License

MIT — see [LICENSE](LICENSE). `writing-rules.md` is adapted from Wikipedia's
"Signs of AI writing" and WikiProject AI Cleanup pages, used under
[CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).
