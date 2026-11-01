"""Bounded offline JSON assessment CLI; input assertions remain untrusted."""
import json
import sys
from . import assess


def unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON key')
        result[key] = value
    return result


def main():
    try:
        data = sys.stdin.buffer.read(100001)
        if len(data) > 100000:
            raise ValueError('Input exceeds 100000 bytes')
        record = json.loads(data.decode('utf-8'), object_pairs_hook=unique,
                            parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Non-finite JSON number')))
        result = assess(record)
    except (ValueError, TypeError, UnicodeError, RecursionError):
        print(json.dumps({'error': 'invalid assessment input'}))
        return 2
    print(json.dumps(result, allow_nan=False, sort_keys=True))
    return 0 if result['posture'] == 'ready-for-review' else 1


if __name__ == '__main__':
    sys.exit(main())
