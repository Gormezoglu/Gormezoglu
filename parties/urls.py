from django.urls import path
from . import views

urlpatterns = [
    path('', views.PartyListView.as_view(), name='party-list'),
    path('add/', views.PartyCreateView.as_view(), name='party-add'),
    path('<int:pk>/', views.PartyDetailView.as_view(), name='party-detail'),
    path('<int:pk>/edit/', views.PartyUpdateView.as_view(), name='party-edit'),
    path('<int:pk>/delete/', views.PartyDeleteView.as_view(), name='party-delete'),
]
