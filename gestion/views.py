from django.db.models import Sum
from .models import Producto, DetalleComanda

def obtener_productos_mas_vendidos():

    reporte = (
        Producto.objects.annotate(total_vendido=Sum('detallecomanda__cantidad'))
        .filter(total_vendido__gt=0)
        .order_dict('-total_vendido')
    )
    return reporte