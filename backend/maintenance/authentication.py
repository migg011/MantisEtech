"""Autenticação DRF compatível com o token Bearer já usado pelo Angular."""
from django.conf import settings
from django.core import signing
from django.utils.crypto import constant_time_compare
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from .exceptions import ApiError
from .models import User

TOKEN_SALT = 'mantis.angular.api.v1'


def issue_token(user):
    return signing.dumps({'uid': user.pk, 'auth': user.get_session_auth_hash()}, salt=TOKEN_SALT)


def token_user(request):
    scheme, _, token = request.headers.get('Authorization', '').partition(' ')
    if scheme.lower() != 'bearer' or not token or len(token) > 2048:
        raise ApiError('Autenticação necessária.', 401)
    try:
        data = signing.loads(token, salt=TOKEN_SALT, max_age=settings.API_TOKEN_MAX_AGE)
        user = User.objects.get(pk=data['uid'], active=True)
        if not constant_time_compare(data['auth'], user.get_session_auth_hash()):
            raise ApiError('Sessão expirada. Entre novamente.', 401)
        return user
    except (signing.BadSignature, User.DoesNotExist, KeyError, TypeError, ValueError):
        raise ApiError('Sessão inválida ou expirada. Entre novamente.', 401)


class BearerAuthentication(BaseAuthentication):
    def authenticate(self, request):
        if not request.headers.get('Authorization'):
            return None
        try:
            return token_user(request), None
        except ApiError as error:
            raise AuthenticationFailed(error.message) from error

    def authenticate_header(self, request):
        return 'Bearer'
