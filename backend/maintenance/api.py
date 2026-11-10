"""Compatibilidade dos imports anteriores. As URLs são atendidas pelas views DRF."""
from django.http import JsonResponse


def error_response(message, status, details=None):
    data = {'error': message}
    if details is not None:
        data['details'] = details
    return JsonResponse(data, status=status)


def bad_request(request, exception=None):
    return error_response('Requisição inválida.', 400)


def forbidden(request, exception=None):
    return error_response('Acesso negado.', 403)


def not_found(request, exception=None):
    return error_response('Recurso não encontrado.', 404)


def server_error(request):
    return error_response('Erro interno.', 500)
