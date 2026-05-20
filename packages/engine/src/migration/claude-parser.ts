// CLAUDE.md section classifier for v1 -> v2 migration

export interface ClaudeSection {
  heading: string
  content: string
}

export interface ClaudeMdParseResult {
  preamble: string
  systemSections: ClaudeSection[]
  userSections: ClaudeSection[]
  isUnstructured: boolean
}

// Exact heading matches that go to config.yaml (system sections)
const SYSTEM_EXACT = new Set([
  'Role',
  'Execution Roles',
  'Workflow',
  'Skills',
  'Hard Rules',
  'Stance',
])

// Partial heading matches (case-insensitive substring)
const SYSTEM_CONTAINS = ['Personality', 'Communication', 'Emotional']

function isSystemHeading(heading: string): boolean {
  if (SYSTEM_EXACT.has(heading)) return true
  const lower = heading.toLowerCase()
  return SYSTEM_CONTAINS.some(kw => lower.includes(kw.toLowerCase()))
}

/**
 * Parse CLAUDE.md content into preamble + classified sections.
 * Supports both ## and # as section delimiters (# as fallback).
 */
export function parseClaudeMd(content: string): ClaudeMdParseResult {
  if (!content.trim()) {
    return { preamble: '', systemSections: [], userSections: [], isUnstructured: false }
  }

  // Try ## headings first
  const h2Pattern = /^## (.+)$/m
  if (h2Pattern.test(content)) {
    return parseSections(content, /^## /m, '## ')
  }

  // Fallback to # headings
  const h1Pattern = /^# (.+)$/m
  if (h1Pattern.test(content)) {
    return parseSections(content, /^# /m, '# ')
  }

  // No structured headings
  return {
    preamble: '',
    systemSections: [],
    userSections: [],
    isUnstructured: true,
  }
}

function parseSections(
  content: string,
  headingPattern: RegExp,
  headingPrefix: string,
): ClaudeMdParseResult {
  const parts = content.split(headingPattern)
  // parts[0] is preamble (before first heading)
  const preamble = (parts[0] ?? '').trim()

  const systemSections: ClaudeSection[] = []
  const userSections: ClaudeSection[] = []

  for (let i = 1; i < parts.length; i++) {
    const part = parts[i]
    if (part === undefined) continue
    const newlineIdx = part.indexOf('\n')
    const heading = newlineIdx === -1 ? part.trim() : part.slice(0, newlineIdx).trim()
    const sectionContent = newlineIdx === -1 ? '' : part.slice(newlineIdx + 1).trim()

    // Strip the prefix from heading if it accidentally snuck in (split behavior)
    const cleanHeading = heading.startsWith(headingPrefix)
      ? heading.slice(headingPrefix.length).trim()
      : heading

    const section: ClaudeSection = { heading: cleanHeading, content: sectionContent }

    if (isSystemHeading(cleanHeading)) {
      systemSections.push(section)
    } else {
      userSections.push(section)
    }
  }

  return { preamble, systemSections, userSections, isUnstructured: false }
}
