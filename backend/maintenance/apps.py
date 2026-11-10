"""Registra o aplicativo maintenance no Django para carregar modelos, comandos e migrações."""

from django.apps import AppConfig

class MaintenanceConfig(AppConfig):
    """Declara nome do aplicativo e padrão de chave primária para o registro no Django."""
    name = 'maintenance'
    verbose_name = 'Manutenção industrial'
