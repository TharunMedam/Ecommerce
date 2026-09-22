from django.urls import path
from .views import *
urlpatterns=[path('session/',Session.as_view()),path('auth/<str:action>/',Auth.as_view()),path('catalog/',Catalog.as_view()),path('cart/',Cart.as_view()),path('orders/',Orders.as_view()),path('orders/<uuid:pk>/cancel/',CancelOrder.as_view()),path('orders/<uuid:pk>/verify/',VerifyPayment.as_view()),path('payments/webhook/',Webhook.as_view()),path('feedback/',FeedbackView.as_view()),path('owner/<str:section>/',Owner.as_view())]
