from django.contrib import admin, messages
from django.utils import timezone
from datetime import timedelta
from .models import (
    Mesa, Usuario, Categoria, Producto, 
    Comanda, DetalleComanda, Proveedor, 
    Insumo, EntradaInventario
)

@admin.register(Mesa)
class MesaAdmin(admin.ModelAdmin):
    search_fields = ['numero'] 
    list_display = ('numero', 'capacidad', 'esta_disponible')
    list_filter = ('esta_disponible',)


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'categoria', 'precio', 'codigo_busqueda', 'disponible')
    search_fields = ('nombre', 'codigo_busqueda', 'clave') 
    list_filter = ('categoria', 'disponible')

class DetalleComandaInline(admin.TabularInline):
    model = DetalleComanda
    autocomplete_fields = ('producto',) 
    fields = ('producto', 'cantidad', 'notas', 'subtotal')
    readonly_fields = ('subtotal',)
    extra = 1

@admin.register(Comanda)
class ComandaAdmin(admin.ModelAdmin):
    list_display = ('nombre_cliente', 'mesa', 'total_venta', 'estado', 'ver_estado_cocina', 'fecha_hora')
    autocomplete_fields = ('mesa',)
    readonly_fields = ('total_venta',)
    inlines = [DetalleComandaInline]
    actions = ['enviar_a_cocina_accion']

    def ver_estado_cocina(self, obj):
        pendientes = obj.items.filter(enviado_a_cocina=False).exists()
        return "PENDIENTE" if pendientes else "EN COCINA"
    ver_estado_cocina.short_description = "Cocina"

    @admin.action(description="Enviar productos nuevos a Cocina/Barista")
    def enviar_a_cocina_accion(self, request, queryset):
        for comanda in queryset:
            resumen = comanda.preparar_proxima_impresion()
            if resumen:
                print(f"\n--- TICKET PARA COCINA: {comanda.nombre_cliente} ---")
                for linea in resumen:
                    print(linea)
                print("-------------------------------------------\n")
                self.message_user(request, f"Comanda de {comanda.nombre_cliente} enviada a cocina.")
            else:
                self.message_user(request, f"La comanda de {comanda.nombre_cliente} no tenía productos nuevos.", messages.WARNING)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        hace_3_horas = timezone.now() - timedelta(hours=3)
        return qs.filter(fecha_hora__gte=hace_3_horas)

admin.site.register(Usuario)
admin.site.register(Categoria)
admin.site.register(Proveedor)
admin.site.register(Insumo)
admin.site.register(EntradaInventario)