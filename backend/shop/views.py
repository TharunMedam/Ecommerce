import hashlib,hmac,json
from django.conf import settings
from django.contrib.auth import authenticate,login,logout,get_user_model
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction,IntegrityError
from django.db.models import Q
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.utils.encoding import force_bytes,force_str
from django.utils.http import urlsafe_base64_encode,urlsafe_base64_decode
from django.views.decorators.csrf import csrf_protect
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny,IsAdminUser
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from rest_framework.throttling import ScopedRateThrottle
from .models import *
from .serializers import *
from .services import checkout,shipping,expire_orders,settle,release
User=get_user_model()
def identity(user): return {'id':user.id,'name':user.first_name,'email':user.email,'is_staff':user.is_staff} if user.is_authenticated else None
def audit(request,action,target,details=None): AuditLog.objects.create(actor=request.user,action=action,target=str(target),details=details or {})

class Session(APIView):
    permission_classes=[AllowAny]
    def get(self,request): return Response({'user':identity(request.user),'csrf':get_token(request)})

@method_decorator(csrf_protect,name='dispatch')
class Auth(APIView):
    permission_classes=[AllowAny]
    throttle_classes=[ScopedRateThrottle]
    throttle_scope='auth'
    def post(self,request,action):
        d=request.data
        if action=='logout':
            logout(request)
            return Response({'user':None})
        email=str(d.get('email','')).strip().lower()
        password=d.get('password','')
        if not isinstance(password,str): raise ValidationError('Invalid password.')
        if action=='reset-request':
            u=User.objects.filter(username=email,is_active=True).first()
            if u and settings.EMAIL_HOST:
                link=f'{settings.FRONTEND_URL}/?reset={urlsafe_base64_encode(force_bytes(u.pk))}&token={default_token_generator.make_token(u)}'
                send_mail('Reset your Anjaneya password',f'Reset your password: {link}',settings.DEFAULT_FROM_EMAIL,[u.email])
            return Response({'message':'If this account exists, reset instructions will be emailed when email delivery is configured.'})
        if action=='reset-confirm':
            try:
                u=User.objects.get(pk=force_str(urlsafe_base64_decode(d.get('uid',''))))
                if not default_token_generator.check_token(u,d.get('token','')): raise ValueError()
                validate_password(password,u)
            except (ValueError,TypeError,User.DoesNotExist,DjangoValidationError): raise ValidationError('Invalid or expired reset link, or password does not meet requirements.')
            u.set_password(password);u.save()
            return Response({'message':'Password updated. You can sign in.'})
        if action=='register':
            from django.core.validators import validate_email
            try:
                validate_email(email)
                u=User(username=email,email=email,first_name=str(d.get('name','')).strip()[:100])
                validate_password(password,u)
            except DjangoValidationError as e: raise ValidationError(e.messages)
            if not u.first_name: raise ValidationError('Your name is required.')
            u.set_password(password)
            try: u.save()
            except IntegrityError: raise ValidationError('An account with this email already exists.')
            login(request,u)
        elif action=='login':
            u=authenticate(request,username=email,password=password)
            if not u or (d.get('owner') and not u.is_staff): raise ValidationError('Email or password is incorrect.')
            login(request,u)
        else: raise ValidationError('Unknown action.')
        return Response({'user':identity(request.user),'csrf':get_token(request)})

class Catalog(APIView):
    permission_classes=[AllowAny]
    def get(self,request):
        qs=Product.objects.filter(active=True).select_related('category').prefetch_related('variants').order_by('-featured','id')
        term=request.query_params.get('q','').strip()[:150]
        if term: qs=qs.filter(Q(name__icontains=term)|Q(name_te__icontains=term)|Q(brand__icontains=term))
        if request.query_params.get('category'): qs=qs.filter(category__slug=request.query_params['category'])
        return Response({'products':ProductSerializer(qs,many=True).data,'categories':list(Category.objects.values()),'store':SettingsSerializer(StoreSettings.get()).data,'payments_ready':bool(settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET)})

class Cart(APIView):
    def get(self,request):
        rows=[]
        total=0
        for c in CartItem.objects.filter(user=request.user).select_related('variant__product'):
            v=c.variant
            rows.append({'variant_id':v.id,'quantity':c.quantity,'price':str(v.price),'name':v.product.name,'name_te':v.product.name_te,'label':v.label,'stock':v.stock,'verified':v.product.verified})
            total+=v.price*c.quantity
        return Response({'items':rows,'subtotal':str(total)})
    @transaction.atomic
    def post(self,request):
        User.objects.select_for_update().get(pk=request.user.pk)
        try: vid=int(request.data.get('variant_id'));qty=int(request.data.get('quantity'))
        except (TypeError,ValueError): raise ValidationError('Choose a valid pack and quantity.')
        if qty<0 or qty>100: raise ValidationError('Quantity must be between 0 and 100.')
        v=get_object_or_404(Variant.objects.select_for_update(),pk=vid,product__active=True)
        if qty>v.stock: raise ValidationError(f'Only {v.stock} packs are available.')
        if qty: CartItem.objects.update_or_create(user=request.user,variant=v,defaults={'quantity':qty})
        else: CartItem.objects.filter(user=request.user,variant=v).delete()
        return self.get(request)

class Orders(APIView):
    def get(self,request): return Response(OrderSerializer(Order.objects.filter(user=request.user).prefetch_related('items').order_by('-created_at'),many=True).data)
    def post(self,request):
        serializer=CheckoutSerializer(data=request.data);serializer.is_valid(raise_exception=True)
        expire_orders()
        order=checkout(request.user,serializer.validated_data)
        return Response({'order':OrderSerializer(order).data,'payment':{'key':settings.RAZORPAY_KEY_ID,'order_id':order.gateway_order_id,'amount':int(order.total*100)} if order.gateway_order_id and order.status=='awaiting_payment' else None},status=201)

