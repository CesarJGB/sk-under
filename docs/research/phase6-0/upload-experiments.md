# Experimentos de subida

**Hipótesis:** un sobre JSON con `data` textual comprimido en gzip puede conservar el agregado. **Prueba local:** `prepare_upload_candidate` sobre la primera descarga nueva. **Confirmado mediante ejecución local:** gzip de 17.386 bytes; al descomprimir y extraer `data`, los bytes son idénticos al original; SHA-256 del cuerpo `6b8dd01126d65366954de17ec4b7728532eb4d589e9f96fde1d43df6f98d9bbc`.

Este experimento no transmite datos ni valida el protocolo del servidor. **Pendiente:** prueba real idéntica únicamente cuando el contrato y una copia de seguridad recuperable estén suficientemente verificados. No se ejecutó POST de subida ni se recibió aceptación o rechazo del servidor. Las escrituras remotas continúan deshabilitadas.
