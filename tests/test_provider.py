import base64
import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from PIL import Image

from homelab_vision.provider import LocalVisionClient, ProviderError, validate_endpoint
from homelab_vision.tasks import fields_schema


class ProviderTests(unittest.TestCase):
    def test_rejects_remote_credentials_redirect_paths(self):
        for base in ["https://example.com", "http://localhost:8000", "http://127.0.0.1/x",
                     "http://u:p@127.0.0.1", "http://127.0.0.1?x=1", "http://127.0.0.1#fragment"]:
            with self.subTest(base=base), self.assertRaises(ValueError):
                validate_endpoint(base)

    def test_actual_http_contract_and_malformed_output(self):
        state = {"reply": '{"ports":8}', "finish": "stop", "redirect": False}
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def do_GET(self):
                if state["redirect"]:
                    self.send_response(302); self.send_header("Location", "/other"); self.end_headers(); return
                self.send_response(200); self.end_headers()
                self.wfile.write(b'{"data":[{"id":"fixture-model"}]}')
            def do_POST(self):
                state["request"] = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                self.send_response(state.get('status',200)); self.end_headers()
                self.wfile.write(json.dumps({"choices": [{"message": {"content": state["reply"]},
                    "finish_reason": state["finish"]}]}).encode())
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            client = LocalVisionClient("fixture-model", f"http://127.0.0.1:{server.server_port}")
            with tempfile.TemporaryDirectory() as temporary:
                path = Path(temporary) / "image.png"; Image.new("RGB", (20,20), "white").save(path)
                schema = fields_schema({"ports": "integer"})
                self.assertEqual(client.analyze([path], "Read ports", schema).value, {"ports":8})
                payload = state["request"]
                encoded = payload["messages"][1]["content"][1]["image_url"]["url"].split(",",1)[1]
                self.assertEqual(base64.b64decode(encoded), path.read_bytes())
                self.assertEqual(payload["response_format"]["json_schema"]["schema"], schema)
                for bad in ['```json\n{"ports":8}\n```', '{"ports":true}', '{"ports":8,"extra":"claim"}']:
                    state["reply"] = bad
                    with self.assertRaises(ProviderError): client.analyze([path], "Read ports", schema)
                state["reply"] = '{"ports":8}'; state["finish"] = "length"
                with self.assertRaises(ProviderError): client.analyze([path], "Read ports", schema)
                state['status']=400
                with self.assertRaises(ProviderError) as caught:client.analyze([path],"Read ports",schema)
                self.assertEqual(caught.exception.details['http_status'],400)
                self.assertIn('choices',caught.exception.details['body'])
                state['status']=200
                state["redirect"] = True
                with self.assertRaises(ProviderError): client.identity()
        finally:
            server.shutdown(); server.server_close(); thread.join()
