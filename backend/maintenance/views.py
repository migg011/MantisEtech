"""Entradas HTTP pontuais: autenticação, painel e documentos auxiliares."""
from django.http import HttpResponseBase
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .permissions import MaintenanceTeam
from .serializers import LoginSerializer, INPUT_BY_OPERATION
from .services import operations, preventive
from .services.base import OperationContext, Result


class OperationMixin:
    """Converte Request/Response somente aqui; serviços recebem dados de aplicação."""

    def execute(self, function, **kwargs):
        data = self.request.data if self.request.method in ('POST', 'PUT', 'PATCH') else {}
        input_class = INPUT_BY_OPERATION.get(function.__name__)
        if input_class and self.request.method in ('POST', 'PUT', 'PATCH'):
            input_serializer = input_class(data=data)
            input_serializer.is_valid(raise_exception=True)
        context = OperationContext(
            user=self.request.user if self.request.user.is_authenticated else None,
            method=self.request.method,
            filters=self.request.query_params,
            data=data,
            source=self.request.META.get('REMOTE_ADDR', ''),
        )
        result = function(context, **kwargs)
        if isinstance(result, HttpResponseBase):
            self._record_activity(function, kwargs, 200, result)
            return result
        if isinstance(result, Result):
            self._record_activity(function, kwargs, result.status, result.data)
            return Response(result.data, status=result.status)
        self._record_activity(function, kwargs, 200, result)
        return Response(result)

    def _record_activity(self, function, kwargs, status, result):
        """Grava POST/PATCH/DELETE bem-sucedidos para auditoria administrativa."""
        from .models import ActivityLog
        if self.request.method not in ('POST', 'PATCH', 'DELETE', 'PUT'):
            return
        if not (200 <= status < 300):
            return
        user = getattr(self.request, 'user', None)
        if not user or not getattr(user, 'is_authenticated', False):
            return
        target = {name: value for name, value in (kwargs or {}).items() if isinstance(value, int)}
        if status == 201 and isinstance(result, dict) and isinstance(result.get('id'), int) and 'id' not in target:
            target['id'] = result['id']
        route = ''
        if self.request.resolver_match:
            route = (self.request.resolver_match.route or '')[:180]
        try:
            ActivityLog.objects.create(
                actor_id=user.pk, actor_name=user.name, actor_registration=user.registration,
                method=self.request.method, route=route, target=target,
            )
        except Exception:
            # Audit failures never block the business operation.
            pass

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response['Cache-Control'] = 'no-store'
        return response


class LoginView(OperationMixin, APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    serializer_class = LoginSerializer

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        return self.execute(operations.login)


class HealthView(OperationMixin, APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        return self.execute(operations.health_check)


class CurrentUserView(OperationMixin, APIView):
    def get(self, request):
        return self.execute(operations.current_user)


class DashboardView(OperationMixin, APIView):
    permission_classes = [MaintenanceTeam]

    def get(self, request):
        return self.execute(operations.operations_dashboard)


class LineStatusView(OperationMixin, APIView):
    def get(self, request):
        return self.execute(operations.line_status)


class CalendarTemplateView(OperationMixin, APIView):
    permission_classes = [MaintenanceTeam]

    def get(self, request):
        return self.execute(preventive.calendar_template)


class ManagersView(OperationMixin, APIView):
    def get(self, request):
        return self.execute(operations.managers)


class PurchasePartsView(OperationMixin, APIView):
    def get(self, request):
        return self.execute(operations.purchase_parts)

class ActivityLogView(OperationMixin, APIView):
    permission_classes = [MaintenanceTeam]

    def get(self, request):
        return self.execute(operations.activity_log)

class StockReceiptView(OperationMixin, APIView):
    permission_classes = [MaintenanceTeam]

    def post(self, request):
        return self.execute(operations.stock_receipt)

