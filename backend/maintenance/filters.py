"""Filtros de consulta; autorização por perfil/linha é aplicada antes do filtro."""
import django_filters as filters
from django.db.models import Q

from .models import (
    Equipment, EquipmentPreventive, Line, LinePendency, PreventiveOrder, ProblemType,
    PurchaseRequest, Sector, SparePart, User, WorkOrder,
)


class UserFilter(filters.FilterSet):
    q = filters.CharFilter(method='search')

    def search(self, queryset, name, value):
        return queryset.filter(Q(name__icontains=value) | Q(registration__icontains=value))

    class Meta:
        model = User
        fields = ['role', 'active']


class SectorFilter(filters.FilterSet):
    q = filters.CharFilter(field_name='name', lookup_expr='icontains')

    class Meta:
        model = Sector
        fields = ['active']


class LineFilter(filters.FilterSet):
    sectorId = filters.NumberFilter(field_name='sector_id', min_value=1)
    q = filters.CharFilter(field_name='name', lookup_expr='icontains')

    class Meta:
        model = Line
        fields = ['active']


class EquipmentFilter(filters.FilterSet):
    lineId = filters.NumberFilter(field_name='line_id', min_value=1)
    sectorId = filters.NumberFilter(field_name='sector_id', min_value=1)
    equipmentTypeId = filters.NumberFilter(field_name='equipment_type_id', min_value=1)
    available = filters.BooleanFilter(field_name='line', lookup_expr='isnull')
    q = filters.CharFilter(method='search')

    def search(self, queryset, name, value):
        return queryset.filter(Q(name__icontains=value) | Q(model__icontains=value) | Q(serial__icontains=value) |
                               Q(asset_number__icontains=value))

    class Meta:
        model = Equipment
        fields = []


class WorkOrderFilter(filters.FilterSet):
    lineId = filters.NumberFilter(field_name='equipment__line_id', min_value=1)
    equipmentId = filters.NumberFilter(field_name='equipment_id', min_value=1)

    class Meta:
        model = WorkOrder
        fields = ['status', 'priority']


class LinePendencyFilter(filters.FilterSet):
    lineId = filters.NumberFilter(field_name='line_id', min_value=1)

    class Meta:
        model = LinePendency
        fields = ['status', 'priority']


class SparePartFilter(filters.FilterSet):
    categoryId = filters.NumberFilter(field_name='categories__pk', distinct=True, min_value=1)
    equipmentId = filters.NumberFilter(field_name='compatibility__equipment_id', distinct=True, min_value=1)
    q = filters.CharFilter(method='search')

    def search(self, queryset, name, value):
        return queryset.filter(
            Q(part_number__icontains=value) | Q(description__icontains=value) | Q(manufacturer__icontains=value))

    class Meta:
        model = SparePart
        fields = []


class PurchaseFilter(filters.FilterSet):
    class Meta:
        model = PurchaseRequest
        fields = ['status', 'purchase_type']


class PreventiveScheduleFilter(filters.FilterSet):
    equipmentId = filters.NumberFilter(field_name='equipment_id', min_value=1)

    class Meta:
        model = EquipmentPreventive
        fields = ['frequency']


class PreventiveOrderFilter(filters.FilterSet):
    equipmentId = filters.NumberFilter(field_name='schedule__equipment_id', min_value=1)

    class Meta:
        model = PreventiveOrder
        fields = ['status', 'frequency']


def apply_filters(filter_class, parameters, queryset):
    query_filter = filter_class(data=parameters, queryset=queryset)
    if not query_filter.is_valid():
        from .exceptions import ApiError
        raise ApiError('Filtros de consulta inválidos.', details=dict(query_filter.errors))
    return query_filter.qs
