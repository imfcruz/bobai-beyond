export default function RoleTransitionOverlay({ target }: { target: 'client' | 'employee' }) {
  return (
    <div className="role-transition" role="status" aria-live="polite">
      <div className="role-transition-mark">B</div>
      <strong>{target === 'employee' ? 'Abrindo ambiente do funcionário' : 'Voltando para sua conta'}</strong>
      <span>Preparando os dados da demonstração</span>
      <div className="role-transition-line"><i /></div>
    </div>
  )
}
