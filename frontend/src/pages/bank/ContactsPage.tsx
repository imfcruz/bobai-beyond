import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { createBeneficiary, fetchBeneficiaries, fetchClients, setBeneficiaryFavorite } from '../../services/api'
import type { BeneficiaryResponse, ClientSummary } from '../../types'
import { Btn, ErrorBox, Spinner, inputStyle } from '../../components/ui'

function storedClient(): string {
  try { return localStorage.getItem('bobia_client_id') ?? '' } catch { return '' }
}

export default function ContactsPage() {
  const navigate = useNavigate()
  const [clients, setClients] = useState<ClientSummary[]>([])
  const [clientId, setClientId] = useState(storedClient())
  const [contacts, setContacts] = useState<BeneficiaryResponse[]>([])
  const [tab, setTab] = useState<'all' | 'favorites'>('all')
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [error, setError] = useState('')
  const [form, setForm] = useState({ name: '', pix: '', bank: '' })

  useEffect(() => {
    fetchClients().then(data => {
      setClients(data)
      setClientId(current => current || data[0]?.external_id || '')
    }).catch(() => setError('Não foi possível carregar as contas.'))
  }, [])

  useEffect(() => {
    if (!clientId) return
    try { localStorage.setItem('bobia_client_id', clientId) } catch { /* sem persistência */ }
    setLoading(true)
    fetchBeneficiaries(clientId)
      .then(data => { setContacts(data); setError('') })
      .catch(() => setError('Não foi possível carregar os contatos. Verifique se o backend está ativo.'))
      .finally(() => setLoading(false))
  }, [clientId])

  const shown = useMemo(() => {
    const term = search.trim().toLocaleLowerCase('pt-BR')
    return contacts.filter(contact => {
      if (tab === 'favorites' && !contact.is_favorite) return false
      return !term || `${contact.name} ${contact.bank_name} ${contact.account_hint}`.toLocaleLowerCase('pt-BR').includes(term)
    })
  }, [contacts, search, tab])

  async function toggleFavorite(contact: BeneficiaryResponse) {
    setSaving(contact.external_id)
    try {
      const updated = await setBeneficiaryFavorite(contact.external_id, !contact.is_favorite)
      setContacts(current => current
        .map(item => item.external_id === updated.external_id ? updated : item)
        .sort((a, b) => Number(b.is_favorite) - Number(a.is_favorite) || a.name.localeCompare(b.name)))
    } catch {
      setError('Não foi possível atualizar o favorito.')
    } finally { setSaving('') }
  }

  async function addContact() {
    if (!clientId || !form.name.trim() || !form.pix.trim() || !form.bank.trim()) return
    setSaving('new'); setError('')
    try {
      const created = await createBeneficiary(clientId, {
        name: form.name.trim(),
        account_hint: `Chave Pix: ${form.pix.trim()} (fictícia)`,
        bank_name: form.bank.trim(),
      })
      setContacts(current => [...current, created].sort((a, b) => Number(b.is_favorite) - Number(a.is_favorite) || a.name.localeCompare(b.name)))
      setForm({ name: '', pix: '', bank: '' })
      setShowForm(false)
    } catch {
      setError('Não foi possível cadastrar o contato. Confira os dados e tente novamente.')
    } finally { setSaving('') }
  }

  return (
    <div style={{ maxWidth: 940, margin: '0 auto' }}>
      <header className="section-heading">
        <div>
          <span className="eyebrow">AGENDA PIX</span>
          <h1>Seus contatos</h1>
          <p>Escolha um contato salvo ou cadastre uma nova chave fictícia.</p>
        </div>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          <select value={clientId} onChange={event => setClientId(event.target.value)} style={{ ...inputStyle, width: 210 }} aria-label="Conta">
            {clients.map(client => <option key={client.external_id} value={client.external_id}>{client.name}</option>)}
          </select>
          <Btn onClick={() => setShowForm(value => !value)}>{showForm ? 'Fechar' : 'Novo contato'}</Btn>
        </div>
      </header>

      {error && <div style={{ marginBottom: 16 }}><ErrorBox message={error} /></div>}

      {showForm && (
        <section className="glass-panel contact-form animate-fadein">
          <div><h2>Novo contato</h2><p>Os dados são apenas para a demonstração acadêmica.</p></div>
          <div className="contact-form-grid">
            <label>Nome<input value={form.name} onChange={event => setForm({ ...form, name: event.target.value })} placeholder="Nome completo" /></label>
            <label>Chave Pix<input value={form.pix} onChange={event => setForm({ ...form, pix: event.target.value })} placeholder="E-mail, telefone ou chave" /></label>
            <label>Instituição<input value={form.bank} onChange={event => setForm({ ...form, bank: event.target.value })} placeholder="Banco fictício" /></label>
          </div>
          <div style={{ display: 'flex', justifyContent: 'flex-end' }}><Btn onClick={addContact} disabled={saving === 'new' || !form.name || !form.pix || !form.bank}>{saving === 'new' ? 'Salvando…' : 'Salvar contato'}</Btn></div>
        </section>
      )}

      <section className="glass-panel contacts-panel">
        <div className="contacts-toolbar">
          <div className="segmented-control" role="tablist" aria-label="Filtro de contatos">
            <button className={tab === 'all' ? 'active' : ''} onClick={() => setTab('all')}>Todos <span>{contacts.length}</span></button>
            <button className={tab === 'favorites' ? 'active' : ''} onClick={() => setTab('favorites')}>Favoritos <span>{contacts.filter(item => item.is_favorite).length}</span></button>
          </div>
          <input className="contact-search" value={search} onChange={event => setSearch(event.target.value)} placeholder="Buscar nome, banco ou chave" aria-label="Buscar contatos" />
        </div>

        {loading ? <div className="center-loader"><Spinner size={30} /></div> : shown.length === 0 ? (
          <div className="empty-state"><strong>Nenhum contato encontrado</strong><span>Altere a busca ou cadastre um novo contato.</span></div>
        ) : (
          <div className="contact-grid">
            {shown.map(contact => (
              <article className="contact-card" key={contact.external_id}>
                <button className="favorite-button" onClick={() => toggleFavorite(contact)} disabled={saving === contact.external_id} aria-label={contact.is_favorite ? `Remover ${contact.name} dos favoritos` : `Favoritar ${contact.name}`} title={contact.is_favorite ? 'Remover dos favoritos' : 'Adicionar aos favoritos'}>
                  {contact.is_favorite ? '★' : '☆'}
                </button>
                <div className="contact-avatar">{contact.name.split(' ').slice(0, 2).map(part => part[0]).join('').toUpperCase()}</div>
                <div className="contact-copy"><h3>{contact.name}</h3><p>{contact.bank_name}</p><span>{contact.account_hint.replace(' (fictícia)', '')}</span></div>
                <button className="contact-transfer" onClick={() => navigate('/bank/transfer', { state: { clientId, beneficiaryId: contact.external_id } })}>Fazer Pix</button>
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
