from django.db import models
from django.utils import timezone
from fpdf import FPDF
from django.conf import settings
from django.core.validators import MinValueValidator, RegexValidator, EmailValidator
from django.core.exceptions import ValidationError

class Mesa(models.Model):
    numero = models.PositiveIntegerField(unique=True)
    capacidad = models.PositiveIntegerField()
    esta_disponible = models.BooleanField(default=True)

    def get_comanda_activa(self):
        return Comanda.objects.filter(mesa=self, estado='abierta').first()

    def __str__(self):
        estado = "Libre" if self.esta_disponible else "Ocupada"
        return f"Mesa {self.numero} ({estado})"

class Usuario(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    rol = models.CharField(max_length=50) 
    contrasena = models.CharField(max_length=128)

    def __str__(self):
        return f"{self.nombre} - {self.rol}"

class Categoria(models.Model):
    nombre = models.CharField(max_length=50, unique=True) 
    def __str__(self):
        return self.nombre

    def save(self, *args, **kwargs):
        self.nombre = self.nombre.capitalize()
        super().save(*args, **kwargs)

class Producto(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    codigo_busqueda = models.CharField(max_length=10, unique=True, null=True, blank=True)
    precio = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0, message='El precio debe ser un valor positivo.')]
    )
    clave = models.CharField(max_length=20, unique=True, null=True, blank=True)
    categoria = models.ForeignKey(Categoria, on_delete=models.PROTECT)
    es_especial_semanal = models.BooleanField(default=False)
    disponible = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.nombre} [{self.codigo_busqueda}]"

