import copy
import json
from pathlib import Path
import subprocess
import sys
import unittest

import kis4
from kis4.compare import compare


def comparison():
    card = json.loads(Path('examples/scorecard.json').read_text())
    card['threshold'] = 3
    card['minimums'] = dict.fromkeys(card['dimensions'], 1)
    for criteria in card['dimensions'].values():
        criteria[0]['maturity_cap'] = 5
    return {'schema': 1, 'as_of': '2026-11-01T12:00:00+00:00', 'max_age_hours': 36,
            'options': [{'id': name, 'evidence_observed_at': '2026-11-01T10:00:00+00:00',
                         'evidence_valid_until': '2026-11-02T10:00:00+00:00',
                         'scorecard': copy.deepcopy(card)} for name in ('current', 'candidate')]}


class ComparisonTests(unittest.TestCase):
    def test_ties_remain_ties_and_are_not_arbitrarily_selected(self):
        result = compare(comparison())
        self.assertEqual(result['baseline']['best_options'], ['candidate', 'current'])
        self.assertEqual(result['baseline']['ranking'][0]['options'], ['candidate', 'current'])
        self.assertEqual(len(result['sensitivity']), 8)
        self.assertFalse(result['rank_instability'])
        self.assertFalse(result['authority_granted'])
        self.assertFalse(result['evidence_independently_verified'])

    def test_stronger_option_wins_when_all_constraints_pass(self):
        record = comparison()
        for criteria in record['options'][1]['scorecard']['dimensions'].values():
            criteria[0]['score'] = 5
        result = compare(record)
        self.assertEqual(result['baseline']['best_options'], ['candidate'])
        self.assertEqual(result['baseline']['ranking'][0]['composite'], 5)
        self.assertEqual(result['posture'], 'ready-for-review')

    def test_weight_sensitivity_reveals_rank_reversal(self):
        record = comparison()
        for option in record['options']:
            option['scorecard']['weights'] = dict.fromkeys(option['scorecard']['weights'], .25)
        a, b = [o['scorecard'] for o in record['options']]
        for d, score in zip(('simple', 'secure', 'sustainable', 'scalable'), (5, 3, 4, 4)):
            a['dimensions'][d][0]['score'] = score
        b['dimensions']['scalable'][0]['score'] = 4.1
        result = compare(record)
        self.assertEqual(result['baseline']['best_options'], ['candidate'])
        raised_simple = next(s for s in result['sensitivity'] if s['dimension'] == 'simple' and s['factor'] == 1.2)
        self.assertEqual(raised_simple['best_options'], ['current'])
        self.assertTrue(result['rank_instability'])
        self.assertEqual(result['posture'], 'review-sensitivity')

    def test_incomplete_or_failed_gate_is_excluded_in_all_scenarios(self):
        for status in ('fail', 'unknown'):
            with self.subTest(status=status):
                record = comparison()
                record['options'][1]['scorecard']['gates'][0]['status'] = status
                result = compare(record)
                self.assertIsNone(result['assessments'][1]['assessment']['composite'])
                self.assertEqual(result['baseline']['best_options'], ['current'])
                self.assertTrue(all(s['best_options'] == ['current'] for s in result['sensitivity']))
                self.assertEqual(result['posture'], 'incomplete-comparison')

    def test_absent_material_evidence_is_not_scored_zero(self):
        record = comparison()
        del record['options'][1]['scorecard']['dimensions']['secure'][0]['evidence']
        result = compare(record)
        self.assertIsNone(result['assessments'][1]['assessment']['scores']['secure'])
        self.assertEqual(result['baseline']['best_options'], ['current'])

    def test_freshness_is_explicit_and_boundary_sensitive(self):
        changes = [('evidence_observed_at', None),
                   ('evidence_observed_at', '2026-10-30T23:59:59+00:00'),
                   ('evidence_observed_at', '2026-11-01T12:00:01+00:00'),
                   ('evidence_observed_at', '2026-11-01T10:00:00'),
                   ('evidence_valid_until', '2026-11-01T12:00:00+00:00')]
        for key, value in changes:
            with self.subTest(key=key, value=value):
                record = comparison()
                record['options'][1][key] = value
                result = compare(record)
                self.assertEqual(result['baseline']['best_options'], ['current'])
                self.assertTrue(result['assessments'][1]['exclusions'])
        record = comparison()
        record['options'][1]['evidence_observed_at'] = '2026-10-31T00:00:00+00:00'
        self.assertEqual(len(compare(record)['baseline']['best_options']), 2)

    def test_invalid_interval_is_excluded(self):
        record = comparison()
        record['options'][1]['evidence_valid_until'] = '2026-11-01T09:00:00+00:00'
        self.assertTrue(compare(record)['assessments'][1]['exclusions'])

    def test_frozen_rubric_rejects_same_id_with_changed_rules(self):
        changes = [('threshold', 2), ('owner', 'other-owner'),
                   ('weights', dict(simple=.1, secure=.5, sustainable=.2, scalable=.2)),
                   ('minimums', dict(simple=2, secure=1, sustainable=1, scalable=1))]
        for key, value in changes:
            record = comparison()
            record['options'][1]['scorecard'][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                compare(record)
        for key, value in [('principle', 'different'), ('obligation', 'different'),
                           ('maturity_cap', 4), ('anchors', {'1': 'weak', '5': 'strong'})]:
            record = comparison()
            record['options'][1]['scorecard']['dimensions']['secure'][0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                compare(record)

    def test_control_and_test_evidence_can_differ_between_implementations(self):
        record = comparison()
        record['options'][1]['scorecard']['dimensions']['secure'][0].update(
            control='different implementation', test='different test receipt', evidence='candidate evidence')
        self.assertEqual(compare(record)['posture'], 'ready-for-review')

    def test_critical_gate_inventory_cannot_change(self):
        record = comparison()
        record['options'][1]['scorecard']['gates'][0]['id'] = 'other'
        with self.assertRaises(ValueError):
            compare(record)

    def test_sensitivity_never_relaxes_dimension_minimums(self):
        record = comparison()
        for option in record['options']:
            option['scorecard']['minimums']['secure'] = 4
        record['options'][1]['scorecard']['dimensions']['secure'][0]['score'] = 3
        result = compare(record)
        self.assertTrue(all(s['best_options'] == ['current'] for s in result['sensitivity']))

    def test_rounded_dimension_cannot_pass_a_strict_floor(self):
        record = comparison()
        for option in record['options']:
            option['scorecard']['minimums']['secure'] = 4
        record['options'][1]['scorecard']['dimensions']['secure'][0]['score'] = 3.9999999
        result = compare(record)
        self.assertIn('dimension-minimum-not-met', result['assessments'][1]['exclusions'])
        self.assertEqual(result['baseline']['best_options'], ['current'])
        self.assertTrue(all(s['best_options'] == ['current'] for s in result['sensitivity']))

    def test_rounded_composite_cannot_pass_a_strict_threshold(self):
        record = comparison()
        for option in record['options']:
            option['scorecard']['threshold'] = 4
        for criteria in record['options'][1]['scorecard']['dimensions'].values():
            criteria[0]['score'] = 3.9999999
        result = compare(record)
        self.assertIn('below-composite-threshold', result['assessments'][1]['exclusions'])
        self.assertEqual(result['baseline']['best_options'], ['current'])
        self.assertTrue(all(s['best_options'] == ['current'] for s in result['sensitivity']))

    def test_all_excluded_returns_no_winner(self):
        record = comparison()
        for option in record['options']:
            option['scorecard']['gates'][0]['status'] = 'unknown'
        result = compare(record)
        self.assertEqual(result['baseline']['best_options'], [])
        self.assertEqual(result['baseline']['ranking'], [])

    def test_option_identifiers_and_limits_are_bounded(self):
        for mutate in (lambda r: r['options'][1].update(id='current'),
                       lambda r: r.update(options=r['options'][:1]),
                       lambda r: r.update(max_age_hours=True),
                       lambda r: r.update(max_age_hours=8761),
                       lambda r: r.update(as_of='2026-11-01T12:00:00'),
                       lambda r: r.update(schema=True)):
            record = comparison()
            mutate(record)
            with self.assertRaises(ValueError):
                compare(record)

    def test_comparison_does_not_mutate_caller_record(self):
        record = comparison()
        before = copy.deepcopy(record)
        compare(record)
        self.assertEqual(before, record)

    def test_cli_valid_input_and_bounded_errors(self):
        isolated = ['-I'] if Path(kis4.__file__).resolve().is_relative_to(Path(sys.prefix).resolve()) else []
        command = [sys.executable, *isolated, '-m', 'kis4.compare']
        result = subprocess.run(command, input=json.dumps(comparison()).encode(), capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['baseline']['best_options'], ['candidate', 'current'])
        overflow = json.dumps(comparison()).replace('"score": 4', '"score": 1e999', 1).encode()
        for data in (b'{}', b'{"schema":1,"schema":1}', b'{"schema":NaN}', b'x'*100001, b'\xff', overflow,
                     overflow.replace(b'1e999', b'-1e999')):
            result = subprocess.run(command, input=data, capture_output=True)
            self.assertEqual(result.returncode, 2)
            self.assertNotIn(b'Traceback', result.stderr)


if __name__ == '__main__':
    unittest.main()
