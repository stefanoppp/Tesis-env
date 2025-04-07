from django.test import TestCase

from rest_framework.test import APITestCase
from django.urls import reverse
from django.contrib.auth.models import User
from django.conf import settings
from django.test.utils import override_settings

from UsersApp.utils import generar_y_guardar_token

class User2FATestCase(APITestCase):
    def setUp(self):
        self.register_url = reverse('register')
        self.verify_url = reverse('verify')
        self.username = 'testuser'
        self.email = 'testuser@example.com'
        self.password = 'StrongPass123'

    def test_register_success(self):
        """Registro exitoso + token devuelto"""
        response = self.client.post(self.register_url, {
            "username": self.username,
            "email": self.email,
            "first_name": "Test",
            "last_name": "User",
            "password": self.password
        })
        self.assertEqual(response.status_code, 201)
        self.assertIn('message', response.data)
        if settings.DEBUG:
            self.assertIn('dev_token', response.data)

    def test_register_duplicate_email(self):
        """Email duplicado → error"""
        User.objects.create_user(username='otheruser', email=self.email, password='12345678')
        response = self.client.post(self.register_url, {
            "username": self.username,
            "email": self.email,
            "first_name": "Test",
            "last_name": "User",
            "password": self.password
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn('error', response.data)

    @override_settings(DEBUG=True)
    def test_token_verification_success(self):
        """Token correcto → usuario verificado"""
        response = self.client.post(self.register_url, {
            "username": self.username,
            "email": self.email,
            "first_name": "Test",
            "last_name": "User",
            "password": self.password
        })
        token = response.data.get('dev_token')
        self.assertIsNotNone(token)

        verify_response = self.client.post(self.verify_url, {
            "username": self.username,
            "token": token
        })
        self.assertEqual(verify_response.status_code, 200)
        self.assertIn('message', verify_response.data)

    def test_token_verification_failure(self):
        """Token incorrecto → error"""
        self.client.post(self.register_url, {
            "username": self.username,
            "email": self.email,
            "first_name": "Test",
            "last_name": "User",
            "password": self.password
        })

        response = self.client.post(self.verify_url, {
            "username": self.username,
            "token": "000000"
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn('error', response.data)

    def test_token_verification_attempts_exceeded(self):
        """Demasiados intentos → token inválido"""
        self.client.post(self.register_url, {
            "username": self.username,
            "email": self.email,
            "first_name": "Test",
            "last_name": "User",
            "password": self.password
        })

        for _ in range(settings.REDIS_2FA_MAX_ATTEMPTS):
            self.client.post(self.verify_url, {
                "username": self.username,
                "token": "111111"
            })

        # +1 extra para superar el límite
        final_response = self.client.post(self.verify_url, {
            "username": self.username,
            "token": "111111"
        })

        self.assertEqual(final_response.status_code, 400)
        self.assertIn('error', final_response.data)

class UserLoginTestCase(APITestCase):
    def setUp(self):
        self.register_url = reverse('register')
        self.verify_url = reverse('verify')
        self.login_url = reverse('login')

        self.user_data = {
            'username': 'tester_login',
            'email': 'tester_login@example.com',
            'password': 'loginpass123',
            'first_name': 'Tester',
            'last_name': 'Login',
            'phone': '1234567890'
        }

        # Crear usuario y generar token manualmente
        response = self.client.post(self.register_url, self.user_data, format='json')
        self.user = User.objects.get(username='tester_login')
        self.token = response.data.get('dev_token')

        if not self.token:
            self.token = generar_y_guardar_token(self.user)

    def test_login_with_invalid_credentials(self):
        response = self.client.post(self.login_url, {
            'username': 'tester_login',
            'password': 'wrongpass'
        }, format='json')
        self.assertEqual(response.status_code, 403)
        self.assertIn('error', response.data)

    def test_login_without_verification(self):
        response = self.client.post(self.login_url, {
            "username": self.user_data["username"],
            "password": self.user_data["password"]
        }, format='json')

        self.assertEqual(response.status_code, 403)
        self.assertIn('Usuario no verificado', response.data['error'])


    def test_login_successful_after_verification(self):
        verification_response = self.client.post(self.verify_url, {
            'username': 'tester_login',
            'token': self.token
        }, format='json')

        self.assertEqual(verification_response.status_code, 200)

        login_response = self.client.post(self.login_url, {
            'username': 'tester_login',
            'password': 'loginpass123'
        }, format='json')

        self.assertEqual(login_response.status_code, 200)
        self.assertIn('access', login_response.data)
        self.assertIn('refresh', login_response.data)