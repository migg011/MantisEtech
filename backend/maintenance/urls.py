"""Contratos /api consumidos pelo Angular; caminhos de API não usam barra final."""

from django.urls import path
from functools import wraps
from . import api, feeder_views
from . import preventive_views
from . import preventive_order_views


def route_view(view_value, methods):
    """Restringe métodos por endereço para impedir que uma função compartilhada aceite operações indevidas."""
    @wraps(view_value)
    def encaminhar(request_value, *args, **kwargs):
        """Restringe os métodos permitidos nesta URL antes de chamar a view compartilhada."""
        if request_value.method not in methods:
            response_value = api.error_value('Método não permitido.', 405)
            response_value['Allow'] = ', '.join(methods)
            return response_value
        return view_value(request_value, *args, **kwargs)
    return encaminhar

urlpatterns = [
    path('api/activity-log', api.activity_log),
    path('api/part-categories', route_view(api.material_categories, ['GET','POST'])),
    path('api/part-categories/<int:pk>', route_view(api.material_categories, ['PATCH','DELETE'])),
    path('api/dashboard', api.operational_dashboard),
    path('api/preventive-calendar-template', preventive_views.calendar_template_value),
    path('api/preventive-orders', preventive_order_views.orders_value),
    path('api/preventive-orders/technicians', preventive_order_views.technicians_value),
    path('api/preventive-orders/shifts', preventive_order_views.shifts_value),
    path('api/preventive-orders/<int:pk>', preventive_order_views.detail_value_value),
    path('api/preventive-orders/<int:pk>/complete', preventive_order_views.complete_value),
    path('api/preventive-orders/<int:pk>/cancel', preventive_order_views.cancel_value),
    path('api/preventive-orders/<int:pk>/document', preventive_order_views.document_value),
    path('api/preventive-checklists', preventive_views.checklist_value),
    path('api/preventive-checklists/document', preventive_views.document_value),
    path('api/preventive-schedules', preventive_views.schedules_value),
    path('api/preventive-schedules/<int:pk>/complete', preventive_views.complete_value),
    path('api/preventive-executions', preventive_views.history_value),
    # Entrada e identidade: o frontend recebe uma credencial e a envia nas chamadas protegidas.
    path('api/health', api.health),
    path('api/auth/login', api.login_value_value),
    path('api/me', api.me_value),
    path('api/operator-line', api.operator_line_value),
    # Organização física: setor, linha e montagem das máquinas dentro do mesmo setor.
    path('api/sectors', route_view(api.sectors_value, ['GET', 'POST'])),
    path('api/sectors/<int:pk>', route_view(api.sectors_value, ['PATCH', 'DELETE'])),
    path('api/sectors/<int:sector_id>/feeders', feeder_views.sector_feeders),
    path('api/sectors/<int:sector_id>/feeders/<int:feeder_id>/maintenance', feeder_views.feeder_maintenance),
    path('api/sectors/<int:sector_id>/feeders/<int:feeder_id>/preventives',
         feeder_views.feeder_maintenance, {'preventives_only': True}),
    path('api/lines', api.lines_value),
    path('api/lines/<int:pk>', api.edit_line),
    path('api/lines/<int:pk>/equipment', api.allocate_value),
    path('api/lines/<int:pk>/equipment/<int:equipment_pk>', api.remove_equipment_value),
    path('api/lines/<int:pk>/dismantle', api.dismantle_value),
    # Cadastro técnico e arquivos: anexos são downloads autenticados, não páginas Django.
    path('api/equipment-types', api.equipment_types_value),
    path('api/equipment-reference', api.equipment_reference_value),
    path('api/equipment', route_view(api.equipment_value_value, ['GET', 'POST'])),
    path('api/equipment/<int:pk>', route_view(api.equipment_value_value, ['PATCH', 'DELETE'])),
    path('api/equipment/<int:pk>/history', api.equipment_history),
    path('api/equipment/<int:pk>/movements', api.movements_value),
    path('api/equipment/<int:pk>/transfer', api.transfer_equipment),
    path('api/equipment/<int:pk>/attachments', route_view(api.attachments_value, ['GET'])),
    path('api/equipment/<int:pk>/attachments/<str:kind>', route_view(api.attachments_value, ['POST', 'PUT'])),
    path('api/equipment/<int:pk>/attachments/<str:kind>/download', route_view(api.attachments_value, ['GET']), {'download': True}),
    path('api/equipment/<int:pk>/attachments/<str:kind>/view', route_view(api.attachments_value, ['GET']), {'inline': True}),
    # Administração de contas e atendimento de manutenção.
    path('api/users', route_view(api.users_value, ['GET', 'POST'])),
    path('api/users/<int:pk>', route_view(api.users_value, ['PATCH'])),
    path('api/users/<int:pk>/status', route_view(api.users_value, ['PATCH']), {'action': 'status'}),
    path('api/users/<int:pk>/password', route_view(api.users_value, ['PATCH']), {'action': 'password'}),
    path('api/orders', route_view(api.orders, ['GET', 'POST'])),
    path('api/line-status', api.line_status),
    path('api/orders/<int:pk>', route_view(api.orders, ['GET', 'PATCH'])),
    path('api/orders/<int:pk>/start', api.start_order),
    path('api/orders/<int:pk>/pendencies', api.order_pendencies),
    path('api/line-pendencies', route_view(api.line_pendencies_value, ['GET'])),
    path('api/line-pendencies/<int:pk>', route_view(api.line_pendencies_value, ['PATCH'])),
    path('api/orders/<int:pk>/spare-parts', api.order_parts),
    path('api/orders/<int:pk>/purchase-requests', api.order_purchases),
    path('api/orders/<int:pk>/part-requisitions', api.order_requisitions),
    path('api/problem-types', route_view(api.problem_types_value, ['GET', 'POST'])),
    path('api/problem-types/<int:pk>', route_view(api.problem_types_value, ['PATCH', 'DELETE'])),
    # Reposição e compras: ficha reutilizável, solicitação, aprovação e exportação histórica.
    path('api/spare-parts/image-search', api.part_image_search),
    path('api/spare-parts/receipts', api.stock_receipt),
    path('api/spare-parts/inventory', api.parts_inventory),
    path('api/spare-parts/inventory.csv', api.parts_inventory, {'output_format':'csv'}),
    path('api/spare-parts/<int:pk>/stock-movements', api.stock_movements),
    path('api/spare-parts', route_view(api.parts_value, ['GET', 'POST'])),
    path('api/spare-parts/<int:pk>', route_view(api.parts_value, ['PATCH', 'DELETE'])),
    path('api/spare-parts/<int:pk>/photo', api.part_photo),
    path('api/spare-parts/<int:pk>/details', api.part_details),
    path('api/spare-purchase/managers', api.managers_value),
    path('api/spare-purchase/parts', api.purchase_parts_value),
    path('api/spare-purchase/parts/<int:pk>/technical', route_view(api.technical_value, ['GET', 'PUT'])),
    path('api/spare-purchase/parts/<int:pk>/validate', route_view(api.technical_value, ['POST']), {'validate': True}),
    path('api/spare-purchase/requests', route_view(api.purchases_value, ['GET', 'POST'])),
    path('api/spare-purchase/requests/<int:pk>', route_view(api.purchases_value, ['GET', 'PATCH'])),
    path('api/spare-purchase/requests/<int:pk>/submit', api.submit_purchase_value),
    path('api/spare-purchase/requests/<int:pk>/decision', api.decide_purchase_value),
    path('api/spare-purchase/requests/<int:pk>/export.csv', api.export_purchase_value),
]
