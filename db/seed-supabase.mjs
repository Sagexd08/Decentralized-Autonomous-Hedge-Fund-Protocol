import fs from 'node:fs'
import path from 'node:path'
import postgres from 'postgres'

const repoRoot = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..')
const envPath = path.join(repoRoot, '.env')

function readDotEnvFile(filePath) {
  if (!fs.existsSync(filePath)) {
    return {}
  }

  const lines = fs.readFileSync(filePath, 'utf8').split(/\r?\n/)
  const values = {}

  for (const line of lines) {
    const trimmed = line.trim()
    if (!trimmed || trimmed.startsWith('#') || !trimmed.includes('=')) {
      continue
    }

    const separatorIndex = trimmed.indexOf('=')
    const key = trimmed.slice(0, separatorIndex).trim()
    let value = trimmed.slice(separatorIndex + 1).trim()

    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1)
    }

    values[key] = value
  }

  return values
}

const envValues = readDotEnvFile(envPath)
const databaseUrl = process.env.DATABASE_URL || envValues.DATABASE_URL

if (!databaseUrl) {
  throw new Error('DATABASE_URL is missing. Set it in the environment or the repo root .env file.')
}

const schemaSql = fs.readFileSync(path.join(repoRoot, 'db', 'schema.sql'), 'utf8')
const seedSql = fs.readFileSync(path.join(repoRoot, 'db', 'seed.sql'), 'utf8')

const sql = postgres(databaseUrl, {
  max: 1,
  ssl: 'require',
})

try {
  console.log('Applying db/schema.sql...')
  await sql.unsafe(schemaSql)

  console.log('Applying db/seed.sql...')
  await sql.unsafe(seedSql)

  const [summary] = await sql`
    select
      (select count(*)::int from pools) as pools,
      (select count(*)::int from agents) as agents,
      (select count(*)::int from proposals) as proposals,
      (select count(*)::int from contracts) as contracts
  `

  console.log('Seed complete:', summary)
} finally {
  await sql.end({ timeout: 5 })
}
