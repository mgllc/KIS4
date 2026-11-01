"""KIS4 evidence-based scoring with caller-defined criteria and critical gates."""
import math

__version__ = "0.1.0"
DIMENSIONS = ('simple', 'secure', 'sustainable', 'scalable')


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _number(value, lower, upper):
    return type(value) in (int, float) and lower <= value <= upper and math.isfinite(value)


def assess(record):
    """Evaluate supplied evidence, never organizational approval or source truth.

    All material criteria need complete traceability before aggregation. A missing
    or failed critical gate suppresses the composite regardless of other scores.
    """
    if not isinstance(record, dict) or type(record.get('schema')) is not int or record['schema'] != 1:
        raise ValueError('Expected a schema 1 object')
    for key in ('decision', 'owner', 'rubric_id', 'weights_rationale', 'tradeoffs', 'sensitivity'):
        if not _text(record.get(key)):
            raise ValueError('Missing ' + key)
    dimensions = record.get('dimensions')
    if not isinstance(dimensions, dict) or set(dimensions) != set(DIMENSIONS):
        raise ValueError('Exactly four KIS4 dimensions required')
    weights = record.get('weights')
    if not isinstance(weights, dict) or set(weights) != set(DIMENSIONS):
        raise ValueError('Explicit dimension weights required')
    if any(not _number(w, 0.000001, 1) for w in weights.values()) or not math.isclose(sum(weights.values()), 1, abs_tol=1e-9):
        raise ValueError('Positive dimension weights must sum to 1')
    threshold = record.get('threshold')
    if not _number(threshold, 1, 5):
        raise ValueError('Explicit threshold between 1 and 5 required')
    minimums = record.get('minimums')
    if not isinstance(minimums, dict) or set(minimums) != set(DIMENSIONS) or any(not _number(v, 1, 5) for v in minimums.values()):
        raise ValueError('Explicit minimum for each simultaneous constraint required')
    gates = record.get('gates')
    if not isinstance(gates, list) or not gates:
        raise ValueError('Critical gates required')
    seen = set()
    failed, unknown = [], []
    for gate in gates:
        if not isinstance(gate, dict) or not _text(gate.get('id')) or gate['id'] in seen:
            raise ValueError('Invalid or duplicate gate')
        seen.add(gate['id'])
        if gate.get('status') not in ('pass', 'fail', 'unknown'):
            raise ValueError('Invalid gate status')
        if gate['status'] == 'fail':
            failed.append(gate['id'])
        elif gate['status'] == 'unknown' or not _text(gate.get('evidence')):
            unknown.append(gate['id'])
    scores, gaps = {}, []
    criterion_ids = set()
    for dimension in DIMENSIONS:
        criteria = dimensions[dimension]
        if not isinstance(criteria, list) or not criteria:
            raise ValueError('Criteria required for ' + dimension)
        total, weight, complete = 0.0, 0.0, True
        for c in criteria:
            if not isinstance(c, dict) or not _text(c.get('id')) or c['id'] in criterion_ids:
                raise ValueError('Invalid or duplicate criterion')
            criterion_ids.add(c['id'])
            if not _number(c.get('weight'), 0.000001, 1):
                raise ValueError('Positive criterion weight required')
            weight += c['weight']
            trace = ('principle', 'obligation', 'control', 'test', 'evidence', 'rationale', 'maturity', 'confidence')
            covered = all(_text(c.get(k)) for k in trace)
            covered = covered and _number(c.get('score'), 1, 5) and _number(c.get('maturity_cap'), 1, 5)
            if not covered:
                gaps.append(c['id'] + ':evidence-incomplete')
                complete = False
            elif c['score'] > c['maturity_cap']:
                gaps.append(c['id'] + ':maturity-cap-exceeded')
                complete = False
            else:
                total += c['score'] * c['weight']
        if not math.isclose(weight, 1, abs_tol=1e-9):
            raise ValueError('Criterion weights must sum to 1 per dimension')
        scores[dimension] = round(total, 6) if complete else None
    composite = None
    if failed:
        posture = 'revise'
    elif unknown or gaps:
        posture = 'defer-pending-evidence'
    else:
        composite = round(sum(scores[d] * weights[d] for d in DIMENSIONS), 6)
        posture = 'ready-for-review' if composite >= threshold and all(scores[d] >= minimums[d] for d in DIMENSIONS) else 'revise'
    return {'schema': 1, 'framework': 'KIS4', 'rubric_id': record['rubric_id'],
            'posture': posture, 'scores': scores, 'composite': composite,
            'failed_gates': failed, 'unknown_gates': unknown, 'gaps': gaps,
            'authority_granted': False, 'evidence_independently_verified': False}
