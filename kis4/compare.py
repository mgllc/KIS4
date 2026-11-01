"""Compare evidence-backed options under one frozen rubric, without acting."""
from datetime import datetime
import hashlib
import json
import math
import sys

from . import DIMENSIONS, _composite, _dimension_total, assess
from .__main__ import finite_float, unique


def _instant(value):
    if not isinstance(value, str):
        raise ValueError('Timezone-aware ISO8601 timestamp required')
    instant = datetime.fromisoformat(value)
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ValueError('Timezone-aware ISO8601 timestamp required')
    return instant


def _rubric(card):
    """Bind scoring rules, not the option's implementation or result evidence."""
    return {
        key: card[key] for key in ('rubric_id', 'decision', 'owner', 'weights',
                                   'weights_rationale', 'threshold', 'minimums')
    } | {
        'gates': sorted(gate['id'] for gate in card['gates']),
        'criteria': {
            dimension: sorted([
                {key: criterion.get(key) for key in
                 ('id', 'weight', 'maturity_cap', 'principle', 'obligation', 'anchors')}
                for criterion in card['dimensions'][dimension]
            ], key=lambda criterion: criterion['id'])
            for dimension in DIMENSIONS
        },
    }


def _freshness(option, as_of, max_age_hours):
    try:
        observed = _instant(option.get('evidence_observed_at'))
        expires = _instant(option.get('evidence_valid_until'))
    except (ValueError, TypeError):
        return ['evidence-time-missing-or-invalid']
    reasons = []
    if observed >= expires:
        reasons.append('evidence-invalid-interval')
    if observed > as_of:
        reasons.append('evidence-from-future')
    if (as_of - observed).total_seconds() > max_age_hours * 3600:
        reasons.append('evidence-stale')
    if as_of >= expires:
        reasons.append('evidence-expired')
    return reasons


def _rank(options, weights, threshold):
    eligible, excluded = [], []
    for option in options:
        reasons = list(option['fixed_exclusions'])
        composite = None
        scores = option['raw_scores']
        if not reasons:
            raw_composite = _composite(scores, weights)
            composite = round(raw_composite, 6)
            if raw_composite < threshold:
                reasons.append('below-composite-threshold')
        if reasons:
            excluded.append({'id': option['id'], 'reasons': reasons})
        else:
            eligible.append({'id': option['id'], 'composite': composite})
    eligible.sort(key=lambda option: (-option['composite'], option['id']))
    ranking = []
    for option in eligible:
        if ranking and math.isclose(option['composite'], ranking[-1]['composite'], rel_tol=0, abs_tol=1e-6):
            ranking[-1]['options'].append(option['id'])
            ranking[-1]['options'].sort()
        else:
            ranking.append({'rank': sum(len(group['options']) for group in ranking) + 1,
                            'composite': option['composite'], 'options': [option['id']]})
    return {'ranking': ranking, 'best_options': ranking[0]['options'] if ranking else [],
            'excluded': excluded}


def compare(record):
    """Return analytical rankings and uncertainty; never approval or execution.

    Timestamps and evidence references are supplied assertions. The caller must
    acquire them from authorized sources; this function does not verify truth.
    """
    if not isinstance(record, dict) or type(record.get('schema')) is not int or record['schema'] != 1:
        raise ValueError('Expected a schema 1 comparison object')
    as_of = _instant(record.get('as_of'))
    age = record.get('max_age_hours')
    if type(age) is not int or not 1 <= age <= 8760:
        raise ValueError('max_age_hours must be an integer from 1 to 8760')
    incoming = record.get('options')
    if not isinstance(incoming, list) or not 2 <= len(incoming) <= 20:
        raise ValueError('Two to twenty options required')
    seen, options, rubric = set(), [], None
    for option in incoming:
        if not isinstance(option, dict):
            raise ValueError('Invalid option')
        identifier = option.get('id')
        if not isinstance(identifier, str) or identifier != identifier.strip() or not 1 <= len(identifier) <= 128 or identifier in seen:
            raise ValueError('Unique nonblank option identifiers required')
        seen.add(identifier)
        card = option.get('scorecard')
        assessment = assess(card)
        candidate_rubric = _rubric(card)
        # JSON checks optional anchors for serialization and finite values too.
        encoded = json.dumps(candidate_rubric, sort_keys=True, separators=(',', ':'), allow_nan=False)
        if rubric is None:
            rubric = candidate_rubric
            frozen = encoded
        elif encoded != frozen:
            raise ValueError('Options must use the same frozen rubric and scoring rules')
        reasons = _freshness(option, as_of, age)
        if assessment['failed_gates']:
            reasons.append('failed-critical-gate')
        if assessment['unknown_gates']:
            reasons.append('unknown-critical-gate')
        if assessment['gaps']:
            reasons.append('incomplete-material-evidence')
        raw_scores = {d: _dimension_total(card['dimensions'][d])
                      if assessment['scores'][d] is not None else None for d in DIMENSIONS}
        if any(raw_scores[d] is not None and raw_scores[d] < card['minimums'][d] for d in DIMENSIONS):
            reasons.append('dimension-minimum-not-met')
        options.append({'id': identifier, 'assessment': assessment,
                        'raw_scores': raw_scores, 'fixed_exclusions': reasons})
    baseline = _rank(options, rubric['weights'], rubric['threshold'])
    scenarios = []
    baseline_order = [group['options'] for group in baseline['ranking']]
    for dimension in DIMENSIONS:
        for factor in (.8, 1.2):
            weights = dict(rubric['weights'])
            weights[dimension] *= factor
            total = sum(weights.values())
            weights = {key: value / total for key, value in weights.items()}
            result = _rank(options, weights, rubric['threshold'])
            scenarios.append({'dimension': dimension, 'factor': factor,
                              'weights': weights, **result,
                              'winner_changed': result['best_options'] != baseline['best_options'],
                              'ranking_changed': [g['options'] for g in result['ranking']] != baseline_order})
    instability = any(scenario['ranking_changed'] for scenario in scenarios)
    posture = ('review-sensitivity' if instability else
               'incomplete-comparison' if baseline['excluded'] else 'ready-for-review')
    excluded_by_id = {item['id']: item['reasons'] for item in baseline['excluded']}
    return {'schema': 1, 'framework': 'KIS4', 'as_of': record['as_of'],
            'rubric_id': rubric['rubric_id'],
            'rubric_sha256': hashlib.sha256(frozen.encode()).hexdigest(),
            'posture': posture, 'baseline': baseline,
            'assessments': [{'id': option['id'], 'assessment': option['assessment'],
                             'exclusions': excluded_by_id.get(option['id'], [])} for option in options],
            'sensitivity': scenarios, 'rank_instability': instability,
            'authority_granted': False, 'evidence_independently_verified': False,
            'limits': 'Offline supplied-evidence comparison; no organizational approval, source verification, or causal outcome claim'}


def main():
    try:
        data = sys.stdin.buffer.read(100001)
        if len(data) > 100000:
            raise ValueError('Input exceeds 100000 bytes')
        record = json.loads(data.decode('utf-8'), object_pairs_hook=unique, parse_float=finite_float,
                            parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Non-finite JSON number')))
        result = compare(record)
    except (ValueError, TypeError, UnicodeError, RecursionError):
        print(json.dumps({'error': 'invalid or incompatible comparison input'}))
        return 2
    print(json.dumps(result, allow_nan=False, sort_keys=True))
    return 0 if result['posture'] == 'ready-for-review' else 1


if __name__ == '__main__':
    sys.exit(main())
