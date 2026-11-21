import json
import unittest

import server


class HandleTests(unittest.TestCase):
    def test_health_is_ok(self):
        status, body, level, _ = server.handle("/health")
        self.assertEqual((status, body, level), (200, {"status": "ok"}, "info"))

    def test_orders_are_listed(self):
        status, body, _, _ = server.handle("/orders")
        self.assertEqual(status, 200)
        self.assertEqual(len(body), 3)

    def test_checkout_fails_once_every_fail_every(self):
        results = [server.handle("/checkout", n)[0] for n in range(1, server.FAIL_EVERY * 2 + 1)]
        self.assertEqual(results.count(500), 2)

    def test_unknown_path_is_404(self):
        self.assertEqual(server.handle("/nope")[0], 404)


class LogLineTests(unittest.TestCase):
    def test_log_line_is_json_with_the_fields_logstash_expects(self):
        line = json.loads(server.log_line("GET", "/checkout", 500, 42.123, "error", "checkout failed"))
        for field in ["time", "service", "level", "method", "path", "status", "latency_ms", "trace_id", "message"]:
            self.assertIn(field, line)
        self.assertEqual(line["latency_ms"], 42.1)
        self.assertEqual(line["level"], "error")


if __name__ == "__main__":
    unittest.main()
