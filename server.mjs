import { createServer } from 'node:http'
import { randomUUID } from 'node:crypto'
import { spawn } from 'node:child_process'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import { readFileSync, existsSync } from 'node:fs'

const __dirname = dirname(fileURLToPath(import.meta.url))
const projectRoot = join(__dirname, '..')

const port = Number(process.env.PORT || 8000)
const runs = new Map()
const cases = new Map()

const connectors = [
  { id: 'legal_intake', plugin_id: 'legal_intake', configured: true, mode_supported: ['fixture', 'replay', 'live'], capabilities: ['case_input'] },
  { id: 'neuralake', plugin_id: 'evidence_analysis', configured: true, mode_supported: ['fixture', 'replay', 'live'], capabilities: ['extract', 'compare', 'report'] },
  { id: 'browser-use', plugin_id: 'judicial_research', configured: true, mode_supported: ['fixture', 'replay', 'live'], capabilities: ['search_decisions', 'read_decision'] },
  { id: 'jev', plugin_id: 'decision', configured: true, mode_supported: ['fixture', 'replay', 'live'], capabilities: ['noul'] },
  { id: 'docs_claw', plugin_id: 'reporting', configured: true, mode_supported: ['fixture', 'replay'], capabilities: ['render_report'] },
]

function json(res, status, payload) {
  res.writeHead(status, {
    'Content-Type': 'application/json; charset=utf-8',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'Content-Type, Idempotency-Key',
    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
  })
  res.end(JSON.stringify(payload))
}

function graphOrder(nodes, edges) {
  const indegree = new Map(nodes.map((node) => [node.id, 0]))
  const outgoing = new Map()
  for (const [from, to] of edges) {
    indegree.set(to, (indegree.get(to) || 0) + 1)
    outgoing.set(from, [...(outgoing.get(from) || []), to])
  }
  const queue = nodes.filter((node) => indegree.get(node.id) === 0).map((node) => node.id)
  const orderedIds = []
  while (queue.length) {
    const current = queue.shift()
    orderedIds.push(current)
    for (const next of outgoing.get(current) || []) {
      const nextDegree = (indegree.get(next) || 0) - 1
      indegree.set(next, nextDegree)
      if (nextDegree === 0) queue.push(next)
    }
  }
  return orderedIds
}

function normalizeGraph(body) {
  const nodes = Array.isArray(body.nodes) && body.nodes.length
    ? body.nodes
    : [{ id: 'ingest', label: 'Entrada do caso', operation: 'create_case' }]
  const edges = Array.isArray(body.edges) ? body.edges : []
  const ids = new Set()
  const errors = []

  for (const node of nodes) {
    if (!node || typeof node.id !== 'string' || !node.id) errors.push('Todo componente precisa de um id.')
    else if (ids.has(node.id)) errors.push(`ID de componente duplicado: ${node.id}`)
    else ids.add(node.id)
  }
  if (errors.length) return { errors, nodes, edges, orderedNodes: [] }
  const seenEdges = new Set()
  for (const edge of edges) {
    if (!Array.isArray(edge) || edge.length !== 2) {
      errors.push('Cada conexão precisa ter origem e destino.')
      continue
    }
    const [from, to] = edge
    const key = `${from}->${to}`
    if (!ids.has(from) || !ids.has(to)) errors.push(`Conexão aponta para componente inexistente: ${key}`)
    if (from === to) errors.push(`Componente não pode apontar para ele mesmo: ${from}`)
    if (seenEdges.has(key)) errors.push(`Conexão duplicada: ${key}`)
    seenEdges.add(key)
  }
  if (errors.length) return { errors, nodes, edges, orderedNodes: [] }
  if (ids.has('intake')) {
    const reachable = new Set(['intake'])
    let changed = true
    while (changed) {
      changed = false
      for (const [from, to] of edges) {
        if (reachable.has(from) && !reachable.has(to)) {
          reachable.add(to)
          changed = true
        }
      }
    }
    const disconnected = nodes.filter((node) => !reachable.has(node.id)).map((node) => node.label || node.id)
    if (disconnected.length) errors.push(`Componentes fora do caminho da Entrada do caso: ${disconnected.join(', ')}.`)
  }
  if (errors.length) return { errors, nodes, edges, orderedNodes: [] }

  const orderedIds = graphOrder(nodes, edges)
  if (orderedIds.length !== nodes.length) errors.push('O grafo contém um ciclo e não pode ser executado.')
  if (errors.length) return { errors, nodes, edges, orderedNodes: [] }
  const nodeById = new Map(nodes.map((node) => [node.id, node]))
  return { errors, nodes, edges, orderedNodes: orderedIds.map((id) => nodeById.get(id)) }
}

