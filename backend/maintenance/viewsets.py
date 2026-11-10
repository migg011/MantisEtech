"""ViewSets dos recursos Mantis. Toda escrita passa pelos serviços do domínio."""
from rest_framework.decorators import action
from rest_framework.viewsets import GenericViewSet, ReadOnlyModelViewSet

from . import filters, serializers
from .models import EquipmentAttachment, PartRequisition, SparePartTechnical, StockMovement
from .permissions import ActiveAccount, MaintenanceTeam
from .services import operations, preventive, preventive_orders
from .views import OperationMixin


class EquipmentAttachmentViewSet(OperationMixin, ReadOnlyModelViewSet):
    serializer_class = serializers.EquipmentAttachmentSerializer

    def get_queryset(self):
        return EquipmentAttachment.objects.filter(equipment__in=operations.visible_equipment(self.request.user))


class StockMovementViewSet(OperationMixin, ReadOnlyModelViewSet):
    permission_classes = [MaintenanceTeam]
    serializer_class = serializers.StockMovementSerializer
    queryset = StockMovement.objects.select_related('spare_part', 'performed_by').order_by('-created_at', '-pk')


class PartRequisitionViewSet(OperationMixin, ReadOnlyModelViewSet):
    permission_classes = [MaintenanceTeam]
    serializer_class = serializers.PartRequisitionSerializer
    queryset = PartRequisition.objects.select_related('work_order', 'spare_part', 'requester').order_by('-created_at',
                                                                                                       '-pk')


class TechnicalReadViewSet(OperationMixin, ReadOnlyModelViewSet):
    permission_classes = [MaintenanceTeam]
    serializer_class = serializers.SparePartTechnicalSerializer
    queryset = SparePartTechnical.objects.select_related('spare_part').order_by('pk')


class MantisViewSet(OperationMixin, GenericViewSet):
    permission_classes = [ActiveAccount]
    pagination_class = None  # O Angular recebe listas, sem envelope de paginação.


class UserViewSet(MantisViewSet):
    serializer_class = serializers.UserSerializer
    filterset_class = filters.UserFilter

    def list(self, request):
        return self.execute(operations.users)

    def create(self, request):
        return self.execute(operations.users)

    def partial_update(self, request, pk=None):
        return self.execute(operations.users, pk=pk)

    @action(detail=True, methods=['patch'], url_path='status')
    def status(self, request, pk=None):
        return self.execute(operations.users, pk=pk, action='status')

    @action(detail=True, methods=['patch'], url_path='password')
    def password(self, request, pk=None):
        return self.execute(operations.users, pk=pk, action='password')


class SectorViewSet(MantisViewSet):
    serializer_class = serializers.SectorSerializer
    filterset_class = filters.SectorFilter

    def list(self, request):
        return self.execute(operations.sectors)

    def create(self, request):
        return self.execute(operations.sectors)

    def partial_update(self, request, pk=None):
        return self.execute(operations.sectors, pk=pk)

    def destroy(self, request, pk=None):
        return self.execute(operations.sectors, pk=pk)


class LineViewSet(MantisViewSet):
    serializer_class = serializers.LineSerializer
    filterset_class = filters.LineFilter

    def list(self, request):
        return self.execute(operations.lines)

    def create(self, request):
        return self.execute(operations.lines)

    def partial_update(self, request, pk=None):
        return self.execute(operations.edit_line, pk=pk)

    @action(detail=True, methods=['post'], url_path='equipment')
    def equipment(self, request, pk=None):
        return self.execute(operations.allocate_equipment, pk=pk)

    @action(detail=True, methods=['delete'], url_path='equipment/(?P<equipment_pk>[^/.]+)')
    def remove_equipment(self, request, pk=None, equipment_pk=None):
        return self.execute(operations.remove_equipment, pk=pk, equipment_pk=equipment_pk)

    @action(detail=True, methods=['post'], url_path='dismantle')
    def dismantle(self, request, pk=None):
        return self.execute(operations.dismantle_line, pk=pk)


class EquipmentTypeViewSet(MantisViewSet):
    serializer_class = serializers.EquipmentTypeSerializer

    def list(self, request):
        return self.execute(operations.equipment_types)


