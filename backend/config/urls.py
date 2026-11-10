"""Configuração de URLs; o router e as rotas pertencem ao app maintenance."""
from django.urls import include, path

urlpatterns = [
    path('api/', include('maintenance.urls')),
    path('api/v1/', include('maintenance.urls_v1')),
]

handler400 = 'maintenance.api.bad_request'
handler403 = 'maintenance.api.forbidden'
handler404 = 'maintenance.api.not_found'
handler500 = 'maintenance.api.server_error'
