from rest_framework import serializers
from .models import *
class VariantSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)
    class Meta:
        model = Variant
        fields = ['id','sku','label','price','stock']
        extra_kwargs = {'sku':{'validators':[]}}
class ProductSerializer(serializers.ModelSerializer):
    variants = VariantSerializer(many=True)
    category_name = serializers.CharField(source='category.name',read_only=True)
    category_te = serializers.CharField(source='category.name_te',read_only=True)
    class Meta:
        model = Product
        fields = ['id','category','category_name','category_te','name','name_te','description','description_te','brand','image_url','source_url','source_note','verified','active','featured','variants']
    def validate_variants(self, values):
        if not values: raise serializers.ValidationError('At least one pack size is required.')
        skus = [v['sku'] for v in values]
        if len(skus) != len(set(skus)): raise serializers.ValidationError('SKU values must be unique.')
        for v in values:
            qs = Variant.objects.filter(sku=v['sku'])
            if self.instance: qs = qs.exclude(product=self.instance)
            if qs.exists(): raise serializers.ValidationError('SKU already belongs to another product.')
        return values
    def create(self,data):
        variants = data.pop('variants')
        p = Product.objects.create(**data)
        for v in variants:
            v.pop('id',None)
            Variant.objects.create(product=p,**v)
        return p
    def update(self,instance,data):
        variants = data.pop('variants',None)
        for k,v in data.items(): setattr(instance,k,v)
        instance.save()
        if variants is not None:
            for v in variants:
                vid = v.pop('id',None)
                if vid:
                    try: item = instance.variants.get(pk=vid)
                    except Variant.DoesNotExist: raise serializers.ValidationError('Unknown pack size.')
                    for k,val in v.items(): setattr(item,k,val)
                    item.save()
                else: Variant.objects.create(product=instance,**v)
        return instance
class SettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = StoreSettings
        exclude = ['id']
    def validate(self,data):
        current = self.instance or StoreSettings.get()
        value = lambda key: data.get(key,getattr(current,key))
        if value('opens_at') >= value('closes_at'): raise serializers.ValidationError('Closing time must follow opening time.')
        if value('accepting_orders') and (not value('details_verified') or not value('phone') or not value('open_days')):
            raise serializers.ValidationError('Verify contact details and opening days before opening checkout.')
        return data
    def validate_delivery_pincodes(self,v):
        if not isinstance(v,list) or any(not isinstance(x,str) or len(x)!=6 or not x.isascii() or not x.isdigit() for x in v):
            raise serializers.ValidationError('Enter six-digit PIN codes.')
        return sorted(set(v))
    def validate_open_days(self,v):
        if not isinstance(v,list) or any(type(x)!=int or x not in range(7) for x in v): raise serializers.ValidationError('Days must be 0 (Monday) through 6 (Sunday).')
        return sorted(set(v))
class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model=OrderItem
        fields=['name','name_te','label','quantity','unit_price']
class OrderSerializer(serializers.ModelSerializer):
    items=OrderItemSerializer(many=True,read_only=True)
    class Meta:
        model=Order
        fields=['id','subtotal','delivery_fee','total','fulfillment','payment_method','status','payment_status','contact_name','phone','address','pincode','pickup_at','created_at','items']
class FeedbackSerializer(serializers.ModelSerializer):
    class Meta:
        model=Feedback
        fields=['id','order','subject','message','status','reply','created_at']
        read_only_fields=['status','reply','created_at']
    def validate_order(self,v):
        if v and v.user_id!=self.context['request'].user.id: raise serializers.ValidationError('Select one of your own orders.')
        return v
class CheckoutSerializer(serializers.Serializer):
    idempotency_key=serializers.UUIDField()
    fulfillment=serializers.ChoiceField(choices=['delivery','pickup'])
    payment_method=serializers.ChoiceField(choices=['online','pay_at_pickup'])
    contact_name=serializers.CharField(max_length=120)
    phone=serializers.RegexField(r'^[6-9][0-9]{9}$')
    address=serializers.CharField(max_length=1000,required=False,allow_blank=True,default='')
    pincode=serializers.RegexField(r'^[0-9]{6}$',required=False,allow_blank=True,default='')
    pickup_at=serializers.DateTimeField(required=False,allow_null=True,default=None)
    expected_total=serializers.DecimalField(max_digits=12,decimal_places=2)
