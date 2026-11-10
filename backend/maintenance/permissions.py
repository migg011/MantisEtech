"""Permissões explícitas por perfil; restrições por linha ficam nos serviços."""
from rest_framework.permissions import BasePermission


class ActiveAccount(BasePermission):
    message = 'Autenticação necessária.'

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_active)


class MaintenanceTeam(ActiveAccount):
    message = 'Acesso restrito à equipe de manutenção.'

    def has_permission(self, request, view):
        return super().has_permission(request, view) and request.user.role in ('ADMINISTRADOR', 'TECNICO')


class Administrator(ActiveAccount):
    message = 'Acesso restrito ao administrador.'

    def has_permission(self, request, view):
        return super().has_permission(request, view) and request.user.role == 'ADMINISTRADOR'