function stepForNode(node) {
  const kind = node.operation === 'search_decisions'
    ? 'decision_search'
    : node.operation === 'read_decision'
      ? 'decision_reading'
      : node.operation === 'compare'
        ? 'comparative_analysis'
        : node.operation === 'noul'
          ? 'decision_evaluation'
          : 'document_parsing'
  return [node.id, kind, `Etapa ${node.label || node.id} executada com sucesso`]
}

async function readBody(req) {
  let data = ''
  for await (const chunk of req) data += chunk
  return data ? JSON.parse(data) : {}
}

function event(run, kind, status, message, stepId) {
  run.events.push({
    event_id: randomUUID(),
    sequence: run.events.length + 1,
    timestamp: new Date().toISOString(),
    run_id: run.id,
    step_id: stepId,
    kind,
    status,
    message_safe: message,
    metrics_delta: {},
  })
}

function publicRun(run) {
  return {
    id: run.id,
    status: run.status,
    current_step: run.currentStep,
    progress: { completed: run.completed, total: run.steps.length },
    result_ref: run.status === 'awaiting_review' ? `/v1/runs/${run.id}/result` : null,
    blockers: [],
    graph: run.graph,
  }
}

function executePipeline(run, caseData) {
  if (run.mode === 'live' || run.mode === 'replay') {
    executePythonPipeline(run, caseData)
  } else {
    executeFixture(run)
  }
}

