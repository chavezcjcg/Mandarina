from django.db.models import F
from django.contrib import admin, messages
from django.utils import timezone
from datetime import timedelta
from django.http import HttpResponseRedirect
from django.db.models import Sum
from django.utils.safestring import mark_safe
from .models import (
    Mesa, Usuario, Categoria, Producto, 
    Comanda, DetalleComanda, Proveedor, 
    Insumo, EntradaInventario, MovimientoInventario
)

@admin.register(Mesa)
class MesaAdmin(admin.ModelAdmin):
    search_fields = ['numero'] 
    list_display = ('numero', 'capacidad', 'esta_disponible')
    list_filter = ('esta_disponible',)

@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'categoria', 'precio', 'codigo_busqueda', 'ventas_totales', 'disponible')
    search_fields = ('nombre', 'codigo_busqueda', 'clave') 
    list_filter = ('categoria', 'disponible')
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(total_vendido= Sum('detallecomanda__cantidad'))
    def ventas_totales(self, obj):

        return obj.total_vendido or 0
    ventas_totales.short_description = " Unidades Vendidas"
    ventas_totales.admin_order_field = 'total_vendido'
class DetalleComandaInline(admin.TabularInline):
    model = DetalleComanda
    fields = ('tipo_item', 'producto', 'cantidad', 'notas', 'subtotal')
    readonly_fields = ('tipo_item', 'subtotal')

    def tipo_item(self, obj):
        if obj.producto and obj.producto.categoria.nombre.lower() == "bebidas":
            return mark_safe('<span style="color: #2874A6; font-weight: bold;">☕ BEBIDA</span>')
        return " COMIDA"
    tipo_item.short_description = "Tipo"
@admin.register(Comanda)
class ComandaAdmin(admin.ModelAdmin):
    list_display = ('ver_cliente_id', 'mesa', 'total_venta', 'estado', 'ver_estado_cocina', 'fecha_hora')
    autocomplete_fields = ('mesa',)
    readonly_fields = ('usuario', 'total_venta', 'boton_imprimir')
    inlines = [DetalleComandaInline]
    actions = ['enviar_a_cocina_accion']
    fields = ('usuario', 'mesa', 'nombre_cliente', 'estado', 'metodo_pago', 'total_venta', 'boton_imprimir')
    search_fields = ('nombre_cliente', 'mesa__numero') 
    list_filter = ('estado', 'mesa', 'fecha_hora')   
    ordering = ('-fecha_hora',)
    def save_model(self, request, obj, form, change):
        if not obj.pk: 
            obj.usuario = request.user
        super().save_model(request, obj, form, change)
    def response_change(self, request, obj):
        if "_imprimir" in request.POST:
            pdf_cocina = obj.generar_ticket_dual(tipo="cocina")
            pdf_barista = obj.generar_ticket_dual(tipo="barista")
            
            if pdf_cocina or pdf_barista:
                obj.marcar_como_enviados()
                self.message_user(request, "✅ Nuevos pedidos enviados a producción.")
            else:
                self.message_user(request, "ℹ️ No hay productos nuevos para imprimir.", level='WARNING')
            return HttpResponseRedirect(".")
        if "_factura" in request.POST:
            obj.generar_ticket_dual(tipo="factura")
            self.message_user(request, f"📄 Cuenta completa de {obj.nombre_cliente} generada.")
            return HttpResponseRedirect(".")

        return super().response_change(request, obj)
    @admin.action(description="🖨️ Imprimir y enviar seleccionados")
    def enviar_a_cocina_accion(self, request, queryset):
        exitos = 0
        for comanda in queryset:
            try:
                comanda.generar_ticket_dual(tipo="cocina")
                comanda.generar_ticket_dual(tipo="barista")
                if hasattr(comanda, 'marcar_como_enviados'):
                    comanda.marcar_como_enviados()
                exitos += 1
            except Exception as e:
                self.message_user(request, f"Error en {comanda}: {e}", level=messages.ERROR)
        
        self.message_user(request, f"Se generaron los PDFs de {exitos} comandas.")

    def boton_imprimir(self, obj):
        if obj.pk:
            return mark_safe(f'''
                <div style="background: #ebf5fb; padding: 10px; border: 1px solid #aed6f1; border-radius: 4px;">
                    <input type="submit" name="_imprimir" value="🖨️ IMPRIMIR CUENTA: {obj.nombre_cliente.upper()} #{obj.id}" 
                    style="background: #2874a6; color: white; padding: 8px 15px; border: none; border-radius: 4px; cursor: pointer; font-weight: bold;">
                </div>
            ''')
        return "Guarda los datos para imprimir."

    def ver_cliente_id(self, obj):
        return f"{obj.nombre_cliente} #{obj.id}"
    
    def ver_estado_cocina(self, obj):
        total_items = obj.items.count()
        enviados = obj.items.filter(enviado_a_cocina=True).count()
        pendientes = total_items - enviados
        if total_items == 0: return "VACÍA"
        if pendientes > 0: return f"⚠️ PENDIENTE ({pendientes} nuevos)"
        return "✅ TODO EN COCINA"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        hace_3_horas = timezone.now() - timedelta(hours=3)
        return qs.filter(fecha_hora__gte=hace_3_horas)

    ver_cliente_id.short_description = "Cliente (ID)"
    ver_cliente_id.admin_order_field = 'nombre_cliente'
    boton_imprimir.short_description = "Acción Rápida"
    ver_estado_cocina.short_description = "Estado Cocina"
    def boton_imprimir(self, obj):
        if obj.pk:
            return mark_safe(f'''
                <div style="display:flex; gap:10px;">
                    <button type="submit" name="_imprimir" 
                            style="background: #2874a6; color: white; padding: 10px 15px; border: none; border-radius: 4px; cursor: pointer; font-weight: bold;">
                         Enviar Nuevos a Producción
                    </button>
                    
                    <button type="submit" name="_factura" 
                            style="background: #239b56; color: white; padding: 10px 15px; border: none; border-radius: 4px; cursor: pointer; font-weight: bold;">
                         Generar Cuenta Final (Todo)
                    </button>
                </div>
            ''')
        return "Guarda la comanda para habilitar impresión."
    def response_change(self, request, obj):
        if "_imprimir" in request.POST:
            p1 = obj.generar_ticket_dual(tipo="cocina")
            p2 = obj.generar_ticket_dual(tipo="barista")
            
            if p1 or p2:
                obj.marcar_como_enviados() 
                self.message_user(request, "✅ Comanda enviada a producción.")
            else:
                self.message_user(request, "No hay productos nuevos pendientes.", level='WARNING')
            return HttpResponseRedirect(".")
        if "_factura" in request.POST:
            obj.generar_ticket_dual(tipo="factura")
            self.message_user(request, f"📄 Cuenta de {obj.nombre_cliente} generada con éxito.")
            return HttpResponseRedirect(".")
            
        return super().response_change(request, obj)
