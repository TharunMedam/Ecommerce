import uuid
from decimal import Decimal
from django.conf import settings
from django.db import models
from django.core.validators import MinValueValidator

class Category(models.Model):
    name = models.CharField(max_length=80)
    name_te = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    def __str__(self): return self.name

class Product(models.Model):
    category = models.ForeignKey(Category,on_delete=models.PROTECT)
    name = models.CharField(max_length=160)
    name_te = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    description_te = models.TextField(blank=True)
    brand = models.CharField(max_length=100,blank=True)
    image_url = models.URLField(blank=True)
    source_url = models.URLField(blank=True)
    source_note = models.CharField(max_length=300,blank=True)
    verified = models.BooleanField(default=False)
    active = models.BooleanField(default=True)
    featured = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)
    def __str__(self): return self.name

class Variant(models.Model):
    product = models.ForeignKey(Product,related_name='variants',on_delete=models.CASCADE)
    sku = models.CharField(max_length=60,unique=True)
    label = models.CharField(max_length=60)
    price = models.DecimalField(max_digits=10,decimal_places=2,validators=[MinValueValidator(Decimal('0.01'))])
    stock = models.PositiveIntegerField(default=0)
    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(price__gt=0),name='positive_price')]

class StoreSettings(models.Model):
    name = models.CharField(max_length=120,default='Anjaneya Herbals & Dry Fruits')
    address = models.TextField(default='Vijayawada, Andhra Pradesh')
    phone = models.CharField(max_length=20,blank=True)
    hours = models.CharField(max_length=160,default='10:30 AM – 10:00 PM, Monday–Saturday (confirmation pending)')
    opens_at = models.TimeField(default='10:30')
    closes_at = models.TimeField(default='22:00')
    open_days = models.JSONField(default=list)
    free_delivery_above = models.DecimalField(max_digits=10,decimal_places=2,default=800,validators=[MinValueValidator(0)])
    delivery_fee = models.DecimalField(max_digits=8,decimal_places=2,null=True,blank=True,validators=[MinValueValidator(0)])
    delivery_pincodes = models.JSONField(default=list)
    pickup_enabled = models.BooleanField(default=True)
    accepting_orders = models.BooleanField(default=False)
    details_verified = models.BooleanField(default=False)
    @classmethod
    def get(cls): return cls.objects.get_or_create(pk=1)[0]

class CartItem(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE)
    variant = models.ForeignKey(Variant,on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['user','variant'],name='unique_cart_variant'),models.CheckConstraint(condition=models.Q(quantity__gt=0),name='cart_qty_positive')]

class Order(models.Model):
    id = models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    idempotency_key = models.UUIDField(unique=True)
    subtotal = models.DecimalField(max_digits=12,decimal_places=2)
    delivery_fee = models.DecimalField(max_digits=10,decimal_places=2)
    total = models.DecimalField(max_digits=12,decimal_places=2)
    fulfillment = models.CharField(max_length=10,choices=[('delivery','Delivery'),('pickup','Pickup')])
    payment_method = models.CharField(max_length=20,choices=[('online','Online'),('pay_at_pickup','Pay at pickup')])
    status = models.CharField(max_length=24,default='awaiting_payment')
    payment_status = models.CharField(max_length=24,default='unpaid')
    contact_name = models.CharField(max_length=120)
    phone = models.CharField(max_length=20)
    address = models.TextField(blank=True)
    pincode = models.CharField(max_length=6,blank=True)
    pickup_at = models.DateTimeField(null=True,blank=True)
    gateway_order_id = models.CharField(max_length=100,blank=True)
    gateway_payment_id = models.CharField(max_length=100,blank=True)
    expires_at = models.DateTimeField(null=True,blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

class OrderItem(models.Model):
    order = models.ForeignKey(Order,related_name='items',on_delete=models.CASCADE)
    variant = models.ForeignKey(Variant,on_delete=models.PROTECT)
    name = models.CharField(max_length=160)
    name_te = models.CharField(max_length=160)
    label = models.CharField(max_length=60)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10,decimal_places=2)

class Feedback(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE)
    order = models.ForeignKey(Order,null=True,blank=True,on_delete=models.SET_NULL)
    subject = models.CharField(max_length=160)
    message = models.TextField(max_length=3000)
    status = models.CharField(max_length=16,default='open',choices=[('open','Open'),('in_progress','In progress'),('resolved','Resolved')])
    reply = models.TextField(blank=True,max_length=3000)
    created_at = models.DateTimeField(auto_now_add=True)

class AuditLog(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL,null=True,on_delete=models.SET_NULL)
    action = models.CharField(max_length=80)
    target = models.CharField(max_length=100)
    details = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
