"""Errores tipados de la autenticación nativa y de la sesión web.

Los mensajes son aptos para el navegador: no incluyen cuerpos remotos,
credenciales, correos, tokens ni identificadores personales. El código estable
permite al frontend distinguir estados sin depender del texto.
"""

from __future__ import annotations


class NativeError(Exception):
    code = "native_error"
    status = 400

    def __init__(self, message: str, *, code: str | None = None, status: int | None = None) -> None:
        super().__init__(message)
        if code is not None:
            self.code = code
        if status is not None:
            self.status = status


class NativeDisabled(NativeError):
    code = "native_auth_disabled"
    status = 503


class NativeMisconfigured(NativeError):
    code = "native_auth_misconfigured"
    status = 503


class NativeStoreUnavailable(NativeError):
    code = "native_store_unavailable"
    status = 503


class NativeStoreMisconfigured(NativeError):
    code = "native_store_misconfigured"
    status = 503


class NativeOriginDenied(NativeError):
    code = "native_origin_denied"
    status = 403


class NativeDistributionUnknown(NativeError):
    code = "native_distribution_unknown"
    status = 422


class NativeDistributionDisabled(NativeError):
    code = "native_distribution_disabled"
    status = 409


class NativeProfileMissing(NativeError):
    code = "native_profile_missing"
    status = 503


class NativeProfileRequired(NativeError):
    code = "native_profile_required"
    status = 409


class NativeProfileNotFound(NativeError):
    code = "native_profile_not_found"
    status = 404


class NativeProfileInvalid(NativeError):
    code = "native_profile_invalid"
    status = 422


class NativeProfileExists(NativeError):
    code = "native_profile_exists"
    status = 409


class NativeProfileIdentityMismatch(NativeError):
    code = "native_profile_identity_mismatch"
    status = 409


class NativeIdentityMismatch(NativeError):
    code = "native_identity_mismatch"
    status = 409


class NativeSessionRequired(NativeError):
    code = "native_session_required"
    status = 401


class NativeSessionExpired(NativeError):
    code = "native_session_expired"
    status = 401


class NativeSessionRejected(NativeError):
    code = "native_session_rejected"
    status = 502


class NativeAccountDenied(NativeError):
    """La cuenta solicitada no pertenece al navegador autenticado."""

    code = "native_account_denied"
    status = 403


class NativeInstallationRequired(NativeError):
    code = "native_installation_required"
    status = 409


class NativeInstallationInvalid(NativeError):
    code = "native_installation_invalid"
    status = 422


class NativeSaveIdentityMismatch(NativeError):
    code = "native_save_identity_mismatch"
    status = 422


class NativeSavePlatformMismatch(NativeError):
    """La partida descargada pertenece a la otra plataforma.

    El gateway histórico selecciona la partida por distro, no por la cabecera
    ``x-platform``. Sin esta comprobación una cuenta con partidas Android e iOS
    podría recibir la copia equivocada al elegir una distribución.
    """

    code = "native_platform_mismatch"
    status = 409


class NativeLoginThrottled(NativeError):
    code = "native_login_throttled"
    status = 429

    def __init__(self, message: str, *, retry_after: int) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class NativePortalRejected(NativeError):
    code = "native_portal_rejected"
    status = 401


class NativePortalIdentityMismatch(NativeError):
    code = "native_portal_identity_mismatch"
    status = 409


class NativePortalChallengeRequired(NativeError):
    code = "native_portal_challenge_required"
    status = 409


class NativePortalUnavailable(NativeError):
    code = "native_portal_unavailable"
    status = 502


class NativeNoCloudSave(NativeError):
    code = "native_no_cloud_save"
    status = 404


class NativeSaveVersionAhead(NativeError):
    """El BlobSave remoto fue marcado con una versión de protocolo superior.

    No es un fallo de autenticación ni de formato. La copia existe, pero el
    servicio la considera más nueva que este cliente. Se impide cualquier
    subida para no agravar la discrepancia y se explica cómo recuperarla.
    """

    code = "native_save_version_ahead"
    status = 409


class NativeDeviceBindingThrottled(NativeError):
    """La cuenta está en espera para vincular un dispositivo nuevo.

    No es un fallo de credenciales ni de la instalación: el proveedor limita
    cuántas instalaciones nuevas se vinculan en una ventana. El par generado
    se conserva y se reutiliza; no se regenera para saltar la espera.
    """

    code = "native_device_binding_throttled"
    status = 429

    def __init__(self, message: str, *, retry_after: int) -> None:
        self.retry_after = max(60, min(int(retry_after), 7 * 86400))
        super().__init__(message)


class NativeWriteDisabled(NativeError):
    code = "native_write_disabled"
    status = 503


class NativeWriteDenied(NativeError):
    code = "native_write_denied"
    status = 403


class NativeWritePendingValidation(NativeError):
    """La plataforma permite preparar, pero su escritura aún no está validada.

    Es un estado distinto de ``native_write_denied``: la cuenta puede descargar,
    respaldar y preparar candidatos, pero SK-Under no envía nada a la nube hasta
    contar con evidencia propia de persistencia.
    """

    code = "native_write_pending_validation"
    status = 409
