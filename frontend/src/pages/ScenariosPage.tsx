// Tela 6 — Demonstração de Cenários
// Seleciona cenário pré-configurado, carrega dados e permite executar o fluxo.

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getApiErrorMessage, initiateTransfer, resetDemo } from '../services/api'
import {
  Card, CardHeader, Btn, ErrorBox, Spinner, clr, fmtBRL,
} from './ui'

interface Scenario {
  id: string
  letter: string
  color: string
  title: string
  subtitle: string
  description: string
  expected: string
  client_id: string
  client_name: string
  beneficiary_id: string
  beneficiary_name: string
  amount: string
  purpose: string
  device: boolean
  tags: string[]
}

const SCENARIOS: Scenario[] = [
  {
    id: 'A',
    letter: 'A',
    color: '#16a34a',
    title: 'Operação Normal',
    subtitle: 'Baixo risco — liberação automática esperada',
    description:
      'Transferência dentro do padrão histórico do cliente. Beneficiário conhecido, valor dentro da média, dispositivo reconhecido. Sem sinais de risco.',
    expected: 'LIBERADA automaticamente',
    client_id: 'client-ana-costa',
    client_name: 'Ana Costa',
    beneficiary_id: 'ben-fornecedor-alpha',
    beneficiary_name: 'Fornecedor Alpha Ltda.',
    amount: '1200.00',
    purpose: 'Pagamento mensal de serviço',
    device: true,
    tags: ['baixo risco', 'beneficiário conhecido', 'dispositivo reconhecido'],
  },
  {
    id: 'B',
    letter: 'B',
    color: '#d97706',
    title: 'Operação Incomum',
    subtitle: 'Risco médio — confirmação ou verificação esperada',
    description:
      'Beneficiário cadastrado recentemente, valor significativamente acima da média histórica do cliente. Padrão comportamental desviante.',
    expected: 'CONFIRMAÇÃO CONTEXTUAL ou VERIFICAÇÃO ADICIONAL',
    client_id: 'client-carlos-mendes',
    client_name: 'Carlos Mendes',
    beneficiary_id: 'ben-empresa-xpto',
    beneficiary_name: 'Empresa Desconhecida XPTO',
    amount: '18000.00',
    purpose: 'Pagamento para fornecedor novo',
    device: true,
    tags: ['beneficiário novo', 'valor acima da média', 'risco médio'],
  },
  {
    id: 'C',
    letter: 'C',
    color: '#dc2626',
    title: 'Possível Engenharia Social',
    subtitle: 'Risco crítico — revisão humana esperada',
    description:
      'Múltiplos indicadores de engenharia social: finalidade menciona instrução de terceiro (banco), dispositivo não reconhecido, limite alterado recentemente, beneficiário novo.',
    expected: 'ESCALADA para revisão humana',
    client_id: 'client-beatriz-santos',
    client_name: 'Beatriz Santos',
    beneficiary_id: 'ben-conta-seguranca',
    beneficiary_name: 'Conta Segurança BB',
    amount: '4000.00',
    purpose: 'Funcionário do banco me pediu para proteger minha conta',
    device: false,
    tags: ['engenharia social', 'instrução de terceiro', 'dispositivo não reconhecido', 'risco crítico'],
  },
]

type ScenarioState = 'idle' | 'running' | 'done' | 'error'

