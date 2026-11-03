from django.test import SimpleTestCase


class HealthTests(SimpleTestCase):
    def test_health(self):
        response = self.client.get('/api/health/')
        self.assertEqual(response.status_code, 200)
