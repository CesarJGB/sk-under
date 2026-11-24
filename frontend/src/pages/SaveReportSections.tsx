import type {
  SaveCharacter, SaveReport, SaveResourceGroup, SaveResourceItem,
} from '../api'

const amountFormat = new Intl.NumberFormat('es-MX')

function scalar(value: number | string | null | undefined): string {
  if (value == null) return '—'
  return typeof value === 'number' ? amountFormat.format(value) : value
}

function itemText(item: SaveResourceItem): string {
  if (item.plant != null) {
    const states = [
      item.state != null ? `estado ${item.state}` : '',
      item.fertilized === true ? 'fertilizada' : '',
      item.watered === true ? 'regada' : '',
    ].filter(Boolean)
    return `${item.plant}${states.length ? ` · ${states.join(' · ')}` : ''}`
  }
  if (item.name != null) return `${item.name}${item.count != null ? ` × ${amountFormat.format(item.count)}` : ''}`
  if (item.id != null) {
    if (item.count != null) return `${item.id} × ${amountFormat.format(item.count)}`
    if (item.text_length != null) return `${item.id} · contenido registrado (${amountFormat.format(item.text_length)} caracteres)`
    return item.id
  }
  return 'Entrada sin nombre'
}

function ResourceGroup({ group }: { group: SaveResourceGroup }) {
  const items = group.items ?? []
  return <details className="report-resource" data-testid={`resource-group-${group.id}`}>
    <summary>
      <span>{group.label}</span>
      <span className="report-count">{group.state === 'missing' ? 'Sin datos' : amountFormat.format(group.entries)}</span>
    </summary>
    <div className="report-resource-body">
      <p>{group.note}</p>
      {group.state === 'missing' && <p className="cloud-note">La partida no contiene esta sección.</p>}
      {group.state === 'null' && <p className="cloud-note">La sección aparece vacía (null).</p>}
      {group.value != null && <p className="report-scalar">{scalar(group.value)}</p>}
      {items.length > 0 && <ul className="report-items">
        {items.map((item, index) => <li key={`${group.id}-${index}`}>{itemText(item)}</li>)}
      </ul>}
      {group.truncated && <p className="cloud-note">La lista se muestra incompleta para mantener el informe ligero.</p>}
      {group.list_length != null && items.length === 0 && group.entries > 0 && <p className="cloud-note">
        {amountFormat.format(group.list_length)} registros; la estructura no se muestra porque no está validada.
      </p>}
    </div>
  </details>
}

function CharacterRow({ character }: { character: SaveCharacter }) {
  const unlocked = character.unlocked === true
  const level = character.level === '<missing>' ? 'sin dato' : scalar(character.level)
  const selectedSkill = character.skills.find((skill) => skill.key === character.selected_skill)
  const skillName = selectedSkill?.name ?? character.skill_options.find(
    (skill) => skill.index === character.selected_skill,
  )?.name
  return <li className="report-character" data-testid={`character-row-${character.code}`}>
    <div className="report-character-head">
      <strong>{character.name}</strong>
      <span className={`report-state ${unlocked ? 'available' : 'locked'}`}>
        {unlocked ? 'Disponible' : character.unlocked === '<missing>' ? 'Sin dato' : 'No desbloqueado'}
      </span>
    </div>
    <dl className="report-character-data">
      <div><dt>Nivel</dt><dd data-testid={`character-level-${character.code}`}>{level}</dd></div>
      <div><dt>Habilidad</dt><dd>{skillName ?? (character.selected_skill === '<missing>' ? 'sin dato' : `índice ${character.selected_skill}`)}</dd></div>
      <div><dt>Skin equipada</dt><dd>{character.equipped_skin?.name ?? 'ninguna registrada'}</dd></div>
    </dl>
    {character.skill_options.length > 0 && <details className="report-character-details">
      <summary>Habilidades del catálogo</summary>
      <ul>
        {character.skill_options.map((skill) => {
          const observed = character.skills.find((entry) => entry.key === skill.index)
          return <li key={skill.index}>
            {skill.name}
            {observed ? (observed.unlocked === true ? ' · desbloqueada' : ' · no desbloqueada') : ' · sin dato'}
          </li>
        })}
      </ul>
      <p className="cloud-note">
        {amountFormat.format(character.skins_recorded)} skins registradas. La posesión no se deduce de skinLock.
      </p>
    </details>}
  </li>
}

export function SaveReportSections({
  report, showCharacters = true,
}: { report: SaveReport; showCharacters?: boolean }) {
  const fish = report.fish_chips
  const characters = [...report.characters.items].sort((left, right) => {
    const availability = Number(right.unlocked === true) - Number(left.unlocked === true)
    return availability || left.name.localeCompare(right.name, 'es')
  })
  return <>
    <section className="cloud-section panel report-section" aria-labelledby="report-resources-title" data-testid="save-report">
      <div className="cloud-section-head">
        <div>
          <span className="cloud-kicker">Solo consulta</span>
          <h2 id="report-resources-title">Recursos</h2>
          <p className="cloud-state">
            Datos observados en la copia descargada. La edición de niveles, habilidades, skins y recursos no está habilitada.
          </p>
        </div>
        <span className="report-badge">Lectura</span>
      </div>
      <div className="report-fish">
        <div>
          <span>Fichas de pesca</span>
          <strong data-testid="fish-chip-balance">{fish.balance == null ? '—' : amountFormat.format(fish.balance)}</strong>
        </div>
        <p>
          {fish.balance_path ? `Campo candidato: ${fish.balance_path}. ` : 'No se encontró el campo candidato. '}
          La escritura conjunta de gameData.fishChip e itemData.materials.material_fish está
          confirmada por el propietario en un dispositivo Android: el saldo se muestra en el juego,
          la compra descuenta el importe correcto y el cliente oficial guarda el cambio.
        </p>
        <p data-testid="fish-chip-evidence">{fish.missing_proof}</p>
      </div>
      <div className="report-resource-grid">
        {report.resources.groups.map((group) => <ResourceGroup key={group.id} group={group} />)}
      </div>
      <p className="cloud-note">
        Los identificadores se muestran tal como aparecen. Fertilizantes y fragmentos son claves dentro de materiales;
        no se les atribuye una función no comprobada.
      </p>
    </section>

    {showCharacters && <section className="cloud-section panel report-section" aria-labelledby="report-characters-title">
      <div className="cloud-section-head">
        <div>
          <span className="cloud-kicker">Solo consulta</span>
          <h2 id="report-characters-title">Personajes</h2>
          <p className="cloud-state">
            {amountFormat.format(report.characters.counts.unlocked)} de {amountFormat.format(report.characters.counts.characters)} disponibles.
            Niveles y skins sin máximo o posesión validados.
          </p>
        </div>
        <span className="report-badge">Lectura</span>
      </div>
      <ul className="report-character-list">
        {characters.map((character) => <CharacterRow key={character.code} character={character} />)}
      </ul>
      <details className="report-limits">
        <summary>Alcance del informe</summary>
        <ul>
          {[...report.characters.notes, ...report.limitations].map((note) => <li key={note}>{note}</li>)}
        </ul>
      </details>
    </section>}
  </>
}