import { ApiProblem } from './api'

export const FRIENDLY: Record<string, string> = {
  invalid_request: 'Revisa los datos del formulario y vuelve a intentarlo.',
  native_https_required: 'Abre SK-Under mediante HTTPS para iniciar sesión.',
  native_credentials_rejected: 'El correo o la contraseña no son correctos.',
  native_login_throttled: 'Demasiados intentos. Espera antes de volver a intentarlo.',
  native_auth_throttled: 'ChillyRoom limitó los intentos. Espera antes de reintentar.',
  native_auth_unavailable: 'ChillyRoom no está disponible. Inténtalo más tarde.',
  native_auth_protocol: 'No se pudo comprobar la respuesta de ChillyRoom.',
  native_distribution_rejected: 'ChillyRoom rechazó la plataforma seleccionada.',
  native_identity_mismatch: 'No se pudo verificar la cuenta solicitada.',
  native_profile_identity_mismatch: 'Elige el perfil que corresponde a tu cuenta.',
  native_profile_required: 'Selecciona el perfil que corresponde a tu cuenta.',
  native_profile_missing: 'Pide al administrador que habilite el acceso para esta cuenta.',
  native_installation_required: 'Completa la configuración de acceso para consultar la partida.',
  native_portal_rejected: 'El correo o la contraseña no son correctos.',
  native_portal_identity_mismatch: 'No se pudo verificar la cuenta solicitada.',
  native_portal_challenge_required: 'ChillyRoom pidió una verificación adicional. Completa el acceso en su portal y vuelve a intentarlo.',
  native_portal_unavailable: 'El portal de ChillyRoom no está disponible. Inténtalo más tarde.',
  native_no_cloud_save: 'Sin partida en la nube. Guarda una copia desde Soul Knight y vuelve a intentarlo.',
  native_device_binding_throttled: 'ChillyRoom está aplicando una espera para este dispositivo.',
  native_save_error: 'No se pudo descargar la partida. Vuelve a intentarlo.',
  native_session_expired: 'La sesión caducó. Inicia sesión de nuevo.',
  native_session_required: 'Inicia sesión de nuevo para continuar.',
  native_session_rejected: 'ChillyRoom rechazó el acceso a la partida. Vuelve a intentarlo.',
  native_account_denied: 'La cuenta solicitada no pertenece a este navegador. Vuelve al dashboard.',
  native_store_unavailable: 'El acceso a la cuenta no está disponible. Inténtalo más tarde.',
  native_auth_disabled: 'El inicio de sesión está temporalmente deshabilitado.',
  native_write_disabled: 'La subida a la nube está deshabilitada.',
  native_write_denied: 'Esta cuenta tiene acceso de solo lectura.',
  cloud_write_disabled: 'La subida a la nube está deshabilitada.',
  cloud_session_rejected: 'ChillyRoom rechazó el acceso a la partida. Vuelve a iniciar sesión.',
  cloud_already_confirmed: 'Esta edición ya se subió. Verifica su respaldo en Partida.',
  native_platform_mismatch: 'La partida disponible pertenece a la otra plataforma. No se modificó nada.',
  native_save_identity_mismatch: 'No se pudo verificar que la partida pertenezca a tu cuenta.',
  cloud_remote_changed: 'La partida cambió en la nube. Descárgala de nuevo antes de editar.',
  network_error: 'No se pudo conectar con la API de SK-Under. Revisa tu conexión.',
  cloud_provider_unavailable: 'ChillyRoom no respondió al consultar la partida. Inténtalo más tarde.',
  cloud_provider_protocol: 'La respuesta de ChillyRoom tiene un formato inesperado.',
  invalid_aggregate: 'La partida descargada tiene un esquema de guardado incompatible.',
  unsupported_gems_structure: 'La versión o los tipos de los campos de gemas son incompatibles con el editor.',
  gems_field_missing: 'La partida descargada no contiene el saldo de gemas.',
  unsupported_serialization: 'La copia usa una serialización incompatible con la edición granular.',
  unknown_gems_dependencies: 'El saldo depende de contadores ausentes o fuera del intervalo compatible.',
  invalid_gems_value: 'Introduce un número entero dentro del intervalo de gemas indicado.',
  gems_verification_failed: 'La copia editada no superó la comprobación de integridad.',
  outdated_gems_draft: 'El borrador usa una edición anterior. Prepara de nuevo la edición antes de subirla.',
  invalid_fish_chip_value: 'Introduce un número entero no negativo dentro del intervalo de fichas de pesca.',
  invalid_fish_material_value: 'itemData.materials.material_fish no es un entero; no se sobrescribe automáticamente.',
  invalid_fish_progress_value: 'Introduce un número entero no negativo para el progreso acumulado de fichas.',
  fish_progress_field_missing: 'La partida no contiene itemData.cumulativeFishCount; el progreso acumulado no está disponible.',
  fish_progress_verification_failed: 'La copia editada del progreso acumulado no superó la comprobación de integridad.',
  fish_progress_edit: 'No se pudo preparar la edición del progreso acumulado de fichas.',
  unsupported_fish_progress_serialization: 'La partida no usa el formato JSON canónico admitido para editar el progreso acumulado.',
  outdated_fish_progress_draft: 'El borrador del progreso acumulado usa una edición anterior. Prepara de nuevo la edición antes de subirla.',
  fish_chip_field_missing: 'La partida no contiene gameData.fishChip; la edición de fichas no está disponible.',
  fish_material_field_missing: 'La partida no contiene itemData.materials; la edición de fichas no está disponible.',
  fish_chip_verification_failed: 'La copia editada de fichas no superó la comprobación de integridad.',
  fish_chip_edit: 'No se pudo preparar la edición de fichas de pesca.',
  outdated_fish_chip_draft: 'El borrador de fichas usa una edición anterior. Prepara de nuevo la edición antes de subirla.',
  characters_edit: 'No se pudo preparar el desbloqueo de personajes.',
  invalid_character_selection: 'Selecciona entre 1 y 42 personajes bloqueados, sin repetirlos.',
  unknown_character: 'La selección contiene un personaje que no pertenece al catálogo.',
  character_field_missing: 'La partida no contiene gameData.heroUnlock; el desbloqueo no está disponible.',
  unsupported_characters_structure: 'gameData.heroUnlock no tiene la estructura booleana esperada; no se sobrescribe.',
  character_catalog_missing: 'No está disponible el catálogo local de personajes.',
  character_verification_failed: 'La copia editada de personajes no superó la comprobación de integridad.',
  outdated_character_draft: 'El borrador de personajes usa una selección anterior. Prepara de nuevo el desbloqueo.',
  skills_edit: 'No se pudo preparar el desbloqueo de habilidades.',
  invalid_skill_selection: 'Selecciona entre 1 y 105 habilidades, sin repetir personaje e índice.',
  unknown_skill_character: 'La selección contiene un personaje que no pertenece al catálogo.',
  unknown_skill_index: 'La selección contiene una habilidad que no existe para ese personaje.',
  skill_field_missing: 'La partida no contiene gameData.heroSkillUnlock; el desbloqueo de habilidades no está disponible.',
  incomplete_skill_structure: 'La partida no contiene todas las posiciones de habilidad necesarias. No se crean estructuras faltantes.',
  unsupported_skills_structure: 'gameData.heroSkillUnlock no tiene la estructura esperada; no se sobrescribe.',
  skill_catalog_missing: 'No está disponible el catálogo local de habilidades.',
  skill_verification_failed: 'La copia editada de habilidades no superó la comprobación de integridad.',
  outdated_skill_draft: 'El borrador de habilidades usa una selección anterior. Prepara de nuevo el desbloqueo.',
  skins_edit: 'No se pudo preparar el desbloqueo de skins.',
  invalid_skin_selection: 'Selecciona entre 1 y 802 skins, sin repetir personaje e índice.',
  unknown_skin_character: 'La selección contiene un personaje que no pertenece al catálogo.',
  unknown_skin_index: 'La selección contiene una skin que no existe para ese personaje.',
  skin_field_missing: 'La partida no contiene gameData.skinLock; el desbloqueo de skins no está disponible.',
  incomplete_skin_structure: 'La partida no contiene la posición de skin seleccionada. No se crean entradas faltantes.',
  unsupported_skins_structure: 'gameData.skinLock no tiene la estructura esperada; no se sobrescribe.',
  skin_catalog_missing: 'No está disponible el catálogo local de skins.',
  skin_verification_failed: 'La copia editada de skins no superó la comprobación de integridad.',
  outdated_skin_draft: 'El borrador de skins usa una selección anterior. Prepara de nuevo el desbloqueo.',
  cloud_hash_mismatch: 'La huella del borrador no coincide con la del respaldo. Prepara de nuevo la edición.',
  backup_integrity: 'El respaldo no superó la comprobación de integridad.',
  backup_store: 'No se pudo guardar o leer el respaldo privado.',
  native_backup_unavailable: 'El almacén de respaldos no está disponible. Intenta actualizar el historial.',
  native_backup_legacy: 'La versión del servidor no incluye el historial actualizado. Actualiza el backend y vuelve a intentarlo.',
  native_backup_incompatible: 'El servidor respondió con un formato de historial incompatible. Actualiza la página y vuelve a intentarlo.',
  native_backup_restore_historical: 'La nube cambió desde la última descarga. Actualiza la partida y vuelve a intentar la restauración.',
}

