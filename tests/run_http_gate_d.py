"""Record final regressions before the separately authorized live sandbox run."""
from tests.run_http_gate_a import main

if __name__ == '__main__':
    raise SystemExit(main('d'))
