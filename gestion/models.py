from django.db import models
from django.utils import timezone

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
    nombre = models.CharField(max_length=100)
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
    nombre = models.CharField(max_length=100)
    codigo_busqueda = models.CharField(max_length=10, unique=True, null=True, blank=True)
    precio = models.DecimalField(max_digits=10, decimal_places=2)
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

    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE)
    mesa = models.ForeignKey(Mesa, on_delete=models.CASCADE)
    nombre_cliente = models.CharField(max_length=100, verbose_name="Nombre del Cliente")
    fecha_hora = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(max_length=20, choices=ESTADOS, default='abierta')
    metodo_pago = models.CharField(max_length=20, choices=METODOS, null=True, blank=True)
    total_venta = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def __str__(self):
        return f"{self.nombre_cliente} - Mesa {self.mesa.numero}"

    def actualizar_total(self):
        nuevo_total = sum(item.subtotal for item in self.items.all())
        self.total_venta = nuevo_total
        Comanda.objects.filter(pk=self.pk).update(total_venta=nuevo_total)

    def preparar_proxima_impresion(self):
        items_pendientes = self.items.filter(enviado_a_cocina=False)
        if not items_pendientes.exists():
            return None
        
        resumen = []
        for item in items_pendientes:
            resumen.append(f"{item.cantidad}x {item.producto.nombre} (Notas: {item.notas or 'N/A'})")
        
        items_pendientes.update(enviado_a_cocina=True)
        return resumen

    def save(self, *args, **kwargs):
        if self.estado == 'abierta':
            self.mesa.esta_disponible = False
        else:
            self.mesa.esta_disponible = True
        self.mesa.save()
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

class Proveedor(models.Model):
    nombre_empresa = models.CharField(max_length=100)
    telefono = models.CharField(max_length=20)
    contacto = models.CharField(max_length=100)
    def __str__(self): return self.nombre_empresa

class Insumo(models.Model):
    nombre = models.CharField(max_length=100)
    unidad_medida = models.CharField(max_length=20)
    stock_actual = models.DecimalField(max_digits=10, decimal_places=2)
    stock_minimo = models.DecimalField(max_digits=10, decimal_places=2)
    proveedor = models.ForeignKey(Proveedor, on_delete=models.CASCADE)

    @property
    def necesita_pedido(self):
        return self.stock_actual <= self.stock_minimo

    def __str__(self): return f"{self.nombre} ({self.stock_actual})"

class EntradaInventario(models.Model):
    insumo = models.ForeignKey(Insumo, on_delete=models.CASCADE)
    cantidad = models.DecimalField(max_digits=10, decimal_places=2)
    fecha = models.DateTimeField(auto_now_add=True)
    comentario = models.TextField(blank=True, null=True) 

    def save(self, *args, **kwargs):
        self.insumo.stock_actual += self.cantidad
        self.insumo.save()
        super().save(*args, **kwargs)