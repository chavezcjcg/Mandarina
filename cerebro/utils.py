import subprocess
from pathlib import Path
from django.db import transaction
from gestion.models import Comanda
from django.conf import settings

SUMATRA_PATH = r"C:\Program Files\SumatraPDF\SumatraPDF.exe"  # !!!!!!!ruta al ejecutable de Sumatra en tu equipo

PRINTER_COCINA = "COCINA"  # !!!!!!!!!!!!!!!!!!!!nombre exacto de la impresora térmica de cocina
PRINTER_BARRA = "BARRA"    # !!!!!!!!!!!!!!!!!!!!nombre exacto de la impresora térmica de barra


def imprimir_pdf_silent(pdf_path: str, printer_name: str):
    ruta_completa = Path(settings.MEDIA_ROOT) / pdf_path
    
    ruta_str = str(ruta_completa.absolute())

    if not ruta_completa.exists():
        raise FileNotFoundError(f"No se encontró el PDF en: {ruta_str}")

    args = [
        SUMATRA_PATH,
        "-print-to", printer_name,
        "-silent",
        ruta_str,
    ]
    subprocess.run(args, check=True)
def cerrar_pedido_e_imprimir(comanda_id: int):
    comanda = Comanda.objects.select_related("mesa").prefetch_related("items__producto").get(pk=comanda_id)

    with transaction.atomic():
        pdf_cocina = comanda.generar_ticket_dual(tipo="cocina")
        pdf_barra = comanda.generar_ticket_dual(tipo="barista")
        
        comanda.marcar_como_enviados()
        comanda.estado = "pagada"
        comanda.save(update_fields=["estado"])
    try:
        if pdf_cocina:
            imprimir_pdf_silent(pdf_cocina, PRINTER_COCINA)
        
        if pdf_barra:
            imprimir_pdf_silent(pdf_barra, PRINTER_BARRA)
    except Exception as e:
        print(f"Error de hardware en las impresoras: {e}")

    return pdf_cocina, pdf_barra
