"""Procesamiento local de una copia ya recibida y proveedores de adquisición.

El paquete separa transporte, formato, verificación e importación. El proveedor
por defecto está deshabilitado. ``provider.py`` añade un fixture local y un
prototipo HTTP de solo lectura para el gateway oficial; este último exige un
token de juego y su camino de éxito no se verificó contra el servicio real.
"""
