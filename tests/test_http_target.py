import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from genai_guardrail_lab.models import TargetSpec
from genai_guardrail_lab.targets.builtin import HttpJsonTarget


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802 - required by BaseHTTPRequestHandler
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length))
        assert payload["messages"][0]["content"] == "hello"
        body = json.dumps({"result": {"answer": "SAFE_COMPLETION_TOKEN"}}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):  # noqa: A002
        return


def test_http_json_target_sends_application_payload():
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        spec = TargetSpec(
            name="app",
            target_type="http_json",
            model="rag-app",
            config={
                "endpoint": f"http://127.0.0.1:{server.server_port}/chat",
                "method": "POST",
                "body": {"messages": "${messages}", "scenario": "${scenario_name}"},
                "response_path": "result.answer",
            },
        )
        target = HttpJsonTarget(spec, {"collection": {"request_timeout_seconds": 5}})
        response = target.send([{"role": "user", "content": "hello"}], {"scenario_name": "direct"})
        assert response.error == ""
        assert response.text == "SAFE_COMPLETION_TOKEN"
    finally:
        server.shutdown()
