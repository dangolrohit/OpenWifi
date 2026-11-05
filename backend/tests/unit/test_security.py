"""Unit tests for core security, Argon2id, and token generation."""
import unittest
from backend.app.core.security import (
    hash_password, verify_password,
    generate_session_token, generate_csrf_token, generate_voucher_code
)

class SecurityTests(unittest.TestCase):
    def test_argon2id_hashing_and_verification(self):
        password = "AdminSuperSecretPassword123!"
        hashed = hash_password(password)
        self.assertNotEqual(hashed, password)
        self.assertTrue(hashed.startswith("$argon2id$"))
        self.assertTrue(verify_password(password, hashed))
        self.assertFalse(verify_password("wrong-password", hashed))

    def test_session_token_entropy(self):
        token1 = generate_session_token()
        token2 = generate_session_token()
        self.assertNotEqual(token1, token2)
        self.assertGreaterEqual(len(token1), 32)

    def test_csrf_token_generation(self):
        c1 = generate_csrf_token()
        c2 = generate_csrf_token()
        self.assertNotEqual(c1, c2)
        self.assertEqual(len(c1), 32)

    def test_voucher_code_generation(self):
        v = generate_voucher_code(6)
        self.assertEqual(len(v), 6)
        self.assertTrue(v.isdigit())

if __name__ == "__main__":
    unittest.main()

