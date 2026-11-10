"""Serialização explícita dos recursos e validação compartilhada dos cadastros Mantis.

Os serializers de leitura não aceitam escrita. As regras existentes dos cadastros
são reaproveitadas por ValidacaoFormularioSerializer, sem renderizar formulários.
"""
from decimal import Decimal

from rest_framework import serializers

from . import models


class LoginSerializer(serializers.Serializer):
    registration = serializers.CharField(max_length=50)
    password = serializers.CharField(write_only=True, trim_whitespace=False)


class FormValidationSerializer(serializers.Serializer):
    """Preserva validadores dos cadastros enquanto integra a validação ao DRF."""

    def to_internal_value(self, data):
        form = self.context['form']
        if not form.is_valid():
            raise serializers.ValidationError({
                field: [str(message) for message in messages]
                for field, messages in form.errors.items()
            })
        return form.cleaned_data


class AllocationInputSerializer(serializers.Serializer):
    equipmentId = serializers.IntegerField(min_value=1)
    position = serializers.IntegerField(min_value=1)


class TransferInputSerializer(serializers.Serializer):
    originSectorId = serializers.IntegerField(min_value=1)
    destinationSectorId = serializers.IntegerField(min_value=1)
    reason = serializers.CharField(min_length=3, max_length=500)


class StockInputSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=['INICIAL', 'ENTRADA', 'SAIDA', 'AJUSTE'])
    quantity = serializers.DecimalField(max_digits=14, decimal_places=3, min_value=Decimal('0'))
    requestKey = serializers.UUIDField()
    note = serializers.CharField(max_length=500, required=False, allow_blank=True)
    movementDate = serializers.DateField(required=False)
    supplier = serializers.CharField(max_length=160, required=False, allow_blank=True)
    documentReference = serializers.CharField(max_length=100, required=False, allow_blank=True)


class PartRequisitionInputSerializer(serializers.Serializer):
    sparePartId = serializers.IntegerField(min_value=1)
    quantity = serializers.DecimalField(max_digits=14, decimal_places=3, min_value=Decimal('0'))
    note = serializers.CharField(max_length=5000, required=False, allow_blank=True)


INPUT_BY_OPERATION = {
    'allocate_equipment': AllocationInputSerializer,
    'transfer_equipment': TransferInputSerializer,
    'stock_movements': StockInputSerializer,
    'work_order_part_requisitions': PartRequisitionInputSerializer,
}


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.User
        fields = ['id', 'last_login', 'name', 'registration', 'role', 'line', 'active', 'created_at']
        read_only_fields = fields


class SectorSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Sector
        fields = ['id', 'code', 'name', 'description', 'active', 'created_at']
        read_only_fields = fields


class LineSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Line
        fields = ['id', 'code', 'name', 'description', 'sector', 'active', 'created_at']
        read_only_fields = fields


class EquipmentTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.EquipmentType
        fields = ['id', 'name']
        read_only_fields = fields


class EquipmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Equipment
        fields = ['id', 'equipment_type', 'name', 'sector', 'model_number', 'model', 'serial', 'manufacturer',
                  'manufacturing_date', 'manufacturing_date_text', 'length_mm', 'width_mm', 'height_mm', 'weight_kg',
                  'voltage_v', 'frequency_hz', 'current_a', 'power_w', 'pneumatic_pressure_bar', 'asset_number',
                  'description', 'process_description', 'line', 'position', 'active', 'created_at']
        read_only_fields = fields


class EquipmentAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.EquipmentAttachment
        fields = ['id', 'equipment', 'kind', 'filename', 'mime_type', 'size_bytes', 'uploaded_by', 'created_at']
        read_only_fields = fields


class EquipmentMovementSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.EquipmentMovement
        fields = ['id', 'equipment', 'from_line', 'from_position', 'to_line', 'to_position', 'action', 'from_sector',
                  'to_sector', 'reason', 'performed_by', 'created_at']
        read_only_fields = fields


class ProblemTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.ProblemType
        fields = ['id', 'name', 'equipment_type', 'priority', 'active']
        read_only_fields = fields


class WorkOrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.WorkOrder
        fields = ['id', 'equipment', 'opened_by', 'assigned_to', 'priority', 'status', 'problem',
                  'occurrence_description', 'problem_type', 'root_cause', 'corrective_action', 'preventive_action',
                  'started_at', 'finished_at', 'downtime_seconds', 'created_at']
        read_only_fields = fields


class LinePendencySerializer(serializers.ModelSerializer):
    class Meta:
        model = models.LinePendency
        fields = ['id', 'work_order', 'line', 'equipment', 'equipment_serial', 'description', 'priority', 'status',
                  'created_by', 'created_at', 'resolved_by', 'resolved_at', 'resolution']
        read_only_fields = fields


class MaterialCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = models.MaterialCategory
        fields = ['id', 'name', 'name_key', 'description', 'active']
        read_only_fields = fields


class SparePartSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.SparePart
        fields = ['id', 'code', 'description', 'part_number', 'manufacturer', 'category', 'unit', 'stock_quantity',
                  'minimum_stock', 'maximum_stock', 'reorder_point', 'storage_location', 'preferred_supplier',
                  'average_cost', 'last_cost', 'average_cost_currency', 'last_cost_currency', 'photo_filename',
                  'photo_mime', 'datasheet_filename', 'active', 'created_at', 'updated_at']
        read_only_fields = fields


class StockMovementSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.StockMovement
        fields = ['id', 'spare_part', 'kind', 'quantity', 'previous_quantity', 'delta', 'resulting_quantity',
                  'performed_by', 'note', 'movement_date', 'supplier', 'document_reference', 'request_key',
                  'created_at']
        read_only_fields = fields


class SparePartTechnicalSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.SparePartTechnical
        fields = ['spare_part', 'fiscal_status', 'fiscal_validated_by', 'fiscal_validated_at', 'updated_at',
                  'description_en', 'ncm', 'pli_description', 'description_pt', 'classification',
                  'independent_function', 'connection_details', 'useful_life', 'asset_classification', 'main_function',
                  'secondary_function', 'raw_material', 'intended_use', 'application_machine', 'mechanical_electrical',
                  'current_type', 'power', 'voltage', 'amperage', 'picture_reference']
        read_only_fields = fields


class PurchaseRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.PurchaseRequest
        fields = ['id', 'purchase_type', 'status', 'requester', 'manager', 'work_order', 'equipment',
                  'equipment_serial', 'justification', 'priority', 'manager_comment', 'submitted_at', 'decided_at',
                  'created_at', 'updated_at']
        read_only_fields = fields


class PurchaseItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.PurchaseItem
        fields = ['id', 'request', 'spare_part', 'quantity', 'item_note', 'technical_snapshot']
        read_only_fields = fields


class PurchaseEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.PurchaseEvent
        fields = ['id', 'request', 'actor', 'action', 'details', 'created_at']
        read_only_fields = fields


class PartRequisitionSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.PartRequisition
        fields = ['id', 'work_order', 'equipment', 'equipment_serial', 'spare_part', 'quantity', 'requester', 'note',
                  'created_at']
        read_only_fields = fields


class PreventiveChecklistSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.PreventiveChecklist
        fields = ['id', 'equipment_type', 'frequency', 'items']
        read_only_fields = fields


class EquipmentPreventiveSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.EquipmentPreventive
        fields = ['id', 'equipment', 'frequency', 'next_due', 'last_performed', 'active', 'checklist_items']
        read_only_fields = fields


class PreventiveExecutionSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.PreventiveExecution
        fields = ['id', 'schedule', 'performed_date', 'previous_due', 'next_due', 'technician', 'notes', 'created_at',
                  'order']
        read_only_fields = fields


class PreventiveOrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.PreventiveOrder
        fields = ['id', 'schedule', 'status', 'expected_due', 'planned_date', 'planned_time', 'recurrence_basis',
                  'frequency', 'equipment_snapshot', 'items', 'results', 'safety_instructions', 'parts', 'notes',
                  'performed_date', 'performed_time', 'assigned_to', 'assigned_name', 'created_by', 'created_at',
                  'finished_by', 'executor_name', 'finished_at', 'cancellation_reason', 'revision']
        read_only_fields = fields
