"""Offline tests for the trajectory suite.

The extractor is stubbed with the expected records of each fixture, so these
tests check the tool wiring and trajectory scoring only. They do not measure
extraction quality, and they do not need Ollama or a browser.
"""
import json
import sys
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

    def test_run_live_writes_a_scored_report(self):
        # Uses the gold model through the same report path that a live run would use.
        output = ROOT / 'runs' / 'replay-test' / 'report.json'
        with mock.patch.object(replay_suite, 'ollama_agent_model',
                               side_effect=lambda name, case: replay_suite.gold_model(case)):
            report = replay_suite.run_live('gold-model', output, cases=self.cases[:2])
        self.assertEqual(report['summary']['exact'], 2)
        self.assertEqual(json.loads(output.read_text(encoding='utf-8'))['summary']['cases'], 2)


if __name__ == '__main__':
    unittest.main()
