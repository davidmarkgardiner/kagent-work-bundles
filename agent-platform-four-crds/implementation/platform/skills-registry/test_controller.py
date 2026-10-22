import copy
import io
import tarfile
import unittest
from unittest.mock import patch

from controller import Controller, FINALIZER, Rejected, artifact_bytes, content_digest, sha256, verify_archive


class SkillTests(unittest.TestCase):
    def setUp(self):
        self.body = b"---\nname: platform-demo\ndescription: A synthetic test skill.\n---\nRelease one.\n"
        self.commit = "a" * 40
        files = {"SKILL.md": sha256(self.body)}
        self.skill = {"metadata": {"name": "platform-demo", "namespace": "skills-demo", "generation": 1,
                                   "uid": "test-uid", "resourceVersion": "1", "finalizers": [FINALIZER]},
                      "spec": {"skillName": "platform-demo", "path": "skills/platform-demo", "sourceCommit": self.commit,
                               "sourceRef": {"name": "content"}, "files": files, "contentSha256": content_digest(files)}}
        self.source = {"metadata": {"generation": 2}, "spec": {"ref": {"commit": self.commit}},
                       "status": {"conditions": [{"type": "Ready", "status": "True", "observedGeneration": 2}],
                                  "artifact": {"revision": "sha1:" + self.commit, "url": "http://source-controller.skills-demo.svc.cluster.local/content.tar.gz"}}}
        self.archive = self.tar(self.body)

    def tar(self, body, path="skills/platform-demo/SKILL.md", symlink=False):
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
            entry = tarfile.TarInfo(path)
            if symlink:
                entry.type = tarfile.SYMTYPE
                entry.linkname = "/etc/passwd"
            else:
                entry.size = len(body)
            archive.addfile(entry, None if symlink else io.BytesIO(body))
        result = buffer.getvalue()
        self.source["status"]["artifact"]["digest"] = "sha256:" + sha256(result)
        return result

    def verify(self, archive=None):
        return verify_archive(self.skill, self.source, self.archive if archive is None else archive)

    def test_reviewed_content_and_projection(self):
        data, items, revision = self.verify()
        self.assertEqual(data["file00"], self.body.decode())
        self.assertEqual(items, [{"key": "file00", "path": "platform-demo/SKILL.md"}])
        self.assertEqual(revision, "sha1:" + self.commit)

    def test_changed_bytes_rejected(self):
        archive = self.tar(self.body + b"injection")
        with self.assertRaisesRegex(Rejected, "FileDigestMismatch"):
            self.verify(archive)

    def test_artifact_digest_rejected(self):
        self.source["status"]["artifact"]["digest"] = "sha256:" + "0" * 64
        with self.assertRaisesRegex(Rejected, "ArtifactDigestMismatch"):
            self.verify()

    def test_wrong_commit_rejected(self):
        self.source["spec"]["ref"]["commit"] = "b" * 40
        with self.assertRaisesRegex(Rejected, "SourceNotPinnedAndReady"):
            self.verify()

    def test_stale_source_condition_rejected(self):
        self.source["status"]["conditions"][0]["observedGeneration"] = 1
        with self.assertRaisesRegex(Rejected, "SourceNotPinnedAndReady"):
            self.verify()

    def test_wrong_frontmatter_rejected(self):
        body = self.body.replace(b"platform-demo", b"another-skill")
        self.skill["spec"]["files"]["SKILL.md"] = sha256(body)
        self.skill["spec"]["contentSha256"] = content_digest(self.skill["spec"]["files"])
        archive = self.tar(body)
        with self.assertRaisesRegex(Rejected, "InvalidSkillFrontmatter"):
            self.verify(archive)

    def test_symlink_rejected(self):
        archive = self.tar(self.body, symlink=True)
        with self.assertRaisesRegex(Rejected, "UnsafeSkillFile"):
            self.verify(archive)

    def test_path_traversal_rejected(self):
        self.skill["spec"]["path"] = "../skills/platform-demo"
        with self.assertRaisesRegex(Rejected, "InvalidPath"):
            self.verify()

    def test_missing_file_rejected(self):
        archive = self.tar(self.body, path="skills/another/SKILL.md")
        with self.assertRaisesRegex(Rejected, "MissingSkillFile"):
            self.verify(archive)

    def test_expanded_artifact_limit(self):
        archive = self.tar(b"x" * (8 * 1024 * 1024 + 1), path="unrelated.txt")
        with self.assertRaisesRegex(Rejected, "ExpandedArtifactTooLarge"):
            self.verify(archive)

    def test_download_hosts_rejected_before_network(self):
        for url in ["http://example.com/artifact", "http://source-controller.other.svc.cluster.local/file",
                    "http://source-controller.skills-demo.svc.cluster.local:8080/file"]:
            with self.subTest(url=url), self.assertRaisesRegex(Rejected, "ArtifactHostDenied"):
                artifact_bytes(url, "skills-demo")

    def test_last_good_content_retained_on_bad_revision(self):
        class Kube:
            namespace = "skills-demo"

            def __init__(self, source):
                self.source = source
                self.calls = []

            def call(self, path, method="GET", value=None):
                self.calls.append((path, method, value))
                return self.source if method == "GET" else value

        kube = Kube(self.source)
        self.skill["status"] = {"configMapRef": {"name": "old-reviewed-content"}, "contentSha256": "f" * 64}
        self.skill["spec"]["sourceCommit"] = "b" * 40
        with patch("controller.artifact_bytes", return_value=self.archive):
            Controller(kube).reconcile(self.skill)
        self.assertFalse(any(method == "POST" for _, method, _ in kube.calls))
        status = kube.calls[-1][2]["status"]
        self.assertEqual(status["configMapRef"]["name"], "old-reviewed-content")
        self.assertEqual(status["conditions"][0]["status"], "False")

    def test_in_use_deletion_blocked(self):
        calls = []

        class Kube:
            namespace = "skills-demo"

            def call(self, path, method="GET", value=None):
                calls.append((path, method, value))
                if path.endswith("configmaps"):
                    return {"items": [{"metadata": {"name": "platform-demo-123", "ownerReferences": [{"uid": "test-uid"}]}}]}
                return {"items": [{"spec": {"declarative": {"deployment": {"volumes": [
                    {"projected": {"sources": [{"configMap": {"name": "platform-demo-123"}}]}}]}}}}]}

        self.skill["metadata"]["deletionTimestamp"] = "2026-10-21T00:00:00Z"
        Controller(Kube()).reconcile(self.skill)
        self.assertEqual(calls[-1][2]["status"]["conditions"][0]["reason"], "InUseByAgent")
        self.assertFalse(any(value and "finalizers" in value.get("metadata", {}) for _, _, value in calls))

    def test_invalid_names_rejected(self):
        for name in ["x" * 64, "x" * 253, "name.with.dots"]:
            with self.subTest(name=name):
                skill = copy.deepcopy(self.skill)
                skill["metadata"]["name"] = name
                with self.assertRaisesRegex(Rejected, "InvalidPackageName"):
                    verify_archive(skill, self.source, self.archive)

    def test_duplicate_frontmatter_rejected(self):
        body = self.body.replace(b"description:", b"name: another-skill\ndescription:")
        self.skill["spec"]["files"]["SKILL.md"] = sha256(body)
        self.skill["spec"]["contentSha256"] = content_digest(self.skill["spec"]["files"])
        with self.assertRaisesRegex(Rejected, "InvalidSkillFrontmatter"):
            self.verify(self.tar(body))

    def test_pax_metadata_is_inside_expansion_limit(self):
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w:gz", format=tarfile.PAX_FORMAT) as archive:
            entry = tarfile.TarInfo("skills/platform-demo/SKILL.md")
            entry.size = len(self.body)
            entry.pax_headers = {"comment": "x" * (8 * 1024 * 1024)}
            archive.addfile(entry, io.BytesIO(self.body))
        compressed = buffer.getvalue()
        self.source["status"]["artifact"]["digest"] = "sha256:" + sha256(compressed)
        with self.assertRaisesRegex(Rejected, "ExpandedArtifactTooLarge"):
            self.verify(compressed)

    def test_overlapping_names_do_not_block_unrelated_deletion(self):
        calls = []

        class Kube:
            namespace = "skills-demo"

            def call(self, path, method="GET", value=None):
                calls.append((path, method, value))
                if path.endswith("configmaps"):
                    return {"items": [{"metadata": {"name": "foo-123", "ownerReferences": [{"uid": "test-uid"}]}}]}
                if method == "GET":
                    return {"items": [{"spec": {"declarative": {"deployment": {"volumes": [
                        {"configMap": {"name": "foo-bar-123"}}]}}}}]}
                return value

        self.skill["metadata"].update(name="foo", deletionTimestamp="2026-10-21T00:00:00Z")
        Controller(Kube()).reconcile(self.skill)
        self.assertEqual(calls[-1][2]["metadata"]["finalizers"], [])


if __name__ == "__main__":
    unittest.main()
