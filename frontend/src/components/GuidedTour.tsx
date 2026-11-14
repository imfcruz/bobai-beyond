import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import NavIcon from './NavIcon'

const STORAGE_KEY = 'bobia_guided_tour_v1'
const STEPS = [
  { route: '/bank', kicker: 'Conta do cliente', title: 'Acompanhe sua conta', text: 'Consulte saldo, limite Pix e movimentações recentes. Use o seletor para alternar entre os clientes sintéticos.' },
  { route: '/bank/contacts', kicker: 'Contatos', title: 'Organize beneficiários', text: 'Cadastre uma chave fictícia, pesquise contatos e marque os beneficiários usados com mais frequência.' },
  { route: '/bank/transfer', kicker: 'Pix adaptativo', title: 'Escolha débito ou crédito', text: 'Monte a transferência e escolha a origem do valor. A análise ocorre em segundo plano e adapta a verificação ao contexto.' },
  { route: '/bank/cards', kicker: 'Cartões', title: 'Controle o limite', text: 'Interaja com o cartão, acompanhe o limite disponível e envie uma solicitação de aumento para análise humana.' },
  { route: '/admin/clients', kicker: 'Ambiente do funcionário', title: 'Analise clientes e pendências', text: 'Consulte cada cliente, as transferências sinalizadas e os pedidos de limite que aguardam uma decisão.' },
  { route: '/admin/metrics', kicker: 'Governança', title: 'Acompanhe as decisões', text: 'Use métricas, auditoria e cenários para verificar risco, divergências, tempo de análise e participação humana.' },
] as const

export default function GuidedTour() {
  const navigate = useNavigate()
  const [open, setOpen] = useState(() => {
    try { return !localStorage.getItem(STORAGE_KEY) } catch { return false }
  })
  const [step, setStep] = useState(0)
  const current = STEPS[step]

  function close() {
    setOpen(false)
    try { localStorage.setItem(STORAGE_KEY, 'completed') } catch { /* indisponível */ }
  }
  function restart() { setStep(0); setOpen(true); navigate(STEPS[0].route) }
  function move(nextStep: number) { setStep(nextStep); navigate(STEPS[nextStep].route) }
  function next() { if (step === STEPS.length - 1) close(); else move(step + 1) }

  return <>
    <button className="tour-help-button" onClick={restart} aria-label="Abrir apresentação guiada"><NavIcon name="demo" size={17} />Como usar</button>
    {open && <section className="guided-tour" role="dialog" aria-modal="false" aria-labelledby="tour-title" aria-live="polite">
      <div className="guided-tour-progress" aria-label={`Etapa ${step + 1} de ${STEPS.length}`}>{STEPS.map((_, index) => <i key={index} className={index <= step ? 'active' : ''} />)}</div>
      <button className="guided-tour-close" onClick={close} aria-label="Fechar apresentação">×</button>
      <span>{current.kicker}</span><h2 id="tour-title">{current.title}</h2><p>{current.text}</p>
      <footer><small>{step + 1} de {STEPS.length}</small><div>{step > 0 && <button className="tour-secondary" onClick={() => move(step - 1)}>Voltar</button>}<button className="tour-primary" onClick={next}>{step === STEPS.length - 1 ? 'Concluir' : 'Próximo'}</button></div></footer>
    </section>}
  </>
}
