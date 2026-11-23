"""Procesamiento local de una copia ya recibida. Sin red y sin Android.

El paquete separa transporte, formato, verificación e importación. Su único
proveedor remoto está deshabilitado de forma explícita: no existe una interfaz
documentada y autorizada del proveedor. El proveedor simulado lee un archivo
local y permite integrar el flujo completo en Linux.
"""
