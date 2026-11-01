import copy
import json
from pathlib import Path
import subprocess
import sys
import unittest
from kis4 import assess


class ScorecardTests(unittest.TestCase):
    def setUp(self):
        self.record = json.loads(Path('examples/scorecard.json').read_text())

    def test_complete_evidence_yields_reviewable_score_not_approval(self):
        result = assess(self.record)
        self.assertEqual(result['composite'], 4)
        self.assertEqual(result['posture'], 'ready-for-review')
        self.assertFalse(result['authority_granted'])

    def test_failed_or_unknown_critical_gate_cannot_be_averaged_away(self):
        for status, posture in [('fail','revise'),('unknown','defer-pending-evidence')]:
            record = copy.deepcopy(self.record)
            record['gates'][0]['status'] = status
            result = assess(record)
            self.assertEqual(result['posture'], posture)
            self.assertIsNone(result['composite'])

    def test_claimed_pass_without_evidence_is_unknown(self):
        self.record['gates'][0]['evidence'] = ''
        self.assertEqual(assess(self.record)['unknown_gates'], ['authority'])
        self.assertIsNone(assess(self.record)['composite'])

    def test_missing_trace_or_score_never_becomes_neutral(self):
        for key in ('principle','obligation','control','test','evidence','rationale','maturity','confidence','score'):
            record = copy.deepcopy(self.record)
            del record['dimensions']['secure'][0][key]
            result = assess(record)
            self.assertIsNone(result['composite'])
            self.assertIsNone(result['scores']['secure'])

    def test_caller_maturity_cap_is_enforced(self):
        self.record['dimensions']['secure'][0]['maturity_cap'] = 3
        self.assertEqual(assess(self.record)['gaps'], ['secure-1:maturity-cap-exceeded'])
        self.assertIsNone(assess(self.record)['composite'])

    def test_weights_are_explicit_positive_and_finite(self):
        for value in (0, -1, True, float('nan'), float('inf'), 10**1000, '0.4', .7):
            record = copy.deepcopy(self.record)
            record['weights']['secure'] = value
            with self.assertRaises(ValueError):
                assess(record)

    def test_unique_criteria_and_all_dimensions_required(self):
        self.record['dimensions']['simple'][0]['id'] = 'secure-1'
        with self.assertRaises(ValueError):
            assess(self.record)
        self.setUp()
        del self.record['dimensions']['secure']
        with self.assertRaises(ValueError):
            assess(self.record)

    def test_weighted_arithmetic_and_threshold(self):
        self.record['dimensions']['secure'][0]['score'] = 2
        self.assertEqual(assess(self.record)['composite'], 3.2)
        self.assertEqual(assess(self.record)['posture'], 'revise')

    def test_strong_dimensions_do_not_compensate_for_failed_principle(self):
        for criteria in self.record['dimensions'].values():
            criteria[0].update(score=5, maturity_cap=5)
        self.record['dimensions']['secure'][0]['score'] = 3
        self.assertEqual(assess(self.record)['composite'], 4.2)
        self.assertEqual(assess(self.record)['posture'], 'revise')

    def test_cli_end_to_end_and_rejection(self):
        result = subprocess.run([sys.executable,'-m','kis4'],input=json.dumps(self.record).encode(),capture_output=True)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)['composite'], 4)
        for data in (b'{}', b'{"schema":1,"schema":1}', b'{"schema":NaN}', b'x'*100001, b'\xff'):
            result = subprocess.run([sys.executable,'-m','kis4'],input=data,capture_output=True)
            self.assertEqual(result.returncode, 2)


if __name__ == '__main__':
    unittest.main()