class EquipmentViewSet(MantisViewSet):
    serializer_class = serializers.EquipmentSerializer
    filterset_class = filters.EquipmentFilter

    def list(self, request):
        return self.execute(operations.equipment)

    def create(self, request):
        return self.execute(operations.equipment)

    def partial_update(self, request, pk=None):
        return self.execute(operations.equipment, pk=pk)

    def destroy(self, request, pk=None):
        return self.execute(operations.equipment, pk=pk)

    @action(detail=True, methods=['get'], url_path='movements')
    def movements(self, request, pk=None):
        return self.execute(operations.movements, pk=pk)

    @action(detail=True, methods=['post'], url_path='transfer')
    def transfer(self, request, pk=None):
        return self.execute(operations.transfer_equipment, pk=pk)

    @action(detail=True, methods=['get'], url_path='attachments')
    def attachments(self, request, pk=None):
        return self.execute(operations.attachments, pk=pk)

    @action(detail=True, methods=['put'], url_path='attachments/(?P<kind>[^/.]+)')
    def save_attachment(self, request, pk=None, kind=None):
        return self.execute(operations.attachments, pk=pk, kind=kind)

    @action(detail=True, methods=['get'], url_path='attachments/(?P<kind>[^/.]+)/download')
    def download_attachment(self, request, pk=None, kind=None):
        return self.execute(operations.attachments, pk=pk, kind=kind, download=True)


class ProblemTypeViewSet(MantisViewSet):
    serializer_class = serializers.ProblemTypeSerializer

    def list(self, request):
        return self.execute(operations.problem_types)

    def create(self, request):
        return self.execute(operations.problem_types)

    def partial_update(self, request, pk=None):
        return self.execute(operations.problem_types, pk=pk)

    def destroy(self, request, pk=None):
        return self.execute(operations.problem_types, pk=pk)


class WorkOrderViewSet(MantisViewSet):
    serializer_class = serializers.WorkOrderSerializer
    filterset_class = filters.WorkOrderFilter

    def list(self, request):
        return self.execute(operations.work_orders)

    def create(self, request):
        return self.execute(operations.work_orders)

    def retrieve(self, request, pk=None):
        return self.execute(operations.work_orders, pk=pk)

    def partial_update(self, request, pk=None):
        return self.execute(operations.work_orders, pk=pk)

    @action(detail=True, methods=['post'], url_path='start')
    def start(self, request, pk=None):
        return self.execute(operations.start_service, pk=pk)

    @action(detail=True, methods=['get', 'post'], url_path='pendencies')
    def pendencies(self, request, pk=None):
        return self.execute(operations.work_order_pendencies, pk=pk)

    @action(detail=True, methods=['get'], url_path='spare-parts')
    def spare_parts(self, request, pk=None):
        return self.execute(operations.work_order_parts, pk=pk)

    @action(detail=True, methods=['get', 'post'], url_path='purchase-requests')
    def purchase_requests(self, request, pk=None):
        return self.execute(operations.work_order_purchases, pk=pk)

    @action(detail=True, methods=['get', 'post'], url_path='part-requisitions')
    def part_requisitions(self, request, pk=None):
        return self.execute(operations.work_order_part_requisitions, pk=pk)


class LinePendencyViewSet(MantisViewSet):
    serializer_class = serializers.LinePendencySerializer
    filterset_class = filters.LinePendencyFilter

    def list(self, request):
        return self.execute(operations.line_pendencies)

    def partial_update(self, request, pk=None):
        return self.execute(operations.line_pendencies, pk=pk)


class MaterialCategoryViewSet(MantisViewSet):
    serializer_class = serializers.MaterialCategorySerializer

    def list(self, request):
        return self.execute(operations.material_categories)

    def create(self, request):
        return self.execute(operations.material_categories)

    def partial_update(self, request, pk=None):
        return self.execute(operations.material_categories, pk=pk)

    def destroy(self, request, pk=None):
        return self.execute(operations.material_categories, pk=pk)


