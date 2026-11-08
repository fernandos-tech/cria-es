"""Single-owner login with short-lived, server-side sessions."""
import hashlib
import hmac
import secrets
import threading
import time
import json
import os
from pathlib import Path


class InvalidCredentials(Exception):
    pass


class TooManyAttempts(Exception):
    pass


class Sessions:
    def __init__(self, password='', username='studio', lifetime=8*3600):
        self.password = password
        self.username = username.strip() or 'studio'
        self.lifetime = lifetime
        self.sessions = {}
        self.failures = {}
        self.lock = threading.Lock()
        self.storage = None

    def attach_storage(self, path):
        self.storage = Path(path)
        with self.lock:
            try:
                stored = json.loads(self.storage.read_text())
                if hmac.compare_digest(stored.get('owner', ''), self.owner_fingerprint()):
                    now = time.time()
                    self.sessions = {key: end for key, end in stored.get('sessions', {}).items() if end > now}
            except (OSError, ValueError, TypeError):
                pass

    def owner_fingerprint(self):
        return hmac.new(self.password.encode(), ('cria-owner:'+self.username).encode(), hashlib.sha256).hexdigest()

    def persist(self):
        if self.storage is None:
            return
        temporary = self.storage.with_suffix('.tmp')
        with temporary.open('w', encoding='utf-8') as stream:
            os.chmod(temporary, 0o600)
            json.dump({'owner': self.owner_fingerprint(), 'sessions': self.sessions}, stream)
        temporary.replace(self.storage)

    @property
    def required(self):
        return bool(self.password)

    def credentials_valid(self, username, password):
        if not isinstance(username, str) or not isinstance(password, str):
            return False
        return (hmac.compare_digest(username.encode(), self.username.encode()) and
                hmac.compare_digest(password.encode(), self.password.encode()))

    @staticmethod
    def digest(token):
        return hashlib.sha256(token.encode()).hexdigest()

    def login(self, username, password, client):
        now = time.monotonic()
        with self.lock:
            self.sessions = {key: end for key, end in self.sessions.items() if end > time.time()}
            self.failures = {key: (count, end) for key, (count, end) in self.failures.items() if end > now}
            count, end = self.failures.get(client, (0, now+60))
            if count >= 6:
                raise TooManyAttempts()
            if not self.credentials_valid(username, password):
                self.failures[client] = (count+1, end)
                raise InvalidCredentials()
            self.failures.pop(client, None)
            if len(self.sessions) >= 256:
                self.sessions.pop(next(iter(self.sessions)))
            token = secrets.token_urlsafe(32)
            self.sessions[self.digest(token)] = time.time()+self.lifetime
            self.persist()
            return token

    def valid(self, token):
        if not token or len(token) > 128:
            return False
        with self.lock:
            return self.sessions.get(self.digest(token), 0) > time.time()

    def logout(self, token):
        with self.lock:
            self.sessions.pop(self.digest(token), None)
            self.persist()
