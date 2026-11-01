"""
Minimal CSRF protection for all state-changing requests.

A random token is stored in the user's session and must be sent back with every
POST/PUT/PATCH/DELETE request, either as the hidden form field `csrf_token`
(use {{ csrf_token() }} in templates) or in an `X-CSRFToken` header.
"""
import hmac
import secrets
from flask import abort, request, session

SAFE_METHODS = {'GET', 'HEAD', 'OPTIONS', 'TRACE'}


def get_csrf_token():
    token = session.get('_csrf_token')
    if not token:
        token = secrets.token_hex(32)
        session['_csrf_token'] = token
    return token


def init_csrf(app):
    app.jinja_env.globals['csrf_token'] = get_csrf_token

    @app.before_request
    def _verify_csrf_token():
        if not app.config.get('CSRF_ENABLED', True):
            return
        if request.method in SAFE_METHODS:
            return
        expected = session.get('_csrf_token', '')
        supplied = request.form.get('csrf_token') or request.headers.get('X-CSRFToken', '')
        if not expected or not supplied or not hmac.compare_digest(expected, supplied):
            abort(400)