class Comanda(models.Model):
    ESTADOS = (
        ('abierta', 'Abierta'),
        ('pagada', 'Pagada'),
        ('cancelada', 'Cancelada'),
    )
    METODOS = (
        ('efectivo', 'Efectivo'),
        ('tarjeta', 'Tarjeta'),
    )

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE,
        editable=False,
        null=True,
        blank=True
    )
    mesa = models.ForeignKey(Mesa, on_delete=models.CASCADE)
    nombre_cliente = models.CharField(max_length=100, verbose_name="Nombre del Cliente")
    fecha_hora = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(max_length=20, choices=ESTADOS, default='abierta')
    metodo_pago = models.CharField(max_length=20, choices=METODOS, null=True, blank=True)
    total_venta = models.DecimalField(max_digits=10, decimal_places=2, default=0, editable=False)

    def __str__(self):
        return f"Orden #{self.id} - {self.nombre_cliente} ({self.get_estado_display()})"
    def generar_ticket_dual(self, tipo="cocina"):
        from fpdf import FPDF
        import os
        pdf = FPDF(format=(80, 150))
        pdf.add_page()
        pdf.set_font("Arial", 'B', 14)
        pdf.cell(0, 8, "MANDARINA CAFÉ", ln=True, align='C')
        pdf.set_font("Arial", 'B', 10)
        titulo = "CUENTA FINAL" if tipo == "factura" else f"NUEVOS PEDIDOS: {tipo.upper()}"
        pdf.cell(0, 6, titulo, ln=True, align='C')
        pdf.set_font("Arial", '', 10)
        pdf.cell(0, 6, f"Cliente: {self.nombre_cliente} #{self.id}", ln=True)
        pdf.cell(0, 6, f"Mesa: {self.mesa.numero}", ln=True)
        pdf.cell(0, 2, "-"*40, ln=True)
        pdf.ln(2)
        detalles = self.items.all()
        if tipo != "factura":
            detalles = detalles.filter(enviado_a_cocina=False)  
            if not detalles.exists():
                return None 
        for item in detalles:
            nombre_cat = item.producto.categoria.nombre.lower()
            es_bebida = "bebid" in nombre_cat or "agua" in nombre_cat
            prefijo = " * " if es_bebida else "   "
            pdf.set_font("Arial", 'B' if es_bebida else '', 10)
            linea = f"{item.cantidad}x{prefijo}{item.producto.nombre}"
            if tipo == "barista":
                pdf.cell(45, 6, linea)
                pdf.cell(0, 6, f"Q{item.subtotal:.2f}", align='R', ln=True)
            elif tipo == "cocina":
                pdf.cell(0, 7, linea, ln=True)
            else: 
                pdf.cell(45, 6, linea)
                pdf.cell(0, 6, f"Q{item.subtotal:.2f}", align='R', ln=True)

            if item.notas:
                pdf.set_font("Arial", 'I', 9)
                pdf.cell(0, 5, f"   Nota: {item.notas}", ln=True)

        pdf.ln(2)
        pdf.cell(0, 2, "-"*40, ln=True)

        if tipo in ["barista", "factura"]:
            pdf.set_font("Arial", 'B', 12)
            label = "TOTAL A COBRAR:" if tipo == "factura" else "TOTAL NUEVO:"
            monto = self.total_venta if tipo == "factura" else sum(i.subtotal for i in detalles)
            
            pdf.cell(40, 10, label)
            pdf.cell(0, 10, f"Q{monto:.2f}", align='R', ln=True)

        folder = "tickets"
        if not os.path.exists(folder): os.makedirs(folder)
        filename = f"{folder}/ticket_{tipo}_{self.id}.pdf"
        pdf.output(filename)
        return filename
    def actualizar_total(self):
        total = sum(item.subtotal for item in self.items.all())
        self.total_venta = total
        self.save(update_fields=['total_venta'])
    
    def preparar_proxima_impresion(self):
        items_pendientes = self.items.filter(enviado_a_cocina=False)
        if not items_pendientes.exists():
            return None
        
        resumen = []
        for item in items_pendientes:
            resumen.append(f"{item.cantidad}x {item.producto.nombre} (Notas: {item.notas or 'N/A'})")
        
        items_pendientes.update(enviado_a_cocina=True)
        return resumen
    
    def obtener_productos_pendientes(self):
        return self.items.filter(enviado_a_cocina=False)
    def generar_ticket_ficticio(self):
        pendientes = self.obtener_productos_pendientes()
        if not pendientes.exists():
            return None
        lineas_ticket = []
        lineas_ticket.append(f"MESA: {self.mesa.numero}")
        lineas_ticket.append(f"CLIENTE: {self.nombre_cliente}")
        lineas_ticket.append(f"FECHA: {self.fecha_hora.strftime('%d/%m/%Y %H:%M')}")
        lineas_ticket.append("-" * 20)
        for item in pendientes:
            lineas_ticket.append(f"{item.cantidad}x {item.producto.nombre}")
            if item.notas:
                lineas_ticket.append(f"   * NOTA: {item.notas}")
        lineas_ticket.append("-" * 20)
        return "\n".join(lineas_ticket)
    def marcar_como_enviados(self):
        self.items.filter(enviado_a_cocina=False).update(enviado_a_cocina=True)
    def generar_ticket_cocina(self):
        items = self.items.filter(enviado_a_cocina=False)
        if not items.exists(): return None
        
        lineas = [f"ORDEN: {self.nombre_cliente} #{self.id}", f"MESA: {self.mesa}", "-"*20]
        for item in items:
            lineas.append(f"{item.cantidad}x {item.producto.nombre}")
            if item.notas:
                lineas.append(f"   > NOTA: {item.notas}")
        return "\n".join(lineas)
    def generar_ticket_barista(self):
        items = self.items.filter(enviado_a_cocina=False)
        if not items.exists(): return None
        lineas = [f"CUENTA: {self.nombre_cliente} #{self.id}", "-"*20]
        for item in items:
            prefijo = "☕ [BEBIDA]" if item.producto.categoria.nombre.lower() == "bebidas" else "🍴"
            lineas.append(f"{prefijo} {item.cantidad}x {item.producto.nombre} ... Q{item.subtotal}")
        lineas.append("-"*20)
        lineas.append(f"TOTAL: Q{self.total_venta}")
        return "\n".join(lineas)
def save(self, *args, **kwargs):
    if self.estado == 'pagada':
        self.items.filter(enviado_a_cocina=False).update(enviado_a_cocina=True)

    self.actualizar_total() 
    super().save(*args, **kwargs)

