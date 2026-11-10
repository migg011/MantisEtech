"""Router do domínio: contratos Angular e recursos DRF na mesma implementação."""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views, viewsets

router = DefaultRouter(trailing_slash=False)
router.include_format_suffixes = False
router.register('users', viewsets.UserViewSet, basename='users')
router.register('sectors', viewsets.SectorViewSet, basename='sectors')
router.register('lines', viewsets.LineViewSet, basename='lines')
router.register('equipment-types', viewsets.EquipmentTypeViewSet, basename='equipment-types')
router.register('equipment', viewsets.EquipmentViewSet, basename='equipment')
router.register('problem-types', viewsets.ProblemTypeViewSet, basename='problem-types')
router.register('orders', viewsets.WorkOrderViewSet, basename='orders')
router.register('line-pendencies', viewsets.LinePendencyViewSet, basename='line-pendencies')
router.register('part-categories', viewsets.MaterialCategoryViewSet, basename='part-categories')
router.register('spare-parts', viewsets.SparePartViewSet, basename='spare-parts')
router.register('spare-purchase/parts', viewsets.SparePartTechnicalViewSet, basename='spare-purchase-parts')
router.register('spare-purchase/requests', viewsets.PurchaseRequestViewSet, basename='spare-purchase-requests')
router.register('preventive-checklists', viewsets.PreventiveChecklistViewSet, basename='preventive-checklists')
router.register('preventive-schedules', viewsets.EquipmentPreventiveViewSet, basename='preventive-schedules')
router.register('preventive-executions', viewsets.PreventiveExecutionViewSet, basename='preventive-executions')
router.register('preventive-orders', viewsets.PreventiveOrderViewSet, basename='preventive-orders')

urlpatterns = [
    path('auth/login', views.LoginView.as_view(), name='login'),
    path('health', views.HealthView.as_view(), name='health'),
    path('me', views.CurrentUserView.as_view(), name='current-user'),
    path('dashboard', views.DashboardView.as_view(), name='dashboard'),
    path('line-status', views.LineStatusView.as_view(), name='line-status'),
    path('preventive-calendar-template', views.CalendarTemplateView.as_view(), name='calendar-template'),
    path('spare-purchase/managers', views.ManagersView.as_view(), name='managers'),
    path('spare-purchase/parts', views.PurchasePartsView.as_view(), name='purchase-parts'),
    path('preventive-checklists',
         viewsets.PreventiveChecklistViewSet.as_view({'get': 'list', 'put': 'save_checklist'})),
    path('', include(router.urls)),
]
