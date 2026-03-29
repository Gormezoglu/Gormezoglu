from django.urls import path
from . import views

urlpatterns = [
    path('',              views.TenderListView.as_view(),   name='tender-list'),
    path('add/',          views.TenderCreateView.as_view(), name='tender-add'),
    path('<int:pk>/',     views.TenderDetailView.as_view(), name='tender-detail'),
    path('<int:pk>/edit/',   views.TenderUpdateView.as_view(), name='tender-edit'),
    path('<int:pk>/delete/', views.TenderDeleteView.as_view(), name='tender-delete'),
]
