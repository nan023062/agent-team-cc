import * as yaml from 'yaml'
import type { ModuleFrontmatter, ModuleSections } from './types.js'
import { FrontmatterParseError, InvalidModuleError } from './errors.js'

const SECTION_HEADING_MAP: Record<string, keyof ModuleSections> = {
  'Positioning': 'positioning',
  'Class Diagram': 'diagram',
  'Component Diagram': 'diagram',
  'Sub-module Relationship Diagram': 'diagram',
  'Key Decisions': 'keyDecisions',
}

export function parseModuleMd(
  raw: string,
  modulePath = '<inline>',
): { frontmatter: ModuleFrontmatter; sections: ModuleSections } {
  // --- Extract YAML frontmatter block ---
  const fmMatch = raw.match(/^---\r?\n([\s\S]*?)\r?\n---/)
  if (!fmMatch) {
    throw new FrontmatterParseError(modulePath, '', 'No frontmatter delimiters found')
  }

  const rawYaml = fmMatch[1] ?? ''
  let parsed: unknown
  try {
    parsed = yaml.parse(rawYaml)
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e)
    throw new FrontmatterParseError(modulePath, rawYaml, msg)
  }

  if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
    throw new FrontmatterParseError(modulePath, rawYaml, 'Frontmatter must be a YAML mapping object')
  }

  const obj = parsed as Record<string, unknown>

  // Validate required fields
  const violations: string[] = []
  if (typeof obj['name'] !== 'string' || obj['name'].trim() === '') {
    violations.push('name is required and must be a non-empty string')
  }
  if (typeof obj['owner'] !== 'string' || obj['owner'].trim() === '') {
    violations.push('owner is required and must be a non-empty string')
  }
  if (violations.length > 0) {
    throw new InvalidModuleError(modulePath, violations)
  }

  const frontmatter: ModuleFrontmatter = {
    name: (obj['name'] as string).trim(),
    owner: (obj['owner'] as string).trim(),
    description: typeof obj['description'] === 'string' ? obj['description'] : '',
    keywords: Array.isArray(obj['keywords'])
      ? (obj['keywords'] as unknown[]).map(String)
      : [],
    dependencies: Array.isArray(obj['dependencies'])
      ? (obj['dependencies'] as unknown[]).map(String)
      : [],
    includeDirs: Array.isArray(obj['includeDirs'])
      ? (obj['includeDirs'] as unknown[]).map(String)
      : [],
  }

  // --- Parse markdown body sections ---
  // Everything after the closing --- of frontmatter
  const afterFm = raw.slice((fmMatch.index ?? 0) + fmMatch[0].length)

  const sections = parseBodySections(afterFm)

  return { frontmatter, sections }
}

function parseBodySections(body: string): ModuleSections {
  const result: Record<string, string | undefined> = {}

  // Split by ## headings (h2 only per contract)
  const parts = body.split(/^## /m)
  // parts[0] is content before first ## heading — discard (typically blank)

  for (let i = 1; i < parts.length; i++) {
    const part = parts[i]
    if (part === undefined) continue
    const newlineIdx = part.indexOf('\n')
    const heading = newlineIdx === -1 ? part.trim() : part.slice(0, newlineIdx).trim()
    const content = newlineIdx === -1 ? '' : part.slice(newlineIdx + 1).trim()

    const mappedKey = SECTION_HEADING_MAP[heading]
    if (mappedKey !== undefined) {
      result[mappedKey] = content
    } else {
      result[heading] = content
    }
  }

  return result as ModuleSections
}
