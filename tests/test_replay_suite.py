"""Offline tests for the trajectory suite.

The extractor is stubbed with the expected records of each fixture, so these
tests check the tool wiring and trajectory scoring only. They do not measure
extraction quality, and they do not need Ollama or a browser.
"""
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'evaluation'))
sys.path.insert(0, str(ROOT))

import replay_suite  # noqa: E402
from trajectory_replay import Replayer, run_agent, score  # noqa: E402


class _StubResult:
    def __init__(self, records):
        self.status = 'success' if records else 'empty'
        self.records = [{'values': dict(row)} for row in records]


class ReplaySuiteTests(unittest.TestCase):
    def setUp(self):
        self.cases = replay_suite.load_cases()
        expected_by_task = {case['task']: case['expected'] for case in self.cases}

        def fake_extract(chunks, description, fields, *, model_factory=None, progress=None, sleep=None):
            return _StubResult(expected_by_task[description])

        patcher = mock.patch.object(replay_suite, 'extract_structured', side_effect=fake_extract)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_every_fixture_loads(self):
        self.assertEqual(len(self.cases), 16)
        for case in self.cases:
            self.assertTrue(case['html'])
            self.assertTrue(case['task'])

    def test_gold_trajectory_is_capture_blocks_extract_for_every_fixture(self):
        for case in self.cases:
            with self.subTest(case=case['id']):
                result = replay_suite.run_case(case, replay_suite.gold_model(case))
                self.assertEqual(result.stopped, 'final')
                self.assertEqual([c.name for c in result.trajectory], ['capture', 'blocks', 'extract'])
                self.assertTrue(all(c.error is None for c in result.trajectory))

    def test_replayed_gold_trajectory_matches_exactly(self):
        for case in self.cases:
            with self.subTest(case=case['id']):
                gold = replay_suite.gold_trajectory(case)
                replayer = Replayer(gold)
                replayed = run_agent(replay_suite.gold_model(case), case['task'], replayer.tools())
                replayer.assert_exhausted()
                self.assertTrue(score(replayed.trajectory, gold).exact)

    def test_wrong_fields_are_not_an_exact_match(self):
        case = self.cases[0]
        gold = replay_suite.gold_trajectory(case)

        def wrong_fields(history):
            results = [m for m in history if m['role'] == 'tool']
            if len(results) == 2:
                return {'tool': 'extract', 'arguments': {'page_id': case['id'], 'fields': 'name'}}
            return replay_suite.gold_model(case)(history)

        live = run_agent(wrong_fields, case['task'], replay_suite.make_tools([case]))
        s = score(live.trajectory, gold)
        self.assertFalse(s.exact)
        self.assertEqual(s.matched, 2)

    def test_unknown_page_is_recorded_as_a_tool_error(self):
        case = self.cases[0]
        tools = replay_suite.make_tools([case])
        plan = [{'tool': 'capture', 'arguments': {'page_id': 'missing'}}, {'final': 'stop'}]
        iterator = iter(plan)
        result = run_agent(lambda history: next(iterator), case['task'], tools)
        self.assertEqual(result.trajectory[0].error, 'unknown page: missing')

    def test_cli_help_prints_usage(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            self.assertEqual(replay_suite.main(['--help']), 0)
        self.assertIn('--model', stdout.getvalue())

    def test_cli_rejects_malformed_options_without_crashing(self):
        for argv in [
            [], ['live', '--model', 'x', '--output'],
            ['live', '--output', 'out.json', '--model'],
            ['live', '--model', 'x', '--out', 'y'],
            ['live', '--model', 'x', '--output', 'y', 'extra'],
            ['live', '--model', '--output', 'x', 'y'],
        ]:
            with self.subTest(argv=argv), contextlib.redirect_stderr(io.StringIO()) as stderr:
                self.assertEqual(replay_suite.main(argv), 2)
            self.assertIn('usage:', stderr.getvalue())

    def test_cli_refuses_existing_output(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'report.json'
            output.write_text('keep', encoding='utf-8')
            with contextlib.redirect_stderr(io.StringIO()) as stderr:
                self.assertEqual(replay_suite.main(['live', '--model', 'm', '--output', str(output)]), 2)
            self.assertIn('Refusing to overwrite', stderr.getvalue())
            self.assertEqual(output.read_text(encoding='utf-8'), 'keep')

    def test_cli_runs_with_mocked_live_report(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'out.json'
            stdout = io.StringIO()
            with mock.patch.object(replay_suite, 'run_live', return_value={'summary': {'cases': 2, 'exact': 2}}), contextlib.redirect_stdout(stdout):
                self.assertEqual(replay_suite.main(['live', '--model', 'm', '--output', str(output)]), 0)
            self.assertEqual(json.loads(stdout.getvalue()), {'cases': 2, 'exact': 2})

    def test_run_live_writes_a_scored_report(self):
        # Uses the gold model through the same report path that a live run would use.
        output = ROOT / 'runs' / 'replay-test' / 'report.json'
        with mock.patch.object(replay_suite, 'ollama_agent_model',
                               side_effect=lambda name, case: replay_suite.gold_model(case)):
            report = replay_suite.run_live('gold-model', output, cases=self.cases[:2])
        self.assertEqual(report['summary']['exact'], 2)
        self.assertEqual(report['fixture_manifest_sha256'],
                         replay_suite.sha(replay_suite.FIXTURE_DIR / 'manifest.json'))
        expected_cases_hash = replay_suite.cases_digest(self.cases[:2])
        self.assertEqual(report['fixture_cases_sha256'], expected_cases_hash)
        changed = json.loads(json.dumps(self.cases[:2]))
        changed[0]['html'] += ' '
        self.assertNotEqual(replay_suite.cases_digest(changed), expected_cases_hash)
        self.assertEqual(report['chunk_budget'], replay_suite.chunk_budget())
        self.assertEqual(report['code_hashes']['evaluation/replay_suite.py'],
                         replay_suite.sha(replay_suite.ROOT / 'evaluation/replay_suite.py'))
        self.assertTrue(report['limitations'])
        persisted = json.loads(output.read_text(encoding='utf-8'))
        self.assertEqual(persisted['summary']['cases'], 2)
        self.assertEqual(persisted['fixture_manifest_sha256'], report['fixture_manifest_sha256'])


if __name__ == '__main__':
    unittest.main()
