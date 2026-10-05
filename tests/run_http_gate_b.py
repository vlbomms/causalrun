"""Record the recovery gate without overwriting gate A evidence."""
from tests.run_http_gate_a import main

if __name__ == '__main__':
    raise SystemExit(main('b'))
