"""HTTPS termination must not cause redirects back to the same public URL."""

from django.test import SimpleTestCase, override_settings


@override_settings(
    DEBUG=False,
    SECURE_SSL_REDIRECT=True,
    SECURE_PROXY_SSL_HEADER=("HTTP_X_FORWARDED_PROTO", "https"),
    ALLOWED_HOSTS=["testserver"],
)
class ProxyDeploymentTests(SimpleTestCase):
    def test_plain_http_redirects_to_https(self):
        response = self.client.get("/login/")
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response["Location"], "https://testserver/login/")

    def test_trusted_https_proxy_serves_login_without_redirect_loop(self):
        response = self.client.get("/login/", HTTP_X_FORWARDED_PROTO="https")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Entrar no GenFin")
