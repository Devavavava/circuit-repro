"""Local llama-server stand-in for the P1 mock tests (stdlib only).

Extends kaggle/campaigns/rl-readiness/R2/fake_llama_server.py (same /apply-template and
two-phase /completion behaviour, FAKE_THINK_LEN words of think) with:
  * /v1/chat/completions on a RATIONALIZE prompt (has '=== VERIFIED SOLUTION'):
    a reasoning paragraph + the solution netlist; FAKE_RAT_MODE cycles per request
    through ok / reorder (lines swapped -> tokens differ) / leak / two_blocks /
    long (>512 tokens) so every filter branch is exercised.
  * /tokenize: whitespace tokens.
usage: fake_server.py <port>"""
import itertools
import json
import os
import re
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn

THINK_LEN = int(os.environ.get("FAKE_THINK_LEN", "1500"))
ADDS = ["R Rf1 VOUT1 VIN1", "C Cx VOUT1 VSS", "R Rx VOUT1 VSS"]
MODES = os.environ.get("FAKE_RAT_MODES", "ok,reorder,leak,two_blocks,long,ok").split(",")
_cyc = itertools.cycle(MODES)
_lock = threading.Lock()


def answer_for(text):
    m = re.search(r"=== ANCHOR NETLIST[^\n]*\n```netlist\n(.*?)```", text, re.S)
    anchor = m.group(1) if m else ""
    parts = ["DIAGNOSIS: fake."]
    for a in ADDS:
        parts.append("```netlist\n%s%s\n```\nPREDICTED: s11 improves ~1 dB." % (anchor, a))
    return "\n\n".join(parts)


def rat_answer(text):
    with _lock:
        mode = next(_cyc)
    sol = re.search(r"=== VERIFIED SOLUTION[^\n]*\n.*?```netlist\n(.*?)```", text, re.S).group(1)
    reasoning = ("The binding constraint is input match; the series gate inductor and the "
                 "degeneration set the real part, so I change the input network.")
    if mode == "reorder":
        ls = sol.strip("\n").split("\n")
        ls[0], ls[-1] = ls[-1], ls[0]
        sol = "\n".join(ls) + "\n"
    if mode == "leak":
        reasoning += " This matches the verified netlist."
    if mode == "long":
        reasoning += " filler" * 600
    body = "%s\n\n```netlist\n%s```" % (reasoning, sol)
    if mode == "two_blocks":
        body = "%s\n\n```netlist\n%s```\n\nand again\n```netlist\n%s```" % (reasoning, sol, sol)
    return body, mode


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
        tim = {"prompt_n": 10, "prompt_ms": 5.0, "predicted_n": 0, "predicted_ms": 0.0}
        if self.path == "/tokenize":
            return self._send({"tokens": list(range(len(body["content"].split())))})
        if self.path == "/v1/chat/completions":
            user = body["messages"][-1]["content"]
            if "=== VERIFIED SOLUTION" in user:
                assert user.rstrip().endswith("/no_think")
                ans, mode = rat_answer(user)
                reas = ""
            else:
                ans, mode, reas = answer_for(user), None, "thinking " * 50
            return self._send({"choices": [{"index": 0, "finish_reason": "stop",
                                            "message": {"role": "assistant", "content": ans,
                                                        "reasoning_content": reas}}],
                               "usage": {"prompt_tokens": 10, "completion_tokens": 300,
                                         "total_tokens": 310},
                               "timings": dict(tim, predicted_n=300, predicted_ms=12000.0),
                               "_fake_mode": mode})
        if self.path == "/apply-template":
            p = "".join("<|im_start|>%s\n%s<|im_end|>\n" % (m["role"], m["content"])
                        for m in body["messages"]) + "<|im_start|>assistant\n"
            return self._send({"prompt": p})
        if self.path == "/completion":
            prompt, n = body["prompt"], int(body["n_predict"])
            if prompt.endswith("<|im_start|>assistant\n"):
                if n >= THINK_LEN:
                    txt, st, k = "<think>\n" + "w " * THINK_LEN, "word", THINK_LEN
                else:
                    txt, st, k = "<think>\n" + "w " * n, "limit", n
                return self._send({"content": txt, "tokens_predicted": k, "tokens_evaluated": 10,
                                   "stop_type": st,
                                   "timings": dict(tim, predicted_n=k, predicted_ms=40.0 * k)})
            assert "</think>" in prompt, "phase-2 prompt lacks </think>"
            return self._send({"content": answer_for(prompt), "tokens_predicted": 200,
                               "tokens_evaluated": 30, "stop_type": "eos",
                               "timings": dict(tim, predicted_n=200, predicted_ms=8000.0)})
        self.send_response(404)
        self.end_headers()


class TS(ThreadingMixIn, HTTPServer):
    daemon_threads = True


if __name__ == "__main__":
    TS(("127.0.0.1", int(sys.argv[1])), H).serve_forever()