class InsumoInline(admin.TabularInline):
    model = Insumo
    extra = 0
    fields = ('nombre', 'stock_actual', 'stock_ideal', 'unidad_medida') 
    readonly_fields = ('stock_actual',) 
    can_delete = False
class UrgenciaFilter(admin.SimpleListFilter):
    title = 'Estado de Urgencia'
    parameter_name = 'urgencia'
    def lookups(self, request, model_admin):
        return [
            ('si', '🔴 Solo Urgentes'),
            ('no', 'Stock Suficiente'),
        ]
    def queryset(self, request, queryset):
        if self.value() == 'si':
            return queryset.filter(stock_actual__lte=F('stock_minimo'))
        if self.value() == 'no':
            return queryset.filter(stock_actual__gt=F('stock_minimo'))
        return queryset
@admin.register(Insumo)
class InsumoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'ver_stock_actual', 'stock_minimo', 'stock_ideal', 'estado_pedido', 'proveedor')
    

    list_filter = (UrgenciaFilter, 'proveedor', 'unidad_medida')
    search_fields = ('nombre',)

    def ver_stock_actual(self, obj):
        color = "#E74C3C" if obj.stock_actual <= obj.stock_minimo else "inherit"
        return mark_safe(f'<b style="color: {color};">{obj.stock_actual} {obj.unidad_medida}</b>')

    def estado_pedido(self, obj):
        if obj.stock_actual <= obj.stock_minimo:
            faltante = obj.stock_ideal - obj.stock_actual
            pedido = faltante if faltante > 0 else "Revisar"
            return mark_safe(f'<span style="background: #E74C3C; color: white; padding: 3px 8px; border-radius: 5px; font-weight: bold;"> URGENTE: {pedido}</span>')
        return mark_safe('<span style="color: #27AE60;"> OK</span>')

    ver_stock_actual.short_description = "Stock Actual"
    estado_pedido.short_description = "Estado"
@admin.register(EntradaInventario)
class EntradaInventarioAdmin(admin.ModelAdmin):
    list_display = ('insumo', 'cantidad', 'fecha', 'comentario')
    list_filter = ('insumo', 'fecha')
    search_fields = ('insumo__nombre', 'comentario')

@admin.register(MovimientoInventario)
class MovimientoInventarioAdmin(admin.ModelAdmin):
    list_display = ('insumo', 'cantidad_a_agregar', 'cantidad_a_quitar', 'fecha', 'comentario')
    list_filter = ('insumo', 'fecha')
    search_fields = ('insumo__nombre', 'comentario')

@admin.register(Proveedor)
class ProveedorAdmin(admin.ModelAdmin):
    list_display = ('nombre_empresa', 'contacto', 'telefono')
    search_fields = ('nombre_empresa', 'contacto')
    fields = ('nombre_empresa', 'contacto', 'telefono', 'notas', 'insumos')
    filter_horizontal = ('insumos',)  

admin.site.register(Usuario)
admin.site.register(Categoria)

