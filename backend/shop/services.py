from datetime import timedelta
from decimal import Decimal
import hashlib,hmac,requests
from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from .models import *

def shipping(subtotal,store,fulfillment):
    if fulfillment == 'pickup': return Decimal('0.00')
    if subtotal > store.free_delivery_above: return Decimal('0.00')
    if store.delivery_fee is None: raise ValidationError('Delivery fee is awaiting store confirmation. Choose pickup or contact the store.')
    return store.delivery_fee

def release(order,reason='cancelled'):
    if order.status not in ['awaiting_payment','placed']: raise ValidationError('This order can no longer be cancelled.')
    if order.payment_status == 'paid': raise ValidationError('Paid orders require a refund through the payment provider before cancellation.')
    for item in order.items.order_by('variant_id'):
        Variant.objects.filter(pk=item.variant_id).update(stock=F('stock')+item.quantity)
    order.status=reason
    order.save(update_fields=['status'])

@transaction.atomic
def expire_orders():
    for order in Order.objects.select_for_update().filter(status='awaiting_payment',expires_at__lt=timezone.now()).order_by('id'):
        release(order,'expired')

def gateway(method,path,**kwargs):
    if not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET: raise ValidationError('Online payments are not connected yet. Pay at pickup is available when checkout is open.')
    try:
        response=requests.request(method,'https://api.razorpay.com/v1/'+path,auth=(settings.RAZORPAY_KEY_ID,settings.RAZORPAY_KEY_SECRET),timeout=15,**kwargs)
        response.raise_for_status()
        return response.json()
    except (requests.RequestException,ValueError): raise ValidationError('The payment provider is temporarily unavailable. Please retry.')

@transaction.atomic
def checkout(user,data):
    # Serializing per customer also makes idempotency safe for concurrent retries.
    type(user).objects.select_for_update().get(pk=user.pk)
    existing=Order.objects.filter(user=user,idempotency_key=data['idempotency_key']).first()
    if existing: return existing
    if Order.objects.filter(idempotency_key=data['idempotency_key']).exists(): raise ValidationError('Invalid checkout key.')
    store=StoreSettings.objects.select_for_update().get(pk=1)
    if not store.accepting_orders or not store.details_verified: raise ValidationError('The store is preparing online ordering. Please check back soon.')
    if data['payment_method']=='pay_at_pickup' and data['fulfillment']!='pickup': raise ValidationError('Payment at pickup is only available for pickup orders.')
    if data['fulfillment']=='delivery':
        if data['pincode'] not in store.delivery_pincodes: raise ValidationError('Delivery is not currently available for this PIN code.')
        if len(data['address'].strip())<10: raise ValidationError('Please enter a complete delivery address.')
    else:
        if not store.pickup_enabled: raise ValidationError('Pickup is not currently available.')
        at=data.get('pickup_at')
        if not at or at < timezone.now()+timedelta(minutes=60) or at > timezone.now()+timedelta(days=7): raise ValidationError('Choose pickup at least one hour ahead and within seven days.')
        local=timezone.localtime(at)
        if local.weekday() not in store.open_days or not store.opens_at <= local.time().replace(tzinfo=None) < store.closes_at: raise ValidationError('Choose a pickup time during store opening hours.')
    cart=list(CartItem.objects.filter(user=user).order_by('variant_id'))
    if not cart: raise ValidationError('Your bag is empty.')
    variants={v.id:v for v in Variant.objects.select_for_update().select_related('product').filter(id__in=[c.variant_id for c in cart]).order_by('id')}
    subtotal=Decimal('0')
    for c in cart:
        v=variants[c.variant_id]
        if not v.product.active or not v.product.verified: raise ValidationError(f'{v.product.name} is awaiting store confirmation.')
        if c.quantity>v.stock: raise ValidationError(f'Only {v.stock} packs of {v.product.name} are available.')
        subtotal+=v.price*c.quantity
    fee=shipping(subtotal,store,data['fulfillment'])
    if data.pop('expected_total')!=subtotal+fee: raise ValidationError('Prices or delivery charges changed. Refresh your bag and review the new total.')
    order=Order.objects.create(user=user,subtotal=subtotal,delivery_fee=fee,total=subtotal+fee,status='awaiting_payment' if data['payment_method']=='online' else 'placed',expires_at=timezone.now()+timedelta(minutes=20) if data['payment_method']=='online' else None,**data)
    for c in cart:
        v=variants[c.variant_id]
        v.stock-=c.quantity
        v.save(update_fields=['stock'])
        OrderItem.objects.create(order=order,variant=v,name=v.product.name,name_te=v.product.name_te,label=v.label,quantity=c.quantity,unit_price=v.price)
    if order.payment_method=='online':
        payment=gateway('POST','orders',json={'amount':int(order.total*100),'currency':'INR','receipt':str(order.id)})
        order.gateway_order_id=payment['id']
        order.save(update_fields=['gateway_order_id'])
    CartItem.objects.filter(user=user).delete()
    return order

@transaction.atomic
def settle(order_id,payment_id):
    order=Order.objects.select_for_update().get(pk=order_id)
    if order.payment_status=='paid': return order
    payment=gateway('GET',f'payments/{payment_id}')
    if payment.get('order_id')!=order.gateway_order_id or payment.get('amount')!=int(order.total*100) or payment.get('currency')!='INR' or payment.get('status')!='captured':
        raise ValidationError('Payment has not been captured and verified. Your order remains unpaid.')
    order.gateway_payment_id=payment_id
    if order.status in ['expired','cancelled']:
        order.payment_status='refund_required'
        order.save(update_fields=['payment_status','gateway_payment_id'])
        return order
    order.payment_status='paid'
    order.status='placed'
    order.save(update_fields=['payment_status','status','gateway_payment_id'])
    return order
