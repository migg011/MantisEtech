"""Roteador raiz: inclui os contratos /api e aponta os erros globais para respostas JSON."""

from django.urls import include, path

urlpatterns = [path('', include('maintenance.urls'))]

handler400 = 'maintenance.api.bad_request_value'
handler403 = 'maintenance.api.forbidden_value'
handler404 = 'maintenance.api.not_found_value'
handler500 = 'maintenance.api.server_error_value'
