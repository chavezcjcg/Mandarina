from django.db.models import Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST

from cerebro.utils import cerrar_pedido_e_imprimir
from .models import Comanda, Producto

def obtener_productos_mas_vendidos():

    reporte = (
        Producto.objects.annotate(total_vendido=Sum('detallecomanda__cantidad'))
        .filter(total_vendido__gt=0)
        .order_by('-total_vendido')
    )
    return reporte


@require_POST
def cerrar_comanda(request, comanda_id):
    comanda = get_object_or_404(Comanda, pk=comanda_id)

    try:
        pdf_cocina, pdf_barra = cerrar_pedido_e_imprimir(comanda.id)
        return JsonResponse({
            'success': True,
            'pdf_cocina': pdf_cocina,
            'pdf_barra': pdf_barra,
        })
    except Exception as exc:
        return JsonResponse({'success': False, 'error': str(exc)}, status=400)