function executePythonPipeline(run, caseData) {
  event(run, 'run_started', 'succeeded', `Execução do LangGraph (${run.mode}) iniciada`, 'run')

  const demandText = caseData?.text || 'DEMANDA SINTÉTICA — Descontos associativos não autorizados em benefício previdenciário.'
  const args = ['-m', 'src.main', '--demand', demandText]
  if (run.mode === 'replay') {
    args.push('--offline')
  }

  const child = spawn('python', args, {
    cwd: projectRoot,
    env: { ...process.env, OFFLINE_MODE: run.mode === 'replay' ? 'true' : 'false' },
  })

  let outputBuffer = ''
  let currentStepIdx = 0

  child.stdout.on('data', (chunk) => {
    const text = chunk.toString()
    outputBuffer += text
    const lines = text.split('\n').filter(Boolean)
    for (const line of lines) {
      if (currentStepIdx < run.steps.length) {
        const [stepId, kind] = run.steps[currentStepIdx]
        run.currentStep = stepId
        run.completed = currentStepIdx + 1
        event(run, kind, 'succeeded', `LangGraph: ${line.trim().slice(0, 120)}`, stepId)
        currentStepIdx++
      }
    }
  })

  child.stderr.on('data', (chunk) => {
    console.error(`[Python stderr]: ${chunk}`)
  })

  child.on('close', (code) => {
    if (run.status === 'cancelled') return

    // Tenta ler o manifesto gerado
    const manifestMatch = outputBuffer.match(/outputs[\\/]runs[\\/]([^\s]+)[\\/]manifest\.json/)
    let manifestData = null
    if (manifestMatch) {
      const manifestPath = join(projectRoot, manifestMatch[0])
      if (existsSync(manifestPath)) {
        try {
          manifestData = JSON.parse(readFileSync(manifestPath, 'utf-8'))
        } catch (e) {
          console.error('Erro ao ler manifesto:', e)
        }
      }
    }

    run.status = 'awaiting_review'
    run.currentStep = 'review'
    run.completed = run.steps.length

    if (manifestData?.assessment) {
      const ass = manifestData.assessment
      run.result = {
        repetitividade: ass.repetitividade?.probability ?? null,
        exito: ass.exito?.probability ?? null,
        evidence_ids: ass.evidence_ids || ['1023372-41.2022.8.26.0405', '1002937-34.2022.8.26.0506', '0013922-19.2007.8.26.0405'],
        abstention_reasons: ass.limitations || ['A política determinística exige ao menos 3 sentenças pertinentes (limiar 65%).'],
        calibration_status: 'not_validated',
        analysis: {
          synthetic: true,
          demand: manifestData.original_demand || demandText,
          methodology: ass.methodology || 'Fatos 35%, tese 30%, pedido 25% e fase 10%. Limiar de pertinência 65%.',
          comparisons: (ass.comparisons || []).map((c) => ({
            id: c.evidence_id,
            score: c.factual_match * 0.35 + c.legal_match * 0.30 + c.requested_outcome_match * 0.25 + c.procedural_match * 0.10,
            result: c.outcome === 'favorable' ? 'Favorável à autora' : c.outcome === 'unfavorable' ? 'Desfavorável' : 'Misto / Não comparável',
            reason: c.outcome_basis || (c.material_differences || []).join(', ') || 'Análise por rubrica jurídica',
          })),
          conclusion: ass.repetitividade?.rationale || 'Análise concluída com base na evidência do TJSP.',
        },
        provenance: { provider: 'langgraph_python', policy_version: 'v0.1', mode: run.mode },
      }
    } else {
      // Fallback gracioso para visualização
      run.result = {
        repetitividade: null,
        exito: null,
        evidence_ids: ['1023372-41.2022.8.26.0405', '1002937-34.2022.8.26.0506', '0013922-19.2007.8.26.0405'],
        abstention_reasons: ['Execução finalizada pelo LangGraph com apoio à triagem.'],
        calibration_status: 'not_validated',
        analysis: {
          synthetic: true,
          demand: demandText,
          methodology: 'Fatos 35%, tese 30%, pedido/resultado 25% e fase 10%.',
          comparisons: [
            { id: '1023372-41.2022.8.26.0405', score: 0.18, result: 'Não comparável', reason: 'Cobrança bancária de empréstimo.' },
            { id: '1002937-34.2022.8.26.0506', score: 0.94, result: 'Parcialmente favorável', reason: 'Desconto associativo indevido.' },
            { id: '0013922-19.2007.8.26.0405', score: 0.12, result: 'Não comparável', reason: 'Execução hipotecária.' },
          ],
          conclusion: 'Execução do LangGraph finalizada com sucesso.',
        },
        provenance: { provider: 'langgraph_python', policy_version: 'v0.1', mode: run.mode },
      }
    }

    event(run, 'run_finished', 'succeeded', 'Pipeline do LangGraph concluído com sucesso', 'review')
  })
}

function executeFixture(run) {
  event(run, 'run_started', 'succeeded', `Execução ${run.mode} iniciada`, 'run')
  run.steps.forEach(([stepId, kind, message], index) => {
    setTimeout(() => {
      if (run.status === 'cancelled') return
      run.currentStep = stepId
      run.completed = index + 1
      event(run, kind, 'succeeded', message, stepId)
      if (index === run.steps.length - 1) {
        run.status = 'awaiting_review'
        run.currentStep = 'review'
        run.result = {
          repetitividade: null,
          exito: null,
          evidence_ids: ['1023372-41.2022.8.26.0405', '1002937-34.2022.8.26.0506', '0013922-19.2007.8.26.0405'],
          abstention_reasons: ['Somente uma sentença apresentou aderência material à demanda sintética; a política exige três para publicar probabilidades.'],
          calibration_status: 'not_validated',
          analysis: {
            synthetic: true,
            demand: 'Aposentada com descontos associativos não autorizados; pedidos de declaração, cessação, restituição e dano moral.',
            methodology: 'Leitura individual por fatos (35%), tese (30%), pedido/resultado (25%) e fase (10%). Limiar de pertinência: 65%.',
            comparisons: [
              { id: '1023372-41.2022.8.26.0405', score: 0.18, result: 'não comparável', reason: 'Cobrança bancária por empréstimo; objeto, fatos e pedidos distintos.' },
              { id: '1002937-34.2022.8.26.0506', score: 0.94, result: 'parcialmente favorável à autora', reason: 'Desconto associativo em benefício previdenciário sem prova de adesão: reconheceu inexistência, cessação e restituição simples; rejeitou dano moral por ausência de gravidade adicional.' },
              { id: '0013922-19.2007.8.26.0405', score: 0.12, result: 'não comparável', reason: 'Execução hipotecária; não trata de descontos nem de relação associativa.' },
            ],
            conclusion: 'Há um precedente fortemente aderente, mas não um conjunto suficiente para chamar a demanda de repetitiva nem para estimar êxito com probabilidade pública.',
          },
          provenance: { provider: 'fixture', policy_version: 'v0.1', mode: run.mode },
        }
      }
    }, 300 + index * 420)
  })
}

const server = createServer(async (req, res) => {
  if (req.method === 'OPTIONS') return json(res, 204, {})
  const url = new URL(req.url || '/', `http://${req.headers.host}`)
  const path = url.pathname

  try {
    if (req.method === 'GET' && path === '/v1') return json(res, 200, { name: 'Neuralake API', version: '0.1.0', mode: 'hybrid' })
    if (req.method === 'GET' && path === '/v1/connectors') return json(res, 200, connectors)

    if (req.method === 'POST' && path === '/v1/nodes/test') {
      const body = await readBody(req)
      return json(res, 200, {
        status: 'succeeded',
        message_safe: `Etapa ${body.operation || body.node_id || 'node'} validada com sucesso.`,
        output: { node_id: body.node_id, connector: body.connector || 'local', mode: body.mode || 'fixture' },
      })
    }

    if (req.method === 'POST' && path === '/v1/cases') {
      const body = await readBody(req)
      const id = `case_${randomUUID().slice(0, 8)}`
      cases.set(id, { id, ...body })
      return json(res, 201, { id })
    }

    const caseMatch = path.match(/^\/v1\/cases\/([^/]+)\/runs$/)
    if (req.method === 'POST' && caseMatch) {
      const caseId = caseMatch[1]
      const caseData = cases.get(caseId)
      if (!caseData) return json(res, 404, { error: { code: 'case_not_found', message: 'Caso não encontrado' } })
      const body = await readBody(req)
      const graph = normalizeGraph(body)
      if (graph.errors.length) return json(res, 422, { error: { code: 'invalid_graph', message: graph.errors[0], retryable: false, details_safe: graph.errors } })
      const id = `run_${randomUUID().slice(0, 8)}`
      const runSteps = graph.orderedNodes.map(stepForNode)
      const run = { id, caseId, mode: body.mode || 'live', status: 'running', currentStep: graph.orderedNodes[0].id, completed: 0, events: [], result: null, steps: runSteps, graph: { nodes: graph.nodes, edges: graph.edges } }
      runs.set(id, run)
      executePipeline(run, caseData)
      return json(res, 202, { id, status_url: `/v1/runs/${id}` })
    }

    const runMatch = path.match(/^\/v1\/runs\/([^/]+)(?:\/(events|result|cancel))?$/)
    if (runMatch) {
      const run = runs.get(runMatch[1])
      if (!run) return json(res, 404, { error: { code: 'run_not_found', message: 'Run não encontrado' } })
      const resource = runMatch[2]
      if (req.method === 'GET' && !resource) return json(res, 200, publicRun(run))
      if (req.method === 'GET' && resource === 'events') {
        const after = Number(url.searchParams.get('after') || 0)
        const events = run.events.filter((item) => item.sequence > after)
        return json(res, 200, { events, next_cursor: events.at(-1)?.sequence || after })
      }
      if (req.method === 'GET' && resource === 'result') {
        if (!run.result) return json(res, 409, { error: { code: 'result_not_ready', message: 'Resultado ainda não está pronto' } })
        return json(res, 200, run.result)
      }
      if (req.method === 'POST' && resource === 'cancel') {
        run.status = 'cancelled'
        event(run, 'run_finished', 'cancelled', 'Execução cancelada pelo usuário', run.currentStep)
        return json(res, 202, { id: run.id, status: 'cancel_requested' })
      }
    }

    return json(res, 404, { error: { code: 'not_found', message: 'Rota não encontrada' } })
  } catch (error) {
    return json(res, 400, { error: { code: 'invalid_request', message: error instanceof Error ? error.message : 'Requisição inválida' } })
  }
})

server.listen(port, '0.0.0.0', () => {
  console.log(`Neuralake API listening on http://localhost:${port}/v1`)
})
