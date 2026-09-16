import unittest

import gitlab_summary_writer as writer
from test_alert_controller import snapshot, NOW
import alert_controller


def alert():
    event, _ = alert_controller.build_event(
        snapshot(), {"snapshot": "cluster-health-snapshot-0000000007"}, {},
        now=NOW, daily_slot="2026-09-16", top_n=10, cluster_ref="worker-a-ref",
    )
    return event


ANALYSIS = "## TL;DR\nOne shared scheduling problem affects the supplied namespaces.\n\n## Evidence\nBounded evidence."


class FakeClient(writer.GitLabClient):
    def __init__(self, search):
        self.search = search
        self.calls = []

    def request(self, method, path, body=None):
        self.calls.append((method, path, body))
        if method == "GET":
            if path.startswith("/labels?"):
                label = path.split("search=", 1)[1].split("&", 1)[0]
                from urllib.parse import unquote_plus
                return [{"name": unquote_plus(label)}], {"x-next-page": ""}
            return self.search, {"x-next-page": ""}
        labels = body["labels"].split(",")
        iid = 7 if method == "PUT" else 8
        return {"iid": iid, "labels": labels, "web_url": "https://gitlab.example.invalid/issue"}, {}


class GitLabWriterTests(unittest.TestCase):
    def test_create_when_no_stable_label_match_exists(self):
        client = FakeClient([])
        result = client.reconcile(alert(), ANALYSIS)
        self.assertEqual(result["action"], "created")
        self.assertEqual([call[0] for call in client.calls], ["GET", "GET", "GET", "GET", "POST"])

    def test_update_exactly_one_matching_issue(self):
        labels = writer.issue_labels("worker-a")
        client = FakeClient([{"iid": 7, "labels": labels}])
        result = client.reconcile(alert(), ANALYSIS)
        self.assertEqual(result["action"], "updated")
        self.assertEqual(client.calls[-1][1], "/issues/7")

    def test_multiple_matching_issues_fail_closed(self):
        labels = writer.issue_labels("worker-a")
        client = FakeClient([{"iid": 7, "labels": labels}, {"iid": 8, "labels": labels}])
        with self.assertRaisesRegex(RuntimeError, "multiple"):
            client.reconcile(alert(), ANALYSIS)
        self.assertEqual([call[0] for call in client.calls], ["GET", "GET", "GET", "GET"])

    def test_missing_required_label_fails_before_issue_create(self):
        class MissingLabelClient(FakeClient):
            def request(self, method, path, body=None):
                if path.startswith("/labels?"):
                    self.calls.append((method, path, body))
                    return [], {"x-next-page": ""}
                return super().request(method, path, body)

        client = MissingLabelClient([])
        with self.assertRaisesRegex(RuntimeError, "required GitLab label"):
            client.reconcile(alert(), ANALYSIS)
        self.assertEqual(len(client.calls), 1)

    def test_paginated_identity_search_fails_closed(self):
        class PaginatedClient(FakeClient):
            def request(self, method, path, body=None):
                if path.startswith("/issues?"):
                    self.calls.append((method, path, body))
                    return [], {"x-next-page": "2"}
                return super().request(method, path, body)

        client = PaginatedClient([])
        with self.assertRaisesRegex(RuntimeError, "paginated"):
            client.reconcile(alert(), ANALYSIS)
        self.assertFalse(any(call[0] in {"POST", "PUT"} for call in client.calls))

    def test_input_and_output_bounds(self):
        event = alert()
        writer.validate_inputs(event, ANALYSIS)
        with self.assertRaisesRegex(ValueError, "byte limit"):
            writer.validate_inputs(event, "## TL;DR\n" + "x" * writer.MAX_ANALYSIS_BYTES)
        title, description = writer.issue_content(event, ANALYSIS)
        self.assertIn("worker-a", title)
        self.assertIn("single managed daily health summary", description)
        self.assertNotIn("must-not-leak", description)

    def test_domain_reasons_are_safe_markdown_table_cells(self):
        event = alert()
        event["health"]["domains"]["nodes_scheduling"]["reasons"] = ["bad | node\nnext line"]
        _, description = writer.issue_content(event, ANALYSIS)
        self.assertIn("bad \\| node next line", description)


if __name__ == "__main__":
    unittest.main()
