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


class NativeInstallationRequired(NativeError):
    code = "native_installation_required"
    status = 409


class NativeInstallationInvalid(NativeError):
    code = "native_installation_invalid"
    status = 422


class NativeSaveIdentityMismatch(NativeError):
    code = "native_save_identity_mismatch"
    status = 422


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
