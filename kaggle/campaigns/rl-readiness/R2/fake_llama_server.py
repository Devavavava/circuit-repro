"""Local stand-in for llama-server (R2 mock test of editcap_run.py think flags).

Implements /v1/chat/completions, /apply-template, /completion with the response
fields editcap_run.py reads. The answer = 3 edits derived from the anchor netlist
found in the prompt (anchor + one appended device each). Phase-1 /completion
emits "<think>\\n" + one word per token; FAKE_THINK_LEN (default 1500) words then
"</think>" -> a budget below that exercises the forced-close path, above it the
natural-close path.  usage: fake_llama_server.py <port>"""
import json, os, re, sys
from http.server import BaseHTTPRequestHandler, HTTPServer

THINK_LEN = int(os.environ.get("FAKE_THINK_LEN", "1500"))
ADDS = ["R Rf1 VOUT1 VIN1", "C Cx VOUT1 VSS", "R Rx VOUT1 VSS"]
LOG = os.environ.get("FAKE_LOG")


def answer_for(text):
    m = re.search(r"=== ANCHOR NETLIST[^\n]*\n```netlist\n(.*?)```", text, re.S)
    anchor = m.group(1) if m else ""
    parts = ["DIAGNOSIS: fake."]
    for a in ADDS:
        parts.append("```netlist\n%s%s\n```\nPREDICTED: s11 improves ~1 dB." % (anchor, a))
    return "\n\n".join(parts)


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, obj):
        b = json.dumps(obj).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if LOG:
            with open(LOG, "a") as fh:
                fh.write(json.dumps({"path": self.path, "body": body}) + "\n")
        tim = {"prompt_n": 10, "prompt_ms": 5.0, "predicted_n": 0, "predicted_ms": 0.0}
        if self.path == "/v1/chat/completions":
            user = body["messages"][-1]["content"]
            nothink = user.rstrip().endswith("/no_think")
            ans = answer_for(user)
            reas = "" if nothink else "thinking " * 50
            return self._send({"choices": [{"index": 0, "finish_reason": "stop",
                                            "message": {"role": "assistant", "content": ans,
                                                        "reasoning_content": reas}}],
                               "usage": {"prompt_tokens": 10, "completion_tokens": 300,
                                         "total_tokens": 310},
                               "timings": dict(tim, predicted_n=300, predicted_ms=12000.0)})
        if self.path == "/apply-template":
            p = "".join("<|im_start|>%s\n%s<|im_end|>\n" % (m["role"], m["content"])
                        for m in body["messages"]) + "<|im_start|>assistant\n"
            return self._send({"prompt": p})
        if self.path == "/completion":
            prompt, n = body["prompt"], int(body["n_predict"])
            if prompt.endswith("<|im_start|>assistant\n"):         # phase 1
                if n >= THINK_LEN:
                    txt, st, k = "<think>\n" + "w " * THINK_LEN, "word", THINK_LEN
                else:
                    txt, st, k = "<think>\n" + "w " * n, "limit", n
                return self._send({"content": txt, "tokens_predicted": k,
                                   "tokens_evaluated": 10, "stop_type": st,
                                   "timings": dict(tim, predicted_n=k, predicted_ms=40.0 * k)})
            assert "</think>" in prompt, "phase-2 prompt lacks </think>"
            ans = answer_for(prompt)
            return self._send({"content": ans, "tokens_predicted": 200,
                               "tokens_evaluated": 30, "stop_type": "eos",
                               "timings": dict(tim, predicted_n=200, predicted_ms=8000.0)})
        self.send_response(404)
        self.end_headers()


if __name__ == "__main__":
    HTTPServer(("127.0.0.1", int(sys.argv[1])), H).serve_forever()
