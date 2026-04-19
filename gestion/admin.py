from django.contrib import admin
from django.utils import timezone
from datetime import timedelta
from .models import (
    Mesa, Usuario, Categoria, Producto, 
    Comanda, DetalleComanda, Proveedor, 
    Insumo, EntradaInventario
)


class DetalleComandaInline(admin.TabularInline):
    model = DetalleComanda
    extra = 1


@admin.register(Comanda)
class ComandaAdmin(admin.ModelAdmin):
    list_display = ('nombre_cliente', 'mesa', 'total_venta', 'estado', 'fecha_hora')
    readonly_fields = ('total_venta',)
    inlines = [DetalleComandaInline]
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs

        hace_3_horas = timezone.now() - timedelta(hours=3)
        return qs.filter(fecha_hora__gte=hace_3_horas)


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'categoria', 'precio', 'codigo_busqueda', 'clave', 'disponible')
    list_editable = ('precio', 'disponible')
    search_fields = ('nombre', 'codigo_busqueda', 'clave')
    list_filter = ('categoria', 'es_especial_semanal')

admin.site.register(Mesa)
admin.site.register(Usuario)
admin.site.register(Categoria)
admin.site.register(Proveedor)
admin.site.register(Insumo)
admin.site.register(EntradaInventario)