#!/usr/bin/env node
/* global console, process */

import { existsSync } from "fs"
import { dirname, join, resolve } from "path"
import { fileURLToPath } from "url"
import { spawnSync } from "child_process"

const PLUGIN_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..")
const REPO_ROOT = resolve(PLUGIN_ROOT, "..")

function main(argv) {
  const { command, options, positional } = parseArgs(argv)
  if (options.help || command === "help") {
    printUsage()
    return 0
  }

  if (command === "doctor") return doctor(options)
  if (command === "status") return status(options)
  if (command === "init") return init(options, positional)

  console.error(`Unknown command: ${command || "(missing)"}`)
  printUsage()
  return 2
}

function parseArgs(argv) {
  const options = { workspace: ".", force: false, help: false }
  const positional = []
  let command = ""

  for (let index = 0; index < argv.length; index += 1) {
    const value = argv[index]
    if (!command && !value.startsWith("-")) {
      command = value
      continue
    }
    if (value === "--workspace") {
      options.workspace = argv[index + 1]
      index += 1
      continue
    }
    if (value === "--force") {
      options.force = true
      continue
    }
    if (value === "-h" || value === "--help") {
      options.help = true
      continue
    }
    positional.push(value)
  }

  return { command, options, positional }
}

function doctor(options) {
  const workspace = resolve(options.workspace)
  const quality = qualityCommand(workspace)
  const checks = [
    ["node", process.version],
    ["python", commandVersion("python", ["--version"])],
    ["opencode", commandVersion("opencode", ["--version"])],
    ["qualityCommand", quality.join(" ")],
  ]

  console.log("OpenCode Quality Assistant doctor")
  for (const [name, value] of checks) {
    console.log(`- ${name}: ${value || "not found"}`)
  }

  const methods = runQualityJson(workspace, ["method", "list", "--workspace", workspace])
  if (!methods.ok) return 1
  console.log("- methods: " + summarizeMethods(methods.payload))
  return 0
}

function status(options) {
  const workspace = resolve(options.workspace)
  const methods = runQualityJson(workspace, ["method", "list", "--workspace", workspace])
  if (!methods.ok) return 1
  console.log(JSON.stringify(methods.payload, null, 2))
  return 0
}

function init(options) {
  const workspace = resolve(options.workspace)
  const args = ["opencode", "init", "--workspace", workspace, "--npm-plugin"]
  if (options.force) args.push("--force")
  const result = runQualityJson(workspace, args)
  if (!result.ok) return 1
  console.log(JSON.stringify(result.payload, null, 2))
  return 0
}

function qualityCommand(workspace) {
  const sourceRunner = join(workspace, "scripts", "quality_cli.py")
  if (existsSync(sourceRunner)) return ["python", sourceRunner, "quality"]

  const repoRunner = join(REPO_ROOT, "scripts", "quality_cli.py")
  if (existsSync(repoRunner)) return ["python", repoRunner, "quality"]

  return ["quality"]
}

function runQualityJson(workspace, args) {
  const command = qualityCommand(workspace)
  const completed = spawnSync(command[0], [...command.slice(1), ...args], {
    cwd: workspace,
    encoding: "utf8",
  })

  if (completed.status !== 0) {
    if (completed.stdout) console.error(completed.stdout.trim())
    if (completed.stderr) console.error(completed.stderr.trim())
    return { ok: false, payload: null }
  }

  try {
    return { ok: true, payload: JSON.parse(completed.stdout) }
  } catch {
    console.error(completed.stdout.trim())
    return { ok: false, payload: null }
  }
}

function commandVersion(command, args) {
  const completed = spawnSync(command, args, { encoding: "utf8" })
  if (completed.error || completed.status !== 0) return null
  return (completed.stdout || completed.stderr).trim()
}

function summarizeMethods(payload) {
  const methods = payload?.data?.methods || []
  return methods
    .map(method => `${method.id}:${method.status}${method.implemented ? "" : ":placeholder"}`)
    .join(", ")
}

function printUsage() {
  console.log(`Usage: opencode-quality <doctor|status|init> [--workspace <path>] [--force]

Commands:
  doctor   Check Node, Python, OpenCode, and quality method discovery.
  status   Print quality method discovery JSON.
  init     Install project-local OpenCode commands, skills, plugin hook, and opencode.json.
`)
}

process.exitCode = main(process.argv.slice(2))
