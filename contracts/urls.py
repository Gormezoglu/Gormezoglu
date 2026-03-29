from django.urls import path
from . import views

urlpatterns = [
    path('', views.DashboardView.as_view(), name='dashboard'),
    path('contracts/', views.ContractListView.as_view(), name='contract-list'),
    path('contracts/add/', views.ContractCreateView.as_view(), name='contract-add'),
    path('contracts/<int:pk>/', views.ContractDetailView.as_view(), name='contract-detail'),
    path('contracts/<int:pk>/edit/', views.ContractUpdateView.as_view(), name='contract-edit'),
    path('contracts/<int:pk>/delete/', views.ContractDeleteView.as_view(), name='contract-delete'),
    # Payments
    path('payments/', views.PaymentOverviewView.as_view(), name='payment-overview'),
    path('payments/<int:pk>/pay/', views.PaymentMarkPaidView.as_view(), name='payment-pay'),
    path('payments/<int:pk>/cancel/', views.PaymentCancelView.as_view(), name='payment-cancel'),
]
