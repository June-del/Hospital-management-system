import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app
from models import init_db, create_default_admin, get_user_by_username


class AuthSystemTests(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app.config.update(TESTING=True, SECRET_KEY='test-secret')
        self.client = self.app.test_client()
        init_db()
        create_default_admin()

    def test_default_admin_can_login(self):
        response = self.client.post('/login', data={'username': 'admin', 'password': 'admin123'}, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Welcome back, admin!', response.data)

    def test_unprotected_pages_redirect_to_login(self):
        response = self.client.get('/dashboard', follow_redirects=True)
        self.assertIn(b'Please log in to continue.', response.data)

    def test_user_can_logout(self):
        self.client.post('/login', data={'username': 'admin', 'password': 'admin123'})
        response = self.client.get('/logout', follow_redirects=True)
        self.assertIn(b'You have been logged out.', response.data)


if __name__ == '__main__':
    unittest.main()
