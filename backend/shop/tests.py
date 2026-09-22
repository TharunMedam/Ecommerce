import uuid
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import TestCase,override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework.exceptions import ValidationError
from .models import *
from .services import shipping,checkout,expire_orders,settle
User=get_user_model()
class StoreTests(TestCase):
    def setUp(self):
        self.user=User.objects.create_user('customer@example.test','customer@example.test','Strong-test-pass-731',first_name='Customer')
        self.other=User.objects.create_user('other@example.test',password='Strong-test-pass-732')
        self.owner=User.objects.create_user('owner@example.test',password='Strong-test-pass-733',is_staff=True)
        self.c=APIClient();self.c.force_authenticate(self.user)
        self.cat=Category.objects.create(name='Nuts',name_te='గింజలు',slug='nuts')
        self.p=Product.objects.create(category=self.cat,name='Almonds',name_te='బాదం',verified=True)
        self.v=Variant.objects.create(product=self.p,sku='ALM-250',label='250 g',price=400,stock=10)
        self.s=StoreSettings.get();self.s.accepting_orders=True;self.s.details_verified=True;self.s.phone='9876543210';self.s.address='Example pickup address';self.s.delivery_fee=50;self.s.delivery_pincodes=['520001'];self.s.open_days=list(range(7));self.s.save()
        self.at=(timezone.localtime()+timedelta(days=1)).replace(hour=12,minute=0,second=0,microsecond=0)
    def payload(self,**kwargs):
        return {'idempotency_key':str(uuid.uuid4()),'fulfillment':'pickup','payment_method':'pay_at_pickup','contact_name':'Customer','phone':'9876543210','address':'','pincode':'','pickup_at':self.at.isoformat(),'expected_total':'400.00',**kwargs}
    def cart(self,qty=1): CartItem.objects.create(user=self.user,variant=self.v,quantity=qty)
    def test_exact_threshold(self):
        self.assertEqual(shipping(Decimal('800'),self.s,'delivery'),50)
        self.assertEqual(shipping(Decimal('800.01'),self.s,'delivery'),0)
        self.assertEqual(shipping(Decimal('1'),self.s,'pickup'),0)
    def test_customer_cannot_access_owner(self):
        for section in ['products','orders','settings','feedback']:
            self.assertEqual(self.c.get('/api/owner/'+section+'/').status_code,403)
        self.assertEqual(self.c.patch('/api/owner/settings/',{'free_delivery_above':0},format='json').status_code,403)
    def test_csrf_login_required(self):
        c=APIClient(enforce_csrf_checks=True)
        r=c.post('/api/auth/login/',{'email':self.user.email,'password':'Strong-test-pass-731'},format='json')
        self.assertEqual(r.status_code,403)
        csrf=c.get('/api/session/').data['csrf']
        r=c.post('/api/auth/login/',{'email':self.user.email,'password':'Strong-test-pass-731'},format='json',HTTP_X_CSRFTOKEN=csrf)
        self.assertEqual(r.status_code,200)
    def test_registration_cannot_grant_staff(self):
        c=APIClient();c.get('/api/session/')
        r=c.post('/api/auth/register/',{'name':'New','email':'new@example.test','password':'a-good-password-7841','is_staff':True},format='json')
        self.assertEqual(r.status_code,200)
        self.assertFalse(User.objects.get(username='new@example.test').is_staff)
    def test_customer_owner_login_rejected(self):
        c=APIClient()
        r=c.post('/api/auth/login/',{'email':self.user.email,'password':'Strong-test-pass-731','owner':True},format='json')
        self.assertEqual(r.status_code,400)
    def test_order_reserves_stock_and_is_idempotent(self):
        self.cart();data=self.payload()
        one=self.c.post('/api/orders/',data,format='json');two=self.c.post('/api/orders/',data,format='json')
        self.assertEqual(one.status_code,201,one.data);self.assertEqual(one.data['order']['id'],two.data['order']['id'])
        self.v.refresh_from_db();self.assertEqual(self.v.stock,9);self.assertEqual(Order.objects.count(),1)
        self.assertEqual(CartItem.objects.count(),0)
    def test_price_tampering_rejected(self):
        self.cart();r=self.c.post('/api/orders/',self.payload(expected_total='1.00'),format='json')
        self.assertEqual(r.status_code,400);self.assertEqual(Order.objects.count(),0)
        self.v.refresh_from_db();self.assertEqual(self.v.stock,10)
    def test_cash_on_delivery_rejected(self):
        self.cart();r=self.c.post('/api/orders/',self.payload(fulfillment='delivery',payment_method='cod'),format='json');self.assertEqual(r.status_code,400)
        r=self.c.post('/api/orders/',self.payload(fulfillment='delivery',payment_method='pay_at_pickup'),format='json');self.assertEqual(r.status_code,400)
    def test_stock_and_unverified_product_block_checkout(self):
        self.cart(11);r=self.c.post('/api/orders/',self.payload(expected_total='4400'),format='json');self.assertEqual(r.status_code,400)
        CartItem.objects.filter(user=self.user).update(quantity=1);self.p.verified=False;self.p.save()
        r=self.c.post('/api/orders/',self.payload(),format='json');self.assertEqual(r.status_code,400)
    def test_service_area_and_closed_hours(self):
        self.cart();r=self.c.post('/api/orders/',self.payload(fulfillment='delivery',payment_method='online',pincode='999999',address='Some other delivery address'),format='json');self.assertEqual(r.status_code,400)
        r=self.c.post('/api/orders/',self.payload(pickup_at=self.at.replace(hour=23).isoformat()),format='json');self.assertEqual(r.status_code,400)
    def test_cancel_restores_stock_once(self):
        self.cart();r=self.c.post('/api/orders/',self.payload(),format='json');oid=r.data['order']['id']
        self.assertEqual(self.c.post(f'/api/orders/{oid}/cancel/',{},format='json').status_code,200)
        self.assertEqual(self.c.post(f'/api/orders/{oid}/cancel/',{},format='json').status_code,400)
        self.v.refresh_from_db();self.assertEqual(self.v.stock,10)
    def test_order_isolation(self):
        self.cart();r=self.c.post('/api/orders/',self.payload(),format='json');oid=r.data['order']['id']
        self.c.force_authenticate(self.other)
        self.assertEqual(self.c.get('/api/orders/').data,[])
        self.assertEqual(self.c.post(f'/api/orders/{oid}/cancel/',{},format='json').status_code,404)
    def test_feedback_is_private_and_owner_can_reply(self):
        r=self.c.post('/api/feedback/',{'subject':'Packaging','message':'Please use paper packaging.'},format='json');self.assertEqual(r.status_code,201)
        fid=r.data['id'];self.c.force_authenticate(self.other);self.assertEqual(self.c.get('/api/feedback/').data,[])
        self.c.force_authenticate(self.owner);r=self.c.patch('/api/owner/feedback/',{'id':fid,'reply':'Thank you for the suggestion.','status':'resolved'},format='json');self.assertEqual(r.status_code,200)
        self.c.force_authenticate(self.user);self.assertEqual(self.c.get('/api/feedback/').data[0]['reply'],'Thank you for the suggestion.')
    def test_owner_can_edit_price_and_rule(self):
        self.c.force_authenticate(self.owner)
        r=self.c.patch('/api/owner/products/',{'id':self.p.id,'name_te':'బాదం పప్పు','variants':[{'id':self.v.id,'sku':self.v.sku,'label':'250 g','price':'450.00','stock':12}]},format='json')
        self.assertEqual(r.status_code,200,r.data);self.v.refresh_from_db();self.assertEqual(self.v.price,450)
        r=self.c.patch('/api/owner/settings/',{'free_delivery_above':'900','delivery_fee':'60'},format='json');self.assertEqual(r.status_code,200)
        self.assertEqual(AuditLog.objects.count(),2)
    @override_settings(RAZORPAY_KEY_ID='test',RAZORPAY_KEY_SECRET='secret')
    @patch('shop.services.gateway')
    def test_gateway_failure_rolls_back_inventory(self,gateway):
        gateway.side_effect=ValidationError('Unavailable')
        self.cart();r=self.c.post('/api/orders/',self.payload(payment_method='online'),format='json')
        self.assertEqual(r.status_code,400);self.v.refresh_from_db();self.assertEqual(self.v.stock,10);self.assertEqual(Order.objects.count(),0);self.assertEqual(CartItem.objects.count(),1)
    @patch('shop.services.gateway')
    def test_expiry_and_late_payment_requires_refund(self,gateway):
        self.cart();gateway.return_value={'id':'order_test'}
        r=self.c.post('/api/orders/',self.payload(payment_method='online'),format='json');self.assertEqual(r.status_code,201,r.data)
        o=Order.objects.get();o.expires_at=timezone.now()-timedelta(minutes=1);o.save();expire_orders();expire_orders()
        self.v.refresh_from_db();self.assertEqual(self.v.stock,10)
        gateway.return_value={'order_id':'order_test','amount':40000,'currency':'INR','status':'captured'}
        o=settle(o.pk,'pay_test');self.assertEqual(o.payment_status,'refund_required');self.assertEqual(o.status,'expired')
    @patch('shop.services.gateway')
    def test_capture_must_match_amount_currency_order(self,gateway):
        self.cart();gateway.return_value={'id':'order_test'};self.c.post('/api/orders/',self.payload(payment_method='online'),format='json');o=Order.objects.get()
        gateway.return_value={'order_id':'order_wrong','amount':1,'currency':'USD','status':'captured'}
        with self.assertRaises(ValidationError):settle(o.pk,'pay_test')
        o.refresh_from_db();self.assertEqual(o.payment_status,'unpaid')
        gateway.return_value={'order_id':'order_test','amount':40000,'currency':'INR','status':'captured'}
        o=settle(o.pk,'pay_test');self.assertEqual(o.payment_status,'paid');self.assertEqual(o.status,'placed')
    def test_paid_required_for_completion(self):
        self.cart();self.c.post('/api/orders/',self.payload(),format='json');o=Order.objects.get();o.status='ready';o.save();self.c.force_authenticate(self.owner)
        r=self.c.patch('/api/owner/orders/',{'id':str(o.pk),'status':'completed'},format='json');self.assertEqual(r.status_code,400)
        r=self.c.patch('/api/owner/orders/',{'id':str(o.pk),'mark_paid':True},format='json');self.assertEqual(r.status_code,200)
        r=self.c.patch('/api/owner/orders/',{'id':str(o.pk),'status':'completed'},format='json');self.assertEqual(r.status_code,200)
    def test_unknown_fee_not_treated_as_free(self):
        self.s.delivery_fee=None
        with self.assertRaises(ValidationError):shipping(Decimal('800'),self.s,'delivery')
