"""Serve only the static public archive on this computer. No PHP or remote requests."""
import argparse
import functools
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT=Path(__file__).resolve().parent/'public'


class ArchiveHandler(SimpleHTTPRequestHandler):
    extensions_map={**SimpleHTTPRequestHandler.extensions_map,'.js':'application/javascript','.css':'text/css','.html':'text/html; charset=utf-8','.svg':'image/svg+xml','.woff2':'font/woff2'}

    def end_headers(self):
        self.send_header('X-Robots-Tag','noindex, nofollow')
        self.send_header('Cache-Control','no-cache')
        super().end_headers()

    def do_POST(self):
        self.send_error(405,'Static archive: form submission is disabled')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=4173)
    args=parser.parse_args()
    if not (ROOT/'index.html').exists():
        raise SystemExit('Archive not built. Run scripts/archive_site.py first.')
    handler=functools.partial(ArchiveHandler,directory=str(ROOT))
    server=ThreadingHTTPServer(('127.0.0.1',args.port),handler)
    print(f'Local VL63 archive: http://127.0.0.1:{args.port}/',flush=True)
    print(f'Content index: http://127.0.0.1:{args.port}/archive-index.html',flush=True)
    print('Stop with Ctrl+C.',flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()
