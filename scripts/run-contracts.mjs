/**
 * QA-00 root contract runner.
 *
 * Runs every contract validator and the deliberate-mismatch (negative) suite against the owned
 * fixtures in tests/contracts/, prints a `command | result | detail` table, appends it to
 * $GITHUB_STEP_SUMMARY when set, and exits 1 if any command fails.
 *
 * Usage: node scripts/run-contracts.mjs
 */

import { appendFileSync } from 'node:fs'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import { spawnSync } from 'node:child_process'

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..')

const COMMANDS = [
  'tests/contracts/validate-db-schema.mjs',
  'tests/contracts/validate-ui-types.mjs',
  'tests/contracts/validate-backend-models.mjs',
  'tests/contracts/validate-ai-schemas.mjs',
  'tests/contracts/validate-ai-pipeline.mjs',
  'tests/contracts/test-deliberate-mismatch.mjs',
]

const rows = COMMANDS.map((script) => {
  const run = spawnSync(process.execPath, [script], { cwd: ROOT, encoding: 'utf-8' })
  const output = `${run.stdout ?? ''}${run.stderr ?? ''}${run.error ? run.error.message : ''}`
  console.log(`\n$ node ${script}\n${output.trim()}`)
  const pass = run.status === 0
  const lines = output.split('\n').map((l) => l.trim())
  const caught = lines.filter((l) => l.startsWith('PASS') && !l.includes('real files')).length
  const detail = pass
    ? lines.find((l) => l.startsWith('Accepted known deviations')) ??
      lines.find((l) => l.startsWith('PASS ARCH-03:')) ??
      (caught ? `${caught} injected mismatch case(s) caught; real contract files unchanged` : 'no deviations')
    : lines.filter((l) => /^(x |✗|FAIL|Validator error)/.test(l)).slice(0, 3).join('; ') || `exit ${run.status}`
  return { command: `node ${script}`, result: pass ? 'PASS' : 'FAIL', detail }
})

const failed = rows.filter((r) => r.result === 'FAIL').length
const table = [
  '| Command | Result | Detail |',
  '|---|---|---|',
  ...rows.map((r) => `| \`${r.command}\` | ${r.result} | ${r.detail.replace(/\|/g, '\\|')} |`),
].join('\n')

console.log(`\n=== Contract checks: ${rows.length - failed}/${rows.length} PASS ===\n${table}\n`)
if (process.env.GITHUB_STEP_SUMMARY) {
  appendFileSync(process.env.GITHUB_STEP_SUMMARY, `## Contract checks (QA-00)\n\n${table}\n\n${failed ? `**${failed} FAIL**` : 'All PASS'}\n`)
}
process.exit(failed ? 1 : 0)
