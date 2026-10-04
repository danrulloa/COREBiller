import contextlib
import io
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from http.server import BaseHTTPRequestHandler

import app


class OtherApplication(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'{"application":"Other"}')


class StartupTests(unittest.TestCase):
    def run_collision(self, handler, same_directory=True):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            server = app.LocalServer(('127.0.0.1',0),handler)
            server.data_dir = root / ('data' if same_directory else 'other-data')
            worker = threading.Thread(target=server.serve_forever,daemon=True)
            worker.start()
            output, errors = io.StringIO(), io.StringIO()
            try:
                with patch.object(app,'ROOT',root), contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
                    result = app.main(['--port',str(server.server_port)])
                self.assertFalse((root/'data').exists(), 'A second launch must not initialize or migrate databases.')
                return result, output.getvalue()+errors.getvalue()
            finally:
                server.shutdown()
                server.server_close()
                worker.join()

    def test_running_same_copy_is_successful_noop(self):
        result,message=self.run_collision(app.Handler)
        self.assertEqual(result,0)
        self.assertIn('ya está funcionando',message)
        self.assertNotIn('Traceback',message)

    def test_other_copy_is_not_mistaken_for_this_database(self):
        result,message=self.run_collision(app.Handler,False)
        self.assertEqual(result,1)
        self.assertIn('otra carpeta',message)
        self.assertIn('-Port',message)

    def test_unrelated_application_gets_actionable_error(self):
        result,message=self.run_collision(OtherApplication)
        self.assertEqual(result,1)
        self.assertIn('otra aplicación',message)
        self.assertNotIn('Traceback',message)
