"""Erros de domínio e contrato JSON compartilhado com o Angular."""
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError
from django.db import IntegrityError
from django.http import Http404
from rest_framework.response import Response


class ApiError(Exception):
    def __init__(self, message, status=400, details=None):
        self.message = message
        self.status = status
        self.details = details
        super().__init__(message)


def messages_text(details):
    if isinstance(details, dict):
        return ' '.join(messages_text(value) for value in details.values())
    if isinstance(details, (list, tuple)):
        return ' '.join(messages_text(value) for value in details)
    return str(details)


def handle_exception(exc, context):
    from rest_framework.views import exception_handler

    if isinstance(exc, ApiError):
        data = {'error': exc.message}
        if exc.details is not None:
            data['details'] = exc.details
        return Response(data, status=exc.status)
    if isinstance(exc, (Http404, ObjectDoesNotExist)):
        return Response({'error': 'Recurso não encontrado.'}, status=404)
    if isinstance(exc, PermissionDenied):
        return Response({'error': 'Acesso negado.'}, status=403)
    if isinstance(exc, ValidationError):
        return Response({'error': ' '.join(exc.messages)}, status=400)
    if isinstance(exc, IntegrityError):
        return Response({'error': 'Registro duplicado, posição ocupada ou associação inválida.'}, status=409)
    response = exception_handler(exc, context)
    if response is not None:
        details = response.data
        response.data = {'error': messages_text(details), 'details': details}
    return response