class SparePartViewSet(MantisViewSet):
    serializer_class = serializers.SparePartSerializer
    filterset_class = filters.SparePartFilter

    def list(self, request):
        return self.execute(operations.parts)

    def create(self, request):
        return self.execute(operations.parts)

    def partial_update(self, request, pk=None):
        return self.execute(operations.parts, pk=pk)

    def destroy(self, request, pk=None):
        return self.execute(operations.parts, pk=pk)

    @action(detail=False, methods=['get'], url_path='inventory')
    def inventory(self, request):
        return self.execute(operations.parts_inventory)

    @action(detail=False, methods=['get'], url_path='inventory\\.csv')
    def inventory_csv(self, request):
        return self.execute(operations.parts_inventory, output_format='csv')

    @action(detail=True, methods=['get', 'post'], url_path='stock-movements')
    def stock_movements(self, request, pk=None):
        return self.execute(operations.stock_movements, pk=pk)

    @action(detail=True, methods=['get'], url_path='photo')
    def photo(self, request, pk=None):
        return self.execute(operations.part_photo, pk=pk)

    @action(detail=True, methods=['get'], url_path='details')
    def details(self, request, pk=None):
        return self.execute(operations.part_details, pk=pk)


class SparePartTechnicalViewSet(MantisViewSet):
    serializer_class = serializers.SparePartTechnicalSerializer

    @action(detail=True, methods=['get', 'put'], url_path='technical')
    def technical(self, request, pk=None):
        return self.execute(operations.technical_sheet, pk=pk)

    @action(detail=True, methods=['post'], url_path='validate')
    def validate(self, request, pk=None):
        return self.execute(operations.technical_sheet, pk=pk, validate=True)


class PurchaseRequestViewSet(MantisViewSet):
    serializer_class = serializers.PurchaseRequestSerializer
    filterset_class = filters.PurchaseFilter

    def list(self, request):
        return self.execute(operations.purchases)

    def create(self, request):
        return self.execute(operations.purchases)

    def retrieve(self, request, pk=None):
        return self.execute(operations.purchases, pk=pk)

    def partial_update(self, request, pk=None):
        return self.execute(operations.purchases, pk=pk)

    @action(detail=True, methods=['post'], url_path='submit')
    def submit(self, request, pk=None):
        return self.execute(operations.submit_purchase, pk=pk)

    @action(detail=True, methods=['post'], url_path='decision')
    def decision(self, request, pk=None):
        return self.execute(operations.decide_purchase, pk=pk)

    @action(detail=True, methods=['get'], url_path='export\\.csv')
    def export_csv(self, request, pk=None):
        return self.execute(operations.export_purchase, pk=pk)


class PreventiveChecklistViewSet(MantisViewSet):
    serializer_class = serializers.PreventiveChecklistSerializer

    def list(self, request):
        return self.execute(preventive.checklist)

    @action(detail=False, methods=['put'], url_path='save-checklist')
    def save_checklist(self, request):
        return self.execute(preventive.checklist)

    @action(detail=False, methods=['get'], url_path='document')
    def document(self, request):
        return self.execute(preventive.document)


class EquipmentPreventiveViewSet(MantisViewSet):
    serializer_class = serializers.EquipmentPreventiveSerializer
    filterset_class = filters.PreventiveScheduleFilter

    def list(self, request):
        return self.execute(preventive.schedules)

    @action(detail=True, methods=['post'], url_path='complete')
    def complete(self, request, pk=None):
        return self.execute(preventive.complete, pk=pk)


class PreventiveExecutionViewSet(MantisViewSet):
    serializer_class = serializers.PreventiveExecutionSerializer

    def list(self, request):
        return self.execute(preventive.history)


class PreventiveOrderViewSet(MantisViewSet):
    serializer_class = serializers.PreventiveOrderSerializer
    filterset_class = filters.PreventiveOrderFilter

    def list(self, request):
        return self.execute(preventive_orders.orders)

    def create(self, request):
        return self.execute(preventive_orders.orders)

    def retrieve(self, request, pk=None):
        return self.execute(preventive_orders.details, pk=pk)

    def partial_update(self, request, pk=None):
        return self.execute(preventive_orders.details, pk=pk)

    @action(detail=False, methods=['get'], url_path='technicians')
    def technicians(self, request):
        return self.execute(preventive_orders.technicians)

    @action(detail=True, methods=['post'], url_path='complete')
    def complete(self, request, pk=None):
        return self.execute(preventive_orders.complete, pk=pk)

    @action(detail=True, methods=['post'], url_path='cancel')
    def cancel(self, request, pk=None):
        return self.execute(preventive_orders.cancel, pk=pk)

    @action(detail=True, methods=['get'], url_path='document')
    def document(self, request, pk=None):
        return self.execute(preventive_orders.document, pk=pk)
