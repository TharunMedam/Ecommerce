from django.contrib import admin
from .models import Category, Product, Variant, StoreSettings, Order, OrderItem, Feedback, AuditLog
admin.site.site_header = 'Anjaneya Store Administration'
class VariantInline(admin.TabularInline):
    model = Variant
    extra = 0
@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name','name_te','category','verified','active']
    search_fields = ['name','name_te','variants__sku']
    list_filter = ['category','verified','active']
    inlines = [VariantInline]
@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['id','user','total','status','payment_status','created_at']
    readonly_fields = [f.name for f in Order._meta.fields]
    def has_add_permission(self, request): return False
    def has_delete_permission(self, request, obj=None): return False
admin.site.register(Category)
admin.site.register(StoreSettings)
admin.site.register(Feedback)
@admin.register(AuditLog)
class AuditAdmin(admin.ModelAdmin):
    readonly_fields = [f.name for f in AuditLog._meta.fields]
    def has_add_permission(self,request): return False
    def has_delete_permission(self,request,obj=None): return False