export default function ScenariosPage() {
  const navigate = useNavigate()
  const [selected, setSelected] = useState<string | null>(null)
  const [state, setState] = useState<ScenarioState>('idle')
  const [error, setError] = useState<string | null>(null)
  const [resetting, setResetting] = useState(false)
  const [resetMsg, setResetMsg] = useState<string | null>(null)

  const scenario = SCENARIOS.find(s => s.id === selected)

  async function handleRun() {
    if (!scenario) return
    setState('running')
    setError(null)
    try {
      const result = await initiateTransfer({
        client_external_id: scenario.client_id,
        beneficiary_external_id: scenario.beneficiary_id,
        amount: scenario.amount,
        purpose: scenario.purpose,
        device_recognized: scenario.device,
      })
      navigate('/bank/analysis', { state: { result } })
    } catch (err: unknown) {
      setError(getApiErrorMessage(err, 'Não foi possível executar o cenário. Reinicie os dados e tente novamente.'))
      setState('error')
    }
  }

  async function handleReset() {
    setResetting(true)
    setResetMsg(null)
    try {
      await resetDemo()
      setResetMsg('Dados de demonstração reiniciados com sucesso.')
    } catch {
      setResetMsg('Erro ao reiniciar dados de demonstração.')
    } finally {
      setResetting(false)
    }
  }

  return (
    <div style={{ maxWidth: 860, margin: '0 auto' }}>
      <Card>
        <CardHeader
          title="Demonstração guiada"
          subtitle="Compare como o sistema reage a uma operação comum, uma movimentação incomum e um possível golpe"
        />

        <div style={{
          background: '#f0f7ff', border: '1px solid #bfdbfe',
          borderRadius: 8, padding: '10px 14px', marginBottom: 20, fontSize: 12, color: '#1e40af',
        }}>
          Os cenários utilizam dados sintéticos pré-carregados. Execute <strong>Reiniciar dados</strong>{' '}
          antes de cada sessão para garantir o estado inicial correto.
        </div>

        {/* Reiniciar dados */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20 }}>
          <Btn variant="ghost" onClick={handleReset} disabled={resetting} small>
            {resetting ? <span style={{ display: 'flex', gap: 6, alignItems: 'center' }}><Spinner size={12} />Reiniciando…</span> : 'Reiniciar dados de demo'}
          </Btn>
          {resetMsg && (
            <span style={{
              fontSize: 12,
              color: resetMsg.startsWith('Dados') ? '#166534' : '#dc2626',
            }}>{resetMsg}</span>
          )}
        </div>

        {/* Grade de cenários */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16, marginBottom: 20 }}>
          {SCENARIOS.map(s => (
            <button
              key={s.id}
              onClick={() => { setSelected(s.id); setError(null); setState('idle') }}
              style={{
                border: selected === s.id
                  ? `2px solid ${s.color}`
                  : `1px solid ${clr.border}`,
                borderRadius: 10,
                padding: 16,
                background: selected === s.id ? s.color + '0e' : '#fff',
                cursor: 'pointer',
                textAlign: 'left',
                transition: 'border-color 0.15s, background 0.15s',
                fontFamily: 'inherit',
              }}
            >
              <div style={{
                display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                width: 28, height: 28, borderRadius: '50%',
                background: s.color, color: '#fff',
                fontWeight: 800, fontSize: 13, marginBottom: 10,
              }}>
                {s.letter}
              </div>
              <div style={{ fontWeight: 700, fontSize: 14, color: clr.text, marginBottom: 4 }}>{s.title}</div>
              <div style={{ fontSize: 12, color: s.color, fontWeight: 600, marginBottom: 8 }}>{s.subtitle}</div>
              <div style={{ fontSize: 12, color: clr.textMuted, lineHeight: 1.5 }}>{s.description}</div>
              <div style={{ marginTop: 10, display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                {s.tags.map(t => (
                  <span key={t} style={{
                    background: s.color + '15', color: s.color,
                    borderRadius: 4, padding: '1px 6px', fontSize: 10, fontWeight: 600,
                  }}>{t}</span>
                ))}
              </div>
            </button>
          ))}
        </div>

        {/* Painel de detalhes do cenário */}
        {scenario && (
          <div style={{
            border: `1px solid ${scenario.color}44`,
            borderLeft: `4px solid ${scenario.color}`,
            borderRadius: 8, padding: 16,
            background: scenario.color + '06',
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
              <div>
                <h3 style={{ margin: '0 0 4px', color: clr.text, fontSize: 15 }}>
                  Cenário {scenario.letter} — {scenario.title}
                </h3>
                <p style={{ margin: 0, fontSize: 13, color: clr.textMuted }}>{scenario.description}</p>
              </div>
              <div style={{
                background: scenario.color, color: '#fff',
                borderRadius: 6, padding: '4px 10px',
                fontSize: 11, fontWeight: 700, whiteSpace: 'nowrap',
              }}>
                Esperado: {scenario.expected}
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '6px 20px', fontSize: 13, marginBottom: 14 }}>
              <div><span style={{ color: clr.textMuted }}>Cliente:</span> <strong>{scenario.client_name}</strong></div>
              <div><span style={{ color: clr.textMuted }}>Beneficiário:</span> <strong>{scenario.beneficiary_name}</strong></div>
              <div><span style={{ color: clr.textMuted }}>Valor:</span> <strong>{fmtBRL(scenario.amount)}</strong></div>
              <div><span style={{ color: clr.textMuted }}>Dispositivo:</span> {scenario.device ? 'Reconhecido' : 'Não reconhecido'}</div>
              <div style={{ gridColumn: '1/-1' }}>
                <span style={{ color: clr.textMuted }}>Finalidade:</span>{' '}
                <em>"{scenario.purpose}"</em>
              </div>
            </div>

            {error && <div style={{ marginBottom: 12 }}><ErrorBox message={error} /></div>}

            <Btn
              onClick={handleRun}
              disabled={state === 'running'}
              style={{ background: scenario.color, border: 'none' } as React.CSSProperties}
            >
              {state === 'running'
                ? <span style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                    <Spinner size={14} color="#fff" /> Executando pipeline…
                  </span>
                : `Executar cenário ${scenario.letter}`}
            </Btn>
          </div>
        )}

        {!selected && (
          <div style={{ textAlign: 'center', padding: '20px 0', color: clr.textLight, fontSize: 14 }}>
            Selecione um cenário acima para ver os detalhes e executar o pipeline.
          </div>
        )}
      </Card>
    </div>
  )
}