export const BLOCKED_AUTO_SAVE_ERRORS = new Set([
  'native_no_cloud_save',
  'native_device_binding_throttled',
  'native_installation_required',
  'native_session_expired',
  'native_session_required',
  'native_session_rejected',
])

export function friendly(error: ApiProblem, fallback: string): ApiProblem {
  if (error.code === 'inconsistent_gems_balance') return error
  return new ApiProblem(
    FRIENDLY[error.code] ?? (error.message === 'El inicio de sesión requiere HTTPS en el editor y en la API.'
      ? FRIENDLY.native_https_required : fallback),
    [],
    error.code,
  )
}

export function historyProblemMessage(error: unknown): ApiProblem {
  if (!(error instanceof ApiProblem)) return new ApiProblem('No se pudieron cargar los respaldos.')
  if (error.code === 'native_backup_unavailable') {
    return new ApiProblem(
      'El almacén de respaldos no está disponible: falta el almacenamiento persistente. '
      + 'No se muestra un historial vacío porque el estado es desconocido.',
      [], error.code, error.status,
    )
  }
  const message = error.code === 'network_error'
    ? 'Error temporal de conexión. No se pudo consultar el historial; vuelve a intentarlo.'
    : error.status === 404
      ? 'El servidor desplegado no incluye el historial de respaldos. Actualiza el backend y vuelve a intentarlo.'
      : FRIENDLY[error.code] ?? error.message
  return new ApiProblem(message, [], error.code, error.status)
}

export function isExpired(error: ApiProblem) {
  return error.code === 'native_session_expired' || error.code === 'native_session_required'
}

export function distributionLabel(label: string) {
  return label.replace(/ \((?:GP(?:_VNM)?|IOS(?:_VNM|_CN)?)\)$/, '')
}

export function platformLabel(platform?: string | null) {
  return platform === 'ios' ? 'iOS' : platform === 'android' ? 'Android' : ''
}