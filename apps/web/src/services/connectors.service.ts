import { apiRequest } from '@/lib/api-client'
import type {
  ConnectorSetupResponse,
  CsvUploadResponse,
} from '@/types'

export function createCsvConnector(accessToken: string): Promise<ConnectorSetupResponse> {
  return apiRequest<ConnectorSetupResponse>('/api/connectors/setup', {
    method: 'POST',
    accessToken,
  })
}

export function uploadCsv(
  accessToken: string,
  dataSourceId: string,
  file: File,
): Promise<CsvUploadResponse> {
  const body = new FormData()
  body.append('file', file)

  return apiRequest<CsvUploadResponse>(`/api/connectors/csv/${dataSourceId}/upload`, {
    method: 'POST',
    accessToken,
    body,
  })
}
