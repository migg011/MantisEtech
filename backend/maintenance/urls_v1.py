"""Aliases da API v1 anterior, atendidos pelos mesmos casos de uso do Mantis."""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views, viewsets

router = DefaultRouter()
router.include_format_suffixes = False
router.register('users', viewsets.UserViewSet, basename='v1-user')
router.register('sectors', viewsets.SectorViewSet, basename='v1-sector')
router.register('lines', viewsets.LineViewSet, basename='v1-line')
router.register('equipment-types', viewsets.EquipmentTypeViewSet, basename='v1-equipment-type')
router.register('equipments', viewsets.EquipmentViewSet, basename='v1-equipment')
router.register('equipment-attachments', viewsets.EquipmentAttachmentViewSet, basename='v1-equipment-attachment')
router.register('problem-types', viewsets.ProblemTypeViewSet, basename='v1-problem-type')
router.register('work-orders', viewsets.WorkOrderViewSet, basename='v1-work-order')
router.register('line-pendencies', viewsets.LinePendencyViewSet, basename='v1-line-pendency')
router.register('material-categories', viewsets.MaterialCategoryViewSet, basename='v1-material-category')
router.register('spare-parts', viewsets.SparePartViewSet, basename='v1-spare-part')
router.register('stock-movements', viewsets.StockMovementViewSet, basename='v1-stock-movement')
router.register('spare-part-technicals', viewsets.TechnicalReadViewSet, basename='v1-spare-part-technical')
router.register('purchase-requests', viewsets.PurchaseRequestViewSet, basename='v1-purchase-request')
router.register('part-requisitions', viewsets.PartRequisitionViewSet, basename='v1-part-requisition')
router.register('preventive-checklists', viewsets.PreventiveChecklistViewSet, basename='v1-preventive-checklist')
router.register('equipment-preventives', viewsets.EquipmentPreventiveViewSet, basename='v1-equipment-preventive')
router.register('preventive-executions', viewsets.PreventiveExecutionViewSet, basename='v1-preventive-execution')
router.register('preventive-orders', viewsets.PreventiveOrderViewSet, basename='v1-preventive-order')

urlpatterns = [
    path('auth/login/', views.LoginView.as_view(), name='v1-login'),
    path('auth/me/', views.CurrentUserView.as_view(), name='v1-me'),
    path('health/check/', views.HealthView.as_view(), name='v1-health'),
    path('', include(router.urls)),
    path('', include('maintenance.urls')),
]