class DetalleComanda(models.Model):
    comanda = models.ForeignKey(Comanda, related_name='items', on_delete=models.CASCADE)
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
    cantidad = models.PositiveIntegerField(default=1)
    notas = models.CharField(max_length=200, blank=True, null=True, help_text="Ej: Sin azúcar")
    enviado_a_cocina = models.BooleanField(default=False) 
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, editable=False)

    def save(self, *args, **kwargs):
        self.subtotal = self.producto.precio * self.cantidad
        super().save(*args, **kwargs)
        self.comanda.actualizar_total()
    def __str__(self):
        return f"{self.cantidad}x {self.producto.nombre}"
class Proveedor(models.Model):
    nombre_empresa = models.CharField(max_length=100, unique=True)
    telefono = models.CharField(
        max_length=20,
        validators=[
            RegexValidator(
                regex=r'^\d{8}$',
                message='El teléfono debe contener exactamente 8 dígitos numéricos.'
            )
        ]
    )
    contacto = models.EmailField(
        validators=[
            RegexValidator(
                regex=r'^[a-zA-Z0-9._%+-]+@gmail\.com$',
                message='El correo electrónico debe ser de dominio @gmail.com.'
            )
        ]
    )
    notas = models.TextField(blank=True, null=True, help_text="Acuerdos de entrega, días de pago, etc.")
    insumos = models.ManyToManyField('Insumo', blank=True, related_name='proveedores', help_text="Insumos que vende este proveedor")

    def __str__(self): 
        return self.nombre_empresa

class Insumo(models.Model):
    nombre = models.CharField(max_length=100)
    unidad_medida = models.CharField(max_length=50) 
    stock_actual = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0, message='El stock actual no puede ser negativo.')]
    )
    stock_minimo = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0, message='El stock mínimo no puede ser negativo.')]
    )
    stock_ideal = models.IntegerField(
        default=0,
        help_text="Cantidad óptima a mantener en bodega",
        validators=[MinValueValidator(0, message='El stock ideal no puede ser negativo.')]
    )
    proveedor = models.ForeignKey(Proveedor, on_delete=models.SET_NULL, null=True, blank=True, related_name='insumos_legacy')

    class Meta:
        unique_together = ('proveedor', 'nombre')

    @property
    def necesita_pedido(self):
        return self.stock_actual <= self.stock_minimo

    def __str__(self): return f"{self.nombre} ({self.stock_actual})"

class EntradaInventario(models.Model):
    insumo = models.ForeignKey(Insumo, on_delete=models.CASCADE)
    cantidad = models.PositiveIntegerField(
        validators=[MinValueValidator(1, message='La cantidad de entrada debe ser al menos 1.')]
    )
    fecha = models.DateTimeField(auto_now_add=True)
    comentario = models.TextField(default='', blank=True)

    def save(self, *args, **kwargs):
            self.insumo.stock_actual += self.cantidad   
            self.insumo.save()
            super().save(*args, **kwargs)
    def __str__(self):
        return f"{self.insumo.nombre} - Cantidad: {self.cantidad}"
class MovimientoInventario(models.Model):
    insumo = models.ForeignKey(Insumo, on_delete=models.CASCADE)
    cantidad_a_agregar = models.PositiveIntegerField(default=0, help_text="Cantidad que entra a bodega")
    cantidad_a_quitar = models.PositiveIntegerField(default=0, help_text="Cantidad que sale o se usa")
    comentario = models.TextField(blank=True)
    fecha = models.DateTimeField(auto_now_add=True)

    def clean(self):
        neto = self.cantidad_a_agregar - self.cantidad_a_quitar
        if (self.insumo.stock_actual + neto) < 0:
            raise ValidationError("No hay suficientes existencias en stock para realizar esta operación.")

    def save(self, *args, **kwargs):
        self.full_clean()  # Llamar a clean() antes de guardar
        neto = self.cantidad_a_agregar - self.cantidad_a_quitar
        self.insumo.stock_actual += neto
        self.insumo.save()
        super().save(*args, **kwargs)
class TicketPDF(FPDF):
    def header(self):
        self.set_font("Arial", "B", 12)
        self.cell(0, 10, "MANDARINA CAFÉ", align="C", ln=True)
        self.ln(5)


