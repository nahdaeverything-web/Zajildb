"""Shared: serve next/out on an ephemeral port. Every sync test provisions its own server (R6)."""
import subprocess, socket, sys, time, os
OUT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'out'))
def serve():
    assert os.path.exists(os.path.join(OUT, 'test-harness', 'index.html')), 'run `npm run build:harness` first'
    s = socket.socket(); s.bind(('127.0.0.1', 0)); port = s.getsockname()[1]; s.close()
    srv = subprocess.Popen([sys.executable, '-m', 'http.server', str(port), '-d', OUT, '--bind', '127.0.0.1'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.8)
    return srv, f'http://127.0.0.1:{port}/test-harness/'
