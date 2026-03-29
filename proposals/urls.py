from django.urls import path
from . import views

urlpatterns = [
    path('',                    views.ProposalListView.as_view(),   name='proposal-list'),
    path('add/',                views.ProposalCreateView.as_view(), name='proposal-add'),
    path('<int:pk>/',           views.ProposalDetailView.as_view(), name='proposal-detail'),
    path('<int:pk>/edit/',      views.ProposalUpdateView.as_view(), name='proposal-edit'),
    path('<int:pk>/delete/',    views.ProposalDeleteView.as_view(), name='proposal-delete'),
    path('<int:pk>/send/',      views.ProposalSendView.as_view(),   name='proposal-send'),
    path('<int:pk>/accept/',    views.ProposalAcceptView.as_view(), name='proposal-accept'),
    path('<int:pk>/reject/',    views.ProposalRejectView.as_view(), name='proposal-reject'),
]
