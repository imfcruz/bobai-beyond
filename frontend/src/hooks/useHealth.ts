// Hook para buscar o status de saúde da API

import { useEffect, useState } from 'react'
import { fetchHealth } from '../services/api'
import type { HealthResponse } from '../types'

export function useHealth() {
  const [data, setData] = useState<HealthResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchHealth()
      .then(setData)
      .catch((err) => setError(err?.message ?? 'Erro ao conectar com o backend'))
      .finally(() => setLoading(false))
  }, [])

  return { data, loading, error }
}
