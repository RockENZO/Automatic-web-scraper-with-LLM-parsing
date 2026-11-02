"""Trajectory suite for the structured extraction workflow.

The test agent has three tools, each returning a string:

  capture(page_id)           -> the fixture HTML for that page
  blocks(page_id)            -> JSON list of source blocks for that page
  extract(page_id, fields)   -> JSON result of structured extraction

The task text for each page comes from its fixture, so the model only chooses
the page and the fields. The gold trajectory is capture -> blocks -> extract.

Offline runs (tests and CI) use a scripted gold model and a stubbed extractor.
Live runs need a local Ollama model and are started from the command line:

  python evaluation/replay_suite.py live --model MODEL --output runs/replay/MODEL.json
"""

from __future__ import annotations

import hashlib
import json
import platform
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from trajectory_replay import ToolCall, run_agent, score  # noqa: E402
from trajectory_replay.agent import RunResult  # noqa: E402

import config  # noqa: E402
from ollama_client import OllamaClient  # noqa: E402
from structured_content import Block, chunk_blocks, extract_blocks  # noqa: E402
from structured_parse import extract_structured  # noqa: E402

FIXTURE_DIR = ROOT / 'evaluation' / 'fixtures'
PROVENANCE_FILES = [
    'config.py', 'ollama_client.py', 'structured_content.py',
    'structured_parse.py', 'evaluation/replay_suite.py',
]
PROTOCOL = ('Scripted gold trajectory (capture -> blocks -> extract) versus a live agent '
            'on the 16 synthetic regression fixtures; one run without result-driven tuning. '
            'Call matching ignores tool results and does not measure extraction accuracy.')
LIMITATIONS = [
    '16 synthetic hand-specified fixtures; not a representative sample of live websites.',
    'Trajectory matching ignores tool results; a correct sequence can still contain wrong extracted values.',
    'The agent model is not validated for tool-calling quality or latency; extraction calls use the configured primary/fallback models.',
    'Live runs need a local Ollama endpoint; no live-browser fetch, pagination or CAPTCHA handling is measured.',
]


def sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def cases_digest(cases: list[dict[str, Any]]) -> str:
    """Hash the actual fixture payloads, not just their manifest IDs."""
    payload = json.dumps(cases, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()


def capture_provenance(cases: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'protocol': PROTOCOL,
        'python': platform.python_version(),
        'platform': platform.platform(),
        'chunk_budget': chunk_budget(),
        'fixture_manifest_sha256': sha(FIXTURE_DIR / 'manifest.json'),
        'fixture_cases_sha256': cases_digest(cases),
        'requirements_sha256': sha(ROOT / 'requirements-benchmark.txt'),
        'code_hashes': {name: sha(ROOT / name) for name in PROVENANCE_FILES},
        'scoring': {'trajectory': 'longest common subsequence on tool name and arguments; results ignored',
                    'exact': 'same length and every call matches in order'},
        'limitations': LIMITATIONS,
    }


def load_cases(fixture_dir: Path = FIXTURE_DIR) -> list[dict[str, Any]]:
    """Load the synthetic regression fixtures, excluding the manifest."""
    manifest = json.loads((fixture_dir / 'manifest.json').read_text(encoding='utf-8'))
    cases = []
    for case_id in manifest['case_ids']:
        case = json.loads((fixture_dir / f'{case_id}.json').read_text(encoding='utf-8'))
        cases.append(case)
    return cases


def chunk_budget(fixture_dir: Path = FIXTURE_DIR) -> int:
    return int(json.loads((fixture_dir / 'manifest.json').read_text(encoding='utf-8'))['chunk_budget'])


def parse_fields(text: str) -> list[str]:
    """Accept 'name,price' or 'name, price' and return a list."""
    return [part.strip() for part in text.split(',') if part.strip()]


@dataclass
class _Result:
    status: str
    records: list


def make_tools(cases: list[dict[str, Any]], model_factory=None, budget: int = 1400) -> dict[str, Any]:
    """Build the three tools over a fixed set of fixture pages."""
    pages = {case['id']: case for case in cases}

    def case_for(page_id: str) -> dict[str, Any]:
        if page_id not in pages:
            raise ValueError(f'unknown page: {page_id}')
        return pages[page_id]

    def capture(page_id: str) -> str:
        return case_for(page_id)['html']

    def blocks(page_id: str) -> str:
        found = extract_blocks(case_for(page_id)['html'])
        return json.dumps([{'id': b.id, 'text': b.text} for b in found], ensure_ascii=False)

    def extract(page_id: str, fields: str) -> str:
        case = case_for(page_id)
        source = [Block(**item) for item in json.loads(blocks(page_id))]
        result = extract_structured(
            chunk_blocks(source, budget),
            case['task'],
            parse_fields(fields),
            model_factory=model_factory,
            sleep=lambda seconds: None,
        )
        return json.dumps(
            {'status': result.status, 'records': [row['values'] for row in result.records]},
            sort_keys=True,
            ensure_ascii=False,
        )

    return {'capture': capture, 'blocks': blocks, 'extract': extract}


def gold_model(case: dict[str, Any]):
    """Scripted agent for the gold trajectory: capture, blocks, extract, then answer."""
    page_id = case['id']
    fields = ','.join(case['fields'])

    def model(history: list[dict[str, Any]]) -> dict[str, Any]:
        tool_results = [m for m in history if m['role'] == 'tool']
        if not tool_results:
            return {'tool': 'capture', 'arguments': {'page_id': page_id}}
        if len(tool_results) == 1:
            return {'tool': 'blocks', 'arguments': {'page_id': page_id}}
        if len(tool_results) == 2:
            return {'tool': 'extract', 'arguments': {'page_id': page_id, 'fields': fields}}
        return {'final': tool_results[-1]['content']}

    return model


AGENT_INSTRUCTIONS = (
    'You are a data extraction agent. Tools: capture(page_id) returns the page HTML; '
    'blocks(page_id) returns its source blocks; extract(page_id, fields) returns records '
    'for comma-separated fields. Call them in order, then answer with {"final": "..."}. '
    'Reply with JSON only: {"tool": NAME, "arguments": {...}} or {"final": TEXT}.'
)

ACTION_SCHEMA = {
    'type': 'object',
    'properties': {
        'tool': {'type': 'string', 'enum': ['capture', 'blocks', 'extract']},
        'arguments': {'type': 'object'},
        'final': {'type': 'string'},
    },
}


def _agent_prompt(task: str, page_id: str, history: list[dict[str, Any]]) -> str:
    lines = [AGENT_INSTRUCTIONS, f'Task: {task}', f'Page id: {page_id}']
    for message in history:
        if message['role'] == 'tool':
            content = message['content']
            if len(content) > 4000:
                content = content[:4000] + '...[truncated]'
            lines.append(f"Tool {message['name']} returned: {content}")
    lines.append('Next action JSON:')
    return '\n'.join(lines)


def ollama_agent_model(model_name: str, case: dict[str, Any]):
    """Agent that asks a local Ollama model for each next action."""
    client = OllamaClient(model_name)

    def model(history: list[dict[str, Any]]) -> dict[str, Any]:
        text = client.invoke(_agent_prompt(case['task'], case['id'], history), ACTION_SCHEMA)
        action = json.loads(text)
        if not isinstance(action, dict):
            raise ValueError('agent action must be a JSON object')
        return action

    return model


def run_case(case: dict[str, Any], agent, model_factory=None) -> RunResult:
    tools = make_tools([case], model_factory=model_factory, budget=chunk_budget())
    return run_agent(agent, case['task'], tools, max_steps=6)


def gold_trajectory(case: dict[str, Any], model_factory=None) -> list[ToolCall]:
    return run_case(case, gold_model(case), model_factory=model_factory).trajectory


def run_live(model_name: str, output: Path, cases: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Run the live agent on every fixture and score it against the gold trajectory."""
    cases = cases if cases is not None else load_cases()
    report: dict[str, Any] = {'model': model_name, 'config_model': config.OLLAMA_MODEL,
                              **capture_provenance(cases), 'cases': []}
    for case in cases:
        gold = gold_trajectory(case)
        live = run_case(case, ollama_agent_model(model_name, case))
        s = score(live.trajectory, gold)
        report['cases'].append({
            'id': case['id'],
            'stopped': live.stopped,
            'matched': s.matched,
            'predicted_len': s.predicted_len,
            'gold_len': s.gold_len,
            'exact': s.exact,
            'f1': round(s.f1, 5),
            'calls': [{'name': c.name, 'arguments': c.arguments, 'error': c.error} for c in live.trajectory],
        })
    exact = sum(1 for row in report['cases'] if row['exact'])
    report['summary'] = {'cases': len(report['cases']), 'exact': exact,
                         'mean_f1': round(sum(r['f1'] for r in report['cases']) / max(1, len(report['cases'])), 5)}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    return report


USAGE = 'usage: replay_suite.py live --model MODEL --output PATH'


def _live_options(argv: list[str]) -> tuple[str, Path] | None:
    """Parse exactly `live --model MODEL --output PATH` with values present once.

    Reject anything else instead of raising IndexError on a trailing flag.
    """
    if not argv or argv[0] != 'live' or len(argv) != 5:
        return None
    flags = argv[1::2]
    values = argv[2::2]
    if sorted(flags) != ['--model', '--output']:
        return None
    pairs = dict(zip(flags, values))
    model, output = pairs['--model'].strip(), pairs['--output'].strip()
    if not model or not output or model.startswith('--') or output.startswith('--'):
        return None
    return model, Path(output)


def main(argv: list[str]) -> int:
    if argv in (['--help'], ['-h']):
        print(USAGE)
        return 0
    parsed = _live_options(argv)
    if parsed is None:
        print(USAGE, file=sys.stderr)
        return 2
    model, output = parsed
    if output.exists():
        print(f'Refusing to overwrite existing report: {output}', file=sys.stderr)
        return 2
    summary = run_live(model, output)['summary']
    print(json.dumps(summary))
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