class CancelOrder(APIView):
    @transaction.atomic
    def post(self,request,pk):
        order=get_object_or_404(Order.objects.select_for_update(),pk=pk,user=request.user)
        release(order)
        return Response(OrderSerializer(order).data)

class VerifyPayment(APIView):
    def post(self,request,pk):
        order=get_object_or_404(Order,pk=pk,user=request.user)
        if not settings.RAZORPAY_KEY_SECRET or not order.gateway_order_id: raise ValidationError('No payment is pending.')
        pid=str(request.data.get('razorpay_payment_id',''))
        if not pid.startswith('pay_') or not pid.replace('_','').isalnum(): raise ValidationError('Invalid payment identifier.')
        expected=hmac.new(settings.RAZORPAY_KEY_SECRET.encode(),f'{order.gateway_order_id}|{pid}'.encode(),hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected,str(request.data.get('razorpay_signature',''))): raise ValidationError('Payment signature verification failed.')
        return Response(OrderSerializer(settle(order.pk,pid)).data)

class Webhook(APIView):
    permission_classes=[AllowAny]
    authentication_classes=[]
    def post(self,request):
        secret=settings.RAZORPAY_WEBHOOK_SECRET
        if not secret: return Response(status=503)
        signature=hmac.new(secret.encode(),request.body,hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature,request.headers.get('X-Razorpay-Signature','')): return Response(status=400)
        if request.data.get('event')=='payment.captured':
            entity=request.data.get('payload',{}).get('payment',{}).get('entity',{})
            o=Order.objects.filter(gateway_order_id=entity.get('order_id','')).exclude(gateway_order_id='').first()
            if o: settle(o.pk,entity['id'])
        return Response({'received':True})

class FeedbackView(APIView):
    def get(self,request): return Response(FeedbackSerializer(Feedback.objects.filter(user=request.user).order_by('-created_at'),many=True).data)
    def post(self,request):
        s=FeedbackSerializer(data=request.data,context={'request':request});s.is_valid(raise_exception=True);s.save(user=request.user)
        return Response(s.data,status=201)

class Owner(APIView):
    permission_classes=[IsAdminUser]
    def get(self,request,section):
        if section=='products': return Response(ProductSerializer(Product.objects.select_related('category').prefetch_related('variants').order_by('id'),many=True).data)
        if section=='settings': return Response(SettingsSerializer(StoreSettings.get()).data)
        if section=='orders': return Response(OrderSerializer(Order.objects.prefetch_related('items').order_by('-created_at')[:500],many=True).data)
        if section=='feedback': return Response(FeedbackSerializer(Feedback.objects.order_by('-created_at')[:500],many=True).data)
        raise ValidationError('Unknown section.')
    @transaction.atomic
    def post(self,request,section):
        if section!='products': raise ValidationError('Unsupported action.')
        s=ProductSerializer(data=request.data);s.is_valid(raise_exception=True);p=s.save()
        audit(request,'create_product',p.pk)
        return Response(s.data,status=201)
    @transaction.atomic
    def patch(self,request,section):
        if section=='settings':
            obj=StoreSettings.objects.select_for_update().get(pk=1)
            s=SettingsSerializer(obj,data=request.data,partial=True);s.is_valid(raise_exception=True);s.save()
            audit(request,'update_settings',1,request.data)
            return Response(s.data)
        if section=='products':
            obj=get_object_or_404(Product.objects.select_for_update(),pk=request.data.get('id'))
            # Same variant lock used by checkout; price and inventory edits cannot race it.
            list(Variant.objects.select_for_update().filter(product=obj).order_by('id'))
            s=ProductSerializer(obj,data=request.data,partial=True);s.is_valid(raise_exception=True);s.save()
            audit(request,'update_product',obj.pk,{'name':obj.name})
            return Response(s.data)
        if section=='feedback':
            obj=get_object_or_404(Feedback,pk=request.data.get('id'))
            status=request.data.get('status',obj.status)
            if status not in ['open','in_progress','resolved']: raise ValidationError('Invalid feedback status.')
            obj.status=status;obj.reply=str(request.data.get('reply',obj.reply))[:3000];obj.save()
            audit(request,'reply_feedback',obj.pk)
            return Response(FeedbackSerializer(obj).data)
        if section=='orders':
            obj=get_object_or_404(Order.objects.select_for_update(),pk=request.data.get('id'))
            target=request.data.get('status')
            if request.data.get('mark_paid'):
                if obj.payment_method!='pay_at_pickup' or obj.status not in ['placed','preparing','ready']: raise ValidationError('Only active pickup orders can be marked paid in store.')
                obj.payment_status='paid';obj.save(update_fields=['payment_status'])
            elif target=='cancelled': release(obj)
            else:
                transitions={'placed':['preparing'],'preparing':['ready'] if obj.fulfillment=='pickup' else ['out_for_delivery'],'ready':['completed'],'out_for_delivery':['completed']}
                if target not in transitions.get(obj.status,[]): raise ValidationError('Invalid order status transition.')
                if obj.payment_method=='online' and obj.payment_status!='paid': raise ValidationError('Online payment must be verified first.')
                if target=='completed' and obj.payment_status!='paid': raise ValidationError('Record payment before completing the order.')
                obj.status=target;obj.save(update_fields=['status'])
            audit(request,'update_order',obj.pk,{'status':obj.status,'payment_status':obj.payment_status})
            return Response(OrderSerializer(obj).data)
        raise ValidationError('Unknown section.')
