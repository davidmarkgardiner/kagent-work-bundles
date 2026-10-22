"""Operator-owned artifact origins preserve the bounded download boundary."""
import unittest
from unittest.mock import MagicMock, patch
from controller import Rejected, artifact_bytes


class OriginTests(unittest.TestCase):
    def test_shared_flux_origin_is_exact_and_proxy_free(self):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = b'archive'
        with patch('controller.urllib.request.build_opener') as build:
            build.return_value.open.return_value = response
            self.assertEqual(artifact_bytes('http://source-controller.flux-system.svc.cluster.local/a.tar.gz',
                'tenant', 'http://source-controller.flux-system.svc.cluster.local:80'), b'archive')
            self.assertEqual(build.call_args.args[1].proxies, {})

    def test_origin_does_not_authorize_other_hosts_ports_or_credentials(self):
        for url in ['http://source-controller.other.svc.cluster.local/a',
                    'http://source-controller.flux-system.svc.cluster.local:9090/a',
                    'http://source-controller.flux-system.svc.cluster.local:0/a',
                    'https://source-controller.flux-system.svc.cluster.local/a',
                    'http://user@source-controller.flux-system.svc.cluster.local/a',
                    'http://source-controller.flux-system.svc.cluster.local/a?q=1',
                    'http://source-controller.flux-system.svc.cluster.local/a#x']:
            with self.subTest(url=url), patch('controller.urllib.request.build_opener') as build:
                with self.assertRaises(Rejected):
                    artifact_bytes(url, 'tenant', 'http://source-controller.flux-system.svc.cluster.local')
                build.assert_not_called()

    def test_invalid_operator_origin_is_rejected(self):
        for origin in ['file:///tmp/a', 'http://u:p@source-controller/a', 'http://host/path', 'http://host:bad']:
            with self.subTest(origin=origin), self.assertRaises(Rejected):
                artifact_bytes('http://host/a', 'tenant', origin)

    def test_redirect_is_rejected(self):
        from controller import NoRedirects
        with self.assertRaisesRegex(Rejected, 'ArtifactRedirectDenied'):
            NoRedirects().redirect_request(None, None, 302, '', {}, 'http://other/a')


if __name__ == '__main__':
    unittest.main()
