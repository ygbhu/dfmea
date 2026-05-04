/* global process */
/**
 * OpenCode Quality Assistant npm plugin entrypoint.
 *
 * The OpenCode package is the product entrypoint. It injects host context and
 * delegates all quality operations to the Python engine through CLI contracts.
 */

import { existsSync, readdirSync } from "fs"
import { join, resolve } from "path"

const processedSessions = new Set()

function findUp(start, predicate) {
  let current = resolve(start)
  while (true) {
    if (predicate(current)) return current
    const parent = resolve(current, "..")
    if (parent === current) return null
    current = parent
  }
}

function hasQualityWorkspace(directory) {
  return existsSync(join(directory, ".quality", "workspace.yaml"))
}

function hasSourceCheckout(directory) {
  return existsSync(join(directory, "engine", "pyproject.toml"))
}

function listProjects(root) {
  const projectsRoot = join(root, "projects")
  if (!existsSync(projectsRoot)) return []
  try {
    return readdirSync(projectsRoot, { withFileTypes: true })
      .filter(entry => entry.isDirectory())
      .map(entry => entry.name)
      .filter(name => existsSync(join(projectsRoot, name, "project.yaml")))
      .sort()
  } catch {
    return []
  }
}

function commandPrefix(root) {
  if (existsSync(join(root, "scripts", "quality_cli.py"))) {
    return {
      quality: "python .\\scripts\\quality_cli.py quality",
      dfmea: "python .\\scripts\\quality_cli.py dfmea",
    }
  }
  return { quality: "quality", dfmea: "dfmea" }
}

function buildContext(directory) {
  const root =
    findUp(directory, hasQualityWorkspace) ||
    findUp(directory, hasSourceCheckout) ||
    resolve(directory)
  const commands = commandPrefix(root)
  const projects = listProjects(root)
  const projectLine =
    projects.length === 0
      ? "No quality projects detected under projects/."
      : `Detected quality projects: ${projects.join(", ")}.`

  return `<using-quality-assistant>
Product stance: OpenCode-bound quality assistant.
OpenCode is the required host; Python is the authoritative quality engine behind it.
Use CLI/shared-core write paths only.
Quality command: ${commands.quality}
Method discovery: ${commands.quality} method list --workspace . [--project <slug>]
Active method command: DFMEA uses ${commands.dfmea}
${projectLine}
Rules:
- DFMEA and PFMEA are dynamic quality methods exposed through OpenCode.
- PFMEA is currently planned/placeholder only unless \`quality method list\` reports it active.
- Do not introduce SQLite/PostgreSQL target storage.
- Do not edit generated projections or exports as source.
- Use validation before snapshot/export workflows.
</using-quality-assistant>`
}

function markInjected(part) {
  part.metadata = {
    ...(part.metadata || {}),
    qualityAssistant: { sessionStart: true },
  }
}

function injectText(output, context) {
  const parts = output?.parts || []
  const textPartIndex = parts.findIndex(part => part.type === "text" && part.text !== undefined)

  if (textPartIndex !== -1) {
    const originalText = parts[textPartIndex].text || ""
    parts[textPartIndex].text = `${context}\n\n---\n\n${originalText}`
    markInjected(parts[textPartIndex])
    return
  }

  const injectedPart = { type: "text", text: context }
  markInjected(injectedPart)
  parts.unshift(injectedPart)
}

export default async ({ directory }) => {
  return {
    event: ({ event }) => {
      if (event?.type === "session.compacted" && event?.properties?.sessionID) {
        processedSessions.delete(event.properties.sessionID)
      }
    },

    "chat.message": async (input, output) => {
      if (process.env.OPENCODE_NON_INTERACTIVE === "1") return
      const sessionID = input?.sessionID || "default"
      if (processedSessions.has(sessionID)) return

      const context = buildContext(directory)
      injectText(output, context)
      processedSessions.add(sessionID)
    },
  }
}
