export type ConnectorSetupResponse = {
  data_source_id: string
  provider: string
  status: string
  sync_status: string | null
  last_synced_at: string | null
}

export type CsvUploadResponse = {
  data_source_id: string
  row_count: number
  parsed_rows: Array<Record<string, unknown>>
  parse_warnings: string[]
  sync_status: string
  last_synced_at: string
}
