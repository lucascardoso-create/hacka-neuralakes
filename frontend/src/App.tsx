import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  Activity,
  AlertCircle,
  ArrowDownToLine,
  ArrowRight,
  Check,
  ChevronDown,
  CircleHelp,
  Clock3,
  Cloud,
  Code2,
  Database,
  FileText,
  Gauge,
  GitBranch,
  LayoutGrid,
  LoaderCircle,
  LockKeyhole,
  Menu,
  MoreHorizontal,
  Network,
  Play,
  Plus,
  RotateCcw,
  Search,
  Send,
  Settings2,
  ShieldCheck,
  Sparkles,
  Square,
  Trash2,
  Upload,
  X,
  Zap,
} from 'lucide-react'
import { api, type AnalysisResult, type Connector, type Event, type Run, type RunMode } from './lib/api'

type NodeId = string
type NodeState = 'idle' | 'running' | 'done' | 'blocked'

type FlowNode = {
  id: NodeId
  label: string
  sublabel: string
  icon: typeof FileText
  x: number
  y: number
  color: string
  detail: string
  connector?: string
  operation?: string
}

type NodeDrag = {
  id: NodeId
  pointerId: number
  startX: number
  startY: number
  originX: number
  originY: number
  moved: boolean
}

type NodeTemplate = Omit<FlowNode, 'id' | 'x' | 'y'> & { category: string }

const flowNodes: FlowNode[] = [
  { id: 'intake', label: 'Entrada do caso', sublabel: 'case input', icon: FileText, x: 54, y: 204, color: '#c8a4ff', detail: 'Documentos, perspectiva e definição de êxito', connector: 'legal_intake', operation: 'create_case' },
  { id: 'extract', label: 'Extrair fatos', sublabel: 'intake agent', icon: Sparkles, x: 252, y: 204, color: '#56d6bd', detail: 'Perfil estruturado com referências por página', connector: 'neuralake', operation: 'extract_case_profile' },
  { id: 'plan', label: 'Plano de pesquisa', sublabel: 'research agent', icon: Search, x: 450, y: 204, color: '#82a8ff', detail: 'Filtros, destino autorizado e data de corte', connector: 'neuralake', operation: 'create_research_plan' },
  { id: 'research', label: 'Pesquisar julgados', sublabel: 'saj_claw', icon: Network, x: 648, y: 204, color: '#f2b36f', detail: 'Consulta verificável no e-SAJ TJSP', connector: 'browser-use', operation: 'search_decisions' },
  { id: 'compare', label: 'Comparar evidências', sublabel: 'evidence agent', icon: GitBranch, x: 846, y: 204, color: '#c8a4ff', detail: 'Semelhanças, distinções e evidências contrárias', connector: 'neuralake', operation: 'compare_evidence' },
  { id: 'decision', label: 'Decisão probabilística', sublabel: 'jev · Noul', icon: Gauge, x: 1044, y: 204, color: '#f1c75b', detail: 'p_repetitividade e p_êxito com gates de política', connector: 'jev', operation: 'evaluate_noul' },
  { id: 'report', label: 'Relatório final', sublabel: 'report agent', icon: FileText, x: 1238, y: 204, color: '#56d6bd', detail: 'Markdown/JSON com citações e revisão humana', connector: 'docs_claw', operation: 'render_report' },
]

const nodeCatalog: NodeTemplate[] = [
  { label: 'Entrada do caso', sublabel: 'case input', icon: FileText, color: '#c8a4ff', detail: 'Recebe documentos, perspectiva e definição de êxito', connector: 'legal_intake', operation: 'create_case', category: 'Entrada' },
  { label: 'Extrair fatos', sublabel: 'intake agent', icon: Sparkles, color: '#56d6bd', detail: 'Extrai fatos com referências por página', connector: 'neuralake', operation: 'extract_case_profile', category: 'Neuralake' },
  { label: 'Pesquisar julgados', sublabel: 'saj_claw', icon: Network, color: '#f2b36f', detail: 'Consulta decisões no destino autorizado', connector: 'browser-use', operation: 'search_decisions', category: 'Conectores' },
  { label: 'Comparar evidências', sublabel: 'evidence agent', icon: GitBranch, color: '#c8a4ff', detail: 'Compara fatos, pedido, tese e fase', connector: 'neuralake', operation: 'compare_evidence', category: 'Neuralake' },
  { label: 'Decisão probabilística', sublabel: 'jev · Noul', icon: Gauge, color: '#f1c75b', detail: 'Calcula probabilidades experimentais', connector: 'jev', operation: 'evaluate_noul', category: 'Decisão' },
  { label: 'Relatório final', sublabel: 'report agent', icon: FileText, color: '#56d6bd', detail: 'Gera Markdown/JSON auditável', connector: 'docs_claw', operation: 'render_report', category: 'Saída' },
  { label: 'Gate de política', sublabel: 'policy engine', icon: ShieldCheck, color: '#ff8c9a', detail: 'Avalia destino, orçamento e autonomia', connector: 'policy_engine', operation: 'evaluate_policy', category: 'Governança' },
]

const sampleEvents: Event[] = [
  { event_id: '1', sequence: 1, timestamp: '12:24:02', run_id: 'demo', kind: 'run_started', status: 'succeeded', message_safe: 'Execução fixture iniciada' },
  { event_id: '2', sequence: 2, timestamp: '12:24:03', run_id: 'demo', kind: 'step_started', status: 'succeeded', message_safe: 'Perfil do caso validado' },
  { event_id: '3', sequence: 3, timestamp: '12:24:04', run_id: 'demo', kind: 'evidence_collected', status: 'succeeded', message_safe: '8 evidências verificadas encontradas' },
  { event_id: '4', sequence: 4, timestamp: '12:24:05', run_id: 'demo', kind: 'decision_ready', status: 'succeeded', message_safe: 'Jev retornou as probabilidades' },
  { event_id: '5', sequence: 5, timestamp: '12:24:06', run_id: 'demo', kind: 'report_ready', status: 'succeeded', message_safe: 'Relatório aguardando revisão' },
]

const demoResult: AnalysisResult = {
  repetitividade: 0.78,
  exito: 0.64,
  calibration_status: 'not_validated',
  evidence_ids: ['ev-01', 'ev-02', 'ev-03'],
}

const initialEdges: Array<[NodeId, NodeId]> = [
  ['intake', 'extract'], ['extract', 'plan'], ['plan', 'research'], ['research', 'compare'], ['compare', 'decision'], ['decision', 'report'],
]

function formatProbability(value: number | null | undefined) {
  return value == null ? '—' : `${Math.round(value * 100)}%`
}

function statusForNode(id: NodeId, active: NodeId | null, completed: Set<NodeId>, blocked: boolean): NodeState {
  if (blocked && id === active) return 'blocked'
  if (id === active) return 'running'
  if (completed.has(id)) return 'done'
  return 'idle'
}

function hasPath(edges: Array<[NodeId, NodeId]>, from: NodeId, target: NodeId) {
  const visited = new Set<NodeId>()
  const pending = [from]
  while (pending.length) {
    const current = pending.pop()
    if (!current || visited.has(current)) continue
    if (current === target) return true
    visited.add(current)
    for (const [source, destination] of edges) {
      if (source === current && !visited.has(destination)) pending.push(destination)
    }
  }
  return false
}

function executionOrder(nodes: FlowNode[], edges: Array<[NodeId, NodeId]>) {
  const indegree = new Map(nodes.map((node) => [node.id, 0]))
  const outgoing = new Map<NodeId, NodeId[]>()
  for (const [from, to] of edges) {
    indegree.set(to, (indegree.get(to) || 0) + 1)
    outgoing.set(from, [...(outgoing.get(from) || []), to])
  }
  const queue = nodes.filter((node) => indegree.get(node.id) === 0).map((node) => node.id)
  const ordered: NodeId[] = []
  while (queue.length) {
    const current = queue.shift()
    if (!current) continue
    ordered.push(current)
    for (const next of outgoing.get(current) || []) {
      const nextDegree = (indegree.get(next) || 0) - 1
      indegree.set(next, nextDegree)
      if (nextDegree === 0) queue.push(next)
    }
  }
  return ordered
}

function reachableFrom(edges: Array<[NodeId, NodeId]>, source: NodeId) {
  const reachable = new Set<NodeId>([source])
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
  return reachable
}

function validateGraph(nodes: FlowNode[], edges: Array<[NodeId, NodeId]>) {
  const errors: string[] = []
  const warnings: string[] = []
  const ids = new Set<NodeId>()
  for (const node of nodes) {
    if (ids.has(node.id)) errors.push(`ID duplicado: ${node.id}`)
    ids.add(node.id)
  }
  if (!ids.has('intake')) errors.push('O fluxo precisa manter a Entrada do caso.')
  const seenEdges = new Set<string>()
  for (const [from, to] of edges) {
    const edgeKey = `${from}->${to}`
    if (!ids.has(from) || !ids.has(to)) errors.push(`Conexão aponta para componente inexistente: ${edgeKey}`)
    if (from === to) errors.push('Um componente não pode se conectar a ele mesmo.')
    if (seenEdges.has(edgeKey)) errors.push(`Conexão duplicada: ${edgeKey}`)
    seenEdges.add(edgeKey)
    if (from !== to && hasPath(edges, to, from)) errors.push(`A conexão ${edgeKey} cria um ciclo.`)
  }
  if (executionOrder(nodes, edges).length !== nodes.length) errors.push('O fluxo precisa ser acíclico para executar.')
  const reachable = ids.has('intake') ? reachableFrom(edges, 'intake') : new Set<NodeId>()
  const disconnected = nodes.filter((node) => !reachable.has(node.id)).map((node) => node.label)
  if (disconnected.length) warnings.push(`Componentes fora do caminho da Entrada do caso: ${disconnected.join(', ')}.`)
  return { errors, warnings }
}

function App() {
  const [nodes, setNodes] = useState<FlowNode[]>(flowNodes)
  const [edges, setEdges] = useState<Array<[NodeId, NodeId]>>(initialEdges)
  const [selectedNode, setSelectedNode] = useState<NodeId>('intake')
  const [selectedByUser, setSelectedByUser] = useState(false)
  const [mode, setMode] = useState<RunMode>('fixture')
  const [caseTitle, setCaseTitle] = useState('Ação revisional · contrato bancário')
  const [representedSide, setRepresentedSide] = useState('empresa ré')
  const [successDefinition, setSuccessDefinition] = useState('Rejeição integral do pedido de indenização em primeiro grau')
  const [targetStage, setTargetStage] = useState('primeiro grau')
  const [connected, setConnected] = useState<boolean | null>(null)
  const [connectors, setConnectors] = useState<Connector[]>([])
  const [run, setRun] = useState<Run | null>(null)
  const [events, setEvents] = useState<Event[]>(sampleEvents)
  const [result, setResult] = useState<AnalysisResult>(demoResult)
  const [activeNode, setActiveNode] = useState<NodeId | null>(null)
  const [completedNodes, setCompletedNodes] = useState<Set<NodeId>>(new Set())
  const [loading, setLoading] = useState(false)
  const [toast, setToast] = useState<string | null>(null)
  const [rightTab, setRightTab] = useState<'execution' | 'data' | 'logs'>('execution')
  const [showNodePicker, setShowNodePicker] = useState(false)
  const [testingNode, setTestingNode] = useState(false)
  const [connectionMode, setConnectionMode] = useState(false)
  const [connectionSource, setConnectionSource] = useState<NodeId | null>(null)
  const canvasNodesRef = useRef<HTMLDivElement>(null)
  const nodeDragRef = useRef<NodeDrag | null>(null)
  const suppressNodeClickRef = useRef(false)

  const probeBackend = useCallback(async () => {
    try {
      const response = await api.listConnectors()
      setConnectors(response)
      setConnected(true)
    } catch {
      setConnected(false)
    }
  }, [])

  useEffect(() => { void probeBackend() }, [probeBackend])

  useEffect(() => {
    if (!toast) return
    const timeout = window.setTimeout(() => setToast(null), 4200)
    return () => window.clearTimeout(timeout)
  }, [toast])

  const nodeById = useMemo(() => Object.fromEntries(nodes.map((node) => [node.id, node])) as Record<NodeId, FlowNode>, [nodes])
  const graphOrder = useMemo(() => executionOrder(nodes, edges), [nodes, edges])
  const graphValidation = useMemo(() => validateGraph(nodes, edges), [nodes, edges])

  const selectNode = (nodeId: NodeId) => {
    setSelectedNode(nodeId)
    setSelectedByUser(true)
  }

  const addNode = (template: NodeTemplate) => {
    const id = `${template.operation || 'node'}_${crypto.randomUUID().slice(0, 6)}`
    const column = nodes.length % 6
    const row = Math.floor(nodes.length / 6)
    const newNode: FlowNode = { ...template, id, x: 54 + column * 198, y: 204 + row * 142 }
    const previous = selectedByUser ? nodeById[selectedNode] : undefined
    setNodes((current) => [...current, newNode])
    if (previous) setEdges((current) => [...current, [previous.id, id]])
    setSelectedNode(id)
    setSelectedByUser(false)
    setConnectionMode(false)
    setConnectionSource(null)
    setShowNodePicker(false)
    setCompletedNodes((current) => {
      const next = new Set(current)
      next.delete(id)
      return next
    })
    setToast(previous ? `${template.label} adicionado e conectado após ${previous.label}.` : `${template.label} adicionado solto. Selecione uma origem para conectá-lo.`)
  }

  const startConnectionFrom = (nodeId: NodeId) => {
    selectNode(nodeId)
    setConnectionMode(true)
    setConnectionSource(nodeId)
    setToast('Origem selecionada. Clique no destino no canvas ou na lista de componentes.')
  }

  const handleNodeClick = (nodeId: NodeId) => {
    if (suppressNodeClickRef.current) return
    selectNode(nodeId)
    if (!connectionMode) return
    if (!connectionSource) {
      setConnectionSource(nodeId)
      setToast('Origem selecionada. Agora clique no componente destino.')
      return
    }
    if (connectionSource === nodeId) {
      setConnectionSource(null)
      setToast('Conexão cancelada.')
      return
    }
    if (hasPath(edges, nodeId, connectionSource)) {
      setConnectionSource(null)
      setToast('Essa conexão criaria um ciclo. Escolha outro destino.')
      return
    }
    const alreadyConnected = edges.some(([from, to]) => from === connectionSource && to === nodeId)
    if (alreadyConnected) {
      setConnectionSource(null)
      setToast('Esses componentes já estão conectados.')
      return
    }
    setEdges((current) => [...current, [connectionSource, nodeId]])
    setConnectionSource(null)
    setConnectionMode(false)
    setToast('Conexão adicionada e pronta para o próximo run.')
  }

  const handlePortClick = (event: React.MouseEvent, nodeId: NodeId, port: 'input' | 'output') => {
    event.stopPropagation()
    selectNode(nodeId)
    if (port === 'output') {
      startConnectionFrom(nodeId)
      return
    }
    if (connectionSource && connectionSource !== nodeId) {
      handleNodeClick(nodeId)
    } else if (!connectionSource) {
      setToast('Selecione a porta de saída do componente primeiro.')
    }
  }

  const removeEdge = (from: NodeId, to: NodeId) => {
    setEdges((current) => current.filter(([source, destination]) => source !== from || destination !== to))
    setToast('Conexão removida do fluxo.')
  }

  const repairGraph = () => {
    if (loading) {
      setToast('Pare a execução antes de reparar o fluxo.')
      return
    }
    const nodeIds = new Set(nodes.map((node) => node.id))
    const cleanEdges = edges.filter(([from, to], index, current) => from !== to && nodeIds.has(from) && nodeIds.has(to) && current.findIndex(([source, destination]) => source === from && destination === to) === index)
    let repaired = cleanEdges
    if (executionOrder(nodes, repaired).length !== nodes.length) {
      repaired = nodes.slice(0, -1).map((node, index) => [node.id, nodes[index + 1].id] as [NodeId, NodeId])
    }
    let reachable = reachableFrom(repaired, 'intake')
    for (const node of nodes) {
      if (node.id === 'intake' || reachable.has(node.id)) continue
      const anchor = [...nodes].reverse().find((candidate) => reachable.has(candidate.id) && !repaired.some(([from]) => from === candidate.id))?.id || 'intake'
      if (anchor !== node.id && !hasPath(repaired, node.id, anchor)) {
        repaired = [...repaired, [anchor, node.id]]
        reachable = reachableFrom(repaired, 'intake')
      }
    }
    setEdges(repaired)
    const added = repaired.length - edges.length
    setToast(added > 0 ? `${added} conexão(ões) restaurada(s) no fluxo.` : 'O fluxo já estava conectado.')
  }

  const removeNode = (nodeId: NodeId) => {
    if (loading) {
      setToast('Pare a execução antes de remover um componente.')
      return
    }
    if (nodeId === 'intake') {
      setToast('A Entrada do caso é obrigatória pela spec e não pode ser removida.')
      return
    }
    const nextNode = nodes.find((node) => node.id !== nodeId)
    const incoming = edges.filter(([, to]) => to === nodeId).map(([from]) => from)
    const outgoing = edges.filter(([from]) => from === nodeId).map(([, to]) => to)
    const bridges: Array<[NodeId, NodeId]> = incoming.flatMap((from) => outgoing.map((to) => [from, to] as [NodeId, NodeId]))
    setNodes((current) => current.filter((node) => node.id !== nodeId))
    setEdges((current) => {
      const retained = current.filter(([from, to]) => from !== nodeId && to !== nodeId)
      const additions = bridges.filter(([from, to]) => !retained.some(([source, destination]) => source === from && destination === to))
      return [...retained, ...additions]
    })
    setCompletedNodes((current) => {
      const next = new Set(current)
      next.delete(nodeId)
      return next
    })
    if (connectionSource === nodeId) {
      setConnectionSource(null)
      setConnectionMode(false)
    }
    setSelectedNode(nextNode?.id || 'intake')
    setSelectedByUser(false)
    setToast(bridges.length ? 'Componente removido e o fluxo foi religado.' : 'Componente removido e conexões associadas apagadas.')
  }

  const handleNodePointerDown = (event: React.PointerEvent<HTMLButtonElement>, node: FlowNode) => {
    if (connectionMode || event.button !== 0 || (event.target as HTMLElement).closest('.node-port, .node-delete-control')) return
    event.currentTarget.setPointerCapture(event.pointerId)
    nodeDragRef.current = { id: node.id, pointerId: event.pointerId, startX: event.clientX, startY: event.clientY, originX: node.x, originY: node.y, moved: false }
  }

  const handleNodePointerMove = (event: React.PointerEvent<HTMLButtonElement>) => {
    const drag = nodeDragRef.current
    if (!drag || drag.pointerId !== event.pointerId) return
    const deltaX = event.clientX - drag.startX
    const deltaY = event.clientY - drag.startY
    if (!drag.moved && Math.hypot(deltaX, deltaY) < 4) return
    drag.moved = true
    const canvasRect = canvasNodesRef.current?.getBoundingClientRect()
    const scale = canvasRect && canvasRect.width ? canvasRect.width / 1450 : 1
    const nextX = Math.max(12, Math.min(1450 - 158 - 12, drag.originX + deltaX / scale))
    const nextY = Math.max(12, Math.min(590 - 84 - 12, drag.originY + deltaY / scale))
    setNodes((current) => current.map((node) => node.id === drag.id ? { ...node, x: nextX, y: nextY } : node))
  }

  const handleNodePointerUp = (event: React.PointerEvent<HTMLButtonElement>) => {
    const drag = nodeDragRef.current
    if (!drag || drag.pointerId !== event.pointerId) return
    if (drag.moved) {
      suppressNodeClickRef.current = true
      window.setTimeout(() => { suppressNodeClickRef.current = false }, 0)
      setToast('Componente reposicionado no plano.')
    }
    nodeDragRef.current = null
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId)
  }

  const handleCanvasClick = (event: React.MouseEvent<HTMLDivElement>) => {
    const target = event.target as HTMLElement
    if (target.closest('.flow-node, .canvas-selection-panel, .canvas-badge, .canvas-flow-status')) return
    setSelectedByUser(false)
    if (connectionMode) {
      setConnectionMode(false)
      setConnectionSource(null)
      setToast('Seleção de conexão cancelada.')
    }
  }

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null
      if (target && ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName)) return
      if (event.key === 'Delete' || event.key === 'Backspace') {
        event.preventDefault()
        removeNode(selectedNode)
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [selectedNode, loading, nodes])

  const testSelectedNode = async () => {
    if (!selected || testingNode) return
    setTestingNode(true)
    try {
      const response = await api.testNode({ node_id: selected.id, connector: selected.connector, operation: selected.operation, mode })
      setToast(response.message_safe)
      setRightTab('logs')
    } catch (error) {
      setToast(error instanceof Error ? error.message : 'Não foi possível testar a etapa')
    } finally {
      setTestingNode(false)
    }
  }

  const syncRunProgress = useCallback((current: Run) => {
    const terminal = ['completed', 'awaiting_review', 'failed', 'blocked', 'partial', 'cancelled'].includes(current.status)
    const completedCount = Math.min(current.progress?.completed || 0, graphOrder.length)
    let completed = graphOrder.slice(0, completedCount)
    if (!terminal && current.current_step) completed = completed.filter((nodeId) => nodeId !== current.current_step)
    setCompletedNodes(new Set(completed))
    setActiveNode(!terminal && current.current_step && nodeById[current.current_step] ? current.current_step : null)
  }, [graphOrder, nodeById])

  const runLive = useCallback(async (runId: string) => {
    let cursor = 0
    let current: Run = { id: runId, status: 'running' }
    while (!['completed', 'awaiting_review', 'failed', 'blocked', 'partial', 'cancelled'].includes(current.status)) {
      current = await api.getRun(runId)
      setRun(current)
      syncRunProgress(current)
      const eventResponse = await api.getEvents(runId, cursor)
      if (eventResponse.events.length) {
        cursor = eventResponse.next_cursor || eventResponse.events.at(-1)?.sequence || cursor
        setEvents((previous) => [...previous, ...eventResponse.events])
      }
      await new Promise((resolve) => window.setTimeout(resolve, 2200))
    }
    if (current.status === 'completed' || current.status === 'awaiting_review') {
      const finalResult = await api.getResult(runId)
      setResult(finalResult)
      setToast('Execução concluída. Resultado pronto para revisão.')
    } else {
      setToast(`Execução terminou como ${current.status}. Verifique os bloqueios.`)
    }
    syncRunProgress(current)
    setActiveNode(null)
  }, [syncRunProgress])

  const startRun = async () => {
    if (loading) return
    if (graphValidation.errors.length || graphValidation.warnings.length) {
      setToast(`Fluxo incompleto: ${graphValidation.errors[0] || graphValidation.warnings[0]}`)
      return
    }
    setLoading(true)
    setEvents([])
    setCompletedNodes(new Set())
    setActiveNode('intake')
    try {
      const createdCase = await api.createCase({
        title: caseTitle,
        represented_side: representedSide,
        success_definition: successDefinition,
        target_stage: targetStage,
        target_claim_id: null,
        as_of_date: new Date().toISOString().slice(0, 10),
      })
      const started = await api.startRun(createdCase.id, mode, nodes.map(({ id, label, connector, operation, x, y }) => ({ id, label, connector, operation, position: { x, y } })), edges)
      setRun({ id: started.id, status: 'running' })
      setToast(`Run ${mode} iniciado no backend.`)
      await runLive(started.id)
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Falha ao iniciar execução'
      setConnected(false)
      setToast(`Backend indisponível: ${message}`)
      setActiveNode(null)
    } finally {
      setLoading(false)
    }
  }

  const cancelRun = async () => {
    if (!run?.id || loading === false) return
    try {
      await api.cancelRun(run.id)
      setRun((current) => current ? { ...current, status: 'cancel_requested' } : current)
      setToast('Cancelamento solicitado ao backend.')
    } catch (error) {
      setToast(error instanceof Error ? error.message : 'Não foi possível cancelar')
    }
  }

  const selected = nodeById[selectedNode]
  const incomingEdges = edges.filter(([, to]) => to === selectedNode)
  const outgoingEdges = edges.filter(([from]) => from === selectedNode)
  const statusLabel = run?.status || 'awaiting_review'
  const runIsActive = loading || ['running', 'queued', 'cancel_requested'].includes(run?.status || '')
  const currentConnectorIds = useMemo(() => new Set(connectors.map((connector) => connector.id)), [connectors])

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand-lockup">
          <div className="brand-mark"><span>n</span></div>
          <span className="brand-name">neuralake</span>
          <span className="brand-divider" />
          <button className="workspace-switcher">Legal Intelligence <ChevronDown size={13} /></button>
        </div>
        <div className="topbar-center">
          <span className="breadcrumb-muted">Workflows</span><ArrowRight size={12} /><span>Case Intelligence</span>
          <span className="saved-pill"><Check size={12} /> Saved</span>
        </div>
        <div className="topbar-actions">
          <div className={`connection-status ${connected === true ? 'online' : connected === false ? 'offline' : ''}`}>
            <span className="connection-dot" />
            {connected === true ? 'Backend conectado' : connected === false ? 'Backend offline' : 'Verificando backend'}
          </div>
          <button className="icon-button" title="Ajuda"><CircleHelp size={17} /></button>
          <button className="icon-button" title="Configurações"><Settings2 size={17} /></button>
          <div className="avatar">LM</div>
        </div>
      </header>

      <div className="main-layout">
        <aside className="left-rail">
          <button className="rail-button active" title="Workflow"><Network size={18} /></button>
          <button className="rail-button" title="Casos"><LayoutGrid size={18} /></button>
          <button className="rail-button" title="Dados"><Database size={18} /></button>
          <button className="rail-button" title="Governança"><ShieldCheck size={18} /></button>
          <div className="rail-spacer" />
          <button className="rail-button" title="Código"><Code2 size={18} /></button>
          <button className="rail-button" title="Menu"><Menu size={18} /></button>
        </aside>

        <aside className="workflow-sidebar">
          <div className="sidebar-heading">
            <div><div className="eyebrow">Workflow</div><h1>Case Intelligence</h1></div>
            <button className="icon-button subtle"><MoreHorizontal size={18} /></button>
          </div>
          <div className="sidebar-search"><Search size={15} /><input placeholder="Buscar no fluxo" /></div>

          <div className="sidebar-section-label">TRIGGER</div>
          <div className="trigger-card">
            <div className="trigger-icon"><Zap size={16} /></div>
            <div><strong>On case submitted</strong><span>Entrada manual ou Drive</span></div>
            <span className="trigger-dot" />
          </div>

          <div className="sidebar-section-row"><span className="sidebar-section-label">NODES</span><button className="add-node" onClick={() => setShowNodePicker(true)} title="Adicionar componente"><Plus size={13} /></button></div>
          <div className="node-list">
            {nodes.map((node) => {
              const Icon = node.icon
              const state = statusForNode(node.id, activeNode, completedNodes, run?.status === 'blocked')
              return <button key={node.id} className={`node-list-item ${selectedByUser && selectedNode === node.id ? 'selected' : ''} ${connectionSource === node.id ? 'connection-source' : ''}`} onClick={() => handleNodeClick(node.id)}>
                <span className="node-list-icon" style={{ color: node.color, background: `${node.color}16` }}><Icon size={15} /></span>
                <span className="node-list-copy"><strong>{node.label}</strong><span>{node.sublabel}</span></span>
                <span className={`mini-status ${state}`} />
                <span className={`node-list-remove ${node.id === 'intake' ? 'disabled' : ''}`} role="button" tabIndex={0} aria-disabled={node.id === 'intake'} aria-label={node.id === 'intake' ? 'Entrada do caso não pode ser removida' : `Remover ${node.label} do painel`} title={node.id === 'intake' ? 'Trigger obrigatório da spec' : 'Remover do painel'} onClick={(event) => { event.stopPropagation(); removeNode(node.id) }} onKeyDown={(event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); event.stopPropagation(); removeNode(node.id) } }}><Trash2 size={12} /></span>
              </button>
            })}
          </div>

          <div className="sidebar-bottom-card">
            <div className="sidebar-section-label">RUN MODE</div>
            <div className="mode-select-wrap"><Cloud size={14} /><select value={mode} onChange={(event) => setMode(event.target.value as RunMode)}><option value="fixture">Fixture · seguro</option><option value="replay">Replay · sem custo live</option><option value="live">Live · fornecedores</option></select><ChevronDown size={13} /></div>
            <div className="mode-help">Modo explícito por execução, conforme a spec.</div>
          </div>
        </aside>

        <main className="workspace">
          <div className="workspace-toolbar">
            <div className="toolbar-left"><button className="toolbar-button" onClick={() => setShowNodePicker(true)}><Plus size={15} /> Add node</button><button className={`toolbar-button ${connectionMode ? 'active' : ''}`} onClick={() => { const next = !connectionMode; setConnectionMode(next); setConnectionSource(null); setToast(next ? 'Clique na origem e depois no destino, no canvas ou na lista.' : 'Modo de conexão encerrado.') }}><GitBranch size={15} /> {connectionMode ? 'Connecting…' : 'Connect'}</button><button className="toolbar-button repair-button" onClick={repairGraph} title="Reconectar componentes fora do caminho"><RotateCcw size={14} /> Repair flow</button><span className="toolbar-divider" /><button className="toolbar-icon"><ArrowDownToLine size={15} /></button></div>
            <div className="toolbar-right"><span className="zoom-label">100%</span><button className="toolbar-icon"><Search size={15} /></button><button className="toolbar-icon"><LockKeyhole size={15} /></button></div>
          </div>

          <div className="canvas-area" onClick={handleCanvasClick}>
            <div className="canvas-grid" />
            <div className="canvas-badge"><Activity size={13} /> {nodes.length} nodes <span /> <Network size={13} /> {edges.length} connections</div>
            <div className={`canvas-flow-status ${graphValidation.errors.length || graphValidation.warnings.length ? 'invalid' : runIsActive ? 'running' : ''}`}><span />{graphValidation.errors.length ? 'Fluxo inválido' : graphValidation.warnings.length ? 'Componentes desconectados' : activeNode ? `Executando: ${nodeById[activeNode]?.label || activeNode}` : run?.status || 'Fluxo pronto'}</div>
            {selectedByUser ? <div className="canvas-selection-panel">
              <div className="canvas-selection-copy"><span className="eyebrow">Componente selecionado</span><strong>{selected.label}</strong><span>{statusForNode(selectedNode, activeNode, completedNodes, run?.status === 'blocked')} · {selected.connector || 'local'}</span></div>
              <div className="canvas-selection-actions"><button className="selection-action" onClick={() => startConnectionFrom(selectedNode)}><GitBranch size={13} /> Conectar</button>{(graphValidation.errors.length || graphValidation.warnings.length) > 0 && <button className="selection-action" onClick={repairGraph}><RotateCcw size={13} /> Reparar</button>}<button className="selection-action danger" onClick={() => removeNode(selectedNode)} disabled={selectedNode === 'intake' || loading}><Trash2 size={13} /> Remover do fluxo</button></div>
            </div> : <div className="canvas-selection-empty">Clique em um componente para editar, conectar ou remover.</div>}
            <svg className="flow-lines" viewBox="0 0 1450 590" preserveAspectRatio="none" aria-hidden="true">
              <defs><linearGradient id="line-gradient" x1="0" x2="1"><stop offset="0%" stopColor="#6d7788" /><stop offset="100%" stopColor="#a28cff" /></linearGradient></defs>
              {edges.map(([from, to]) => {
                const source = nodeById[from]
                const target = nodeById[to]
                const sx = source.x + 158
                const sy = source.y + 42
                const tx = target.x
                const ty = target.y + 42
                return <path key={`${from}-${to}`} className="flow-edge" d={`M ${sx} ${sy} C ${sx + 45} ${sy}, ${tx - 45} ${ty}, ${tx} ${ty}`} />
              })}
            </svg>
            <div className="canvas-nodes" ref={canvasNodesRef}>
              {nodes.map((node) => {
                const Icon = node.icon
                const state = statusForNode(node.id, activeNode, completedNodes, run?.status === 'blocked')
                return <button key={node.id} aria-label={`${node.label}. ${state}`} className={`flow-node ${selectedByUser && selectedNode === node.id ? 'selected' : ''} ${connectionSource === node.id ? 'connecting-source' : ''} state-${state}`} style={{ left: node.x, top: node.y }} onPointerDown={(event) => handleNodePointerDown(event, node)} onPointerMove={handleNodePointerMove} onPointerUp={handleNodePointerUp} onClick={() => handleNodeClick(node.id)}>
                  <span className="node-port input" title="Conectar entrada" onClick={(event) => handlePortClick(event, node.id, 'input')} /><span className="node-port output" title="Conectar saída" onClick={(event) => handlePortClick(event, node.id, 'output')} />
                  <span className="flow-node-header"><span className="flow-node-icon" style={{ color: node.color, background: `${node.color}19` }}><Icon size={16} /></span><span className="node-header-actions"><span className="node-state-indicator">{state === 'done' ? <Check size={11} /> : state === 'running' ? <LoaderCircle size={12} className="spin" /> : state === 'blocked' ? <X size={11} /> : <span />}</span>{selectedByUser && selectedNode === node.id && <span className={`node-delete-control ${node.id === 'intake' ? 'disabled' : ''}`} role="button" tabIndex={0} aria-disabled={node.id === 'intake'} aria-label={node.id === 'intake' ? 'Entrada do caso não pode ser removida' : `Remover ${node.label} do fluxo`} title={node.id === 'intake' ? 'Trigger obrigatório da spec' : 'Remover do fluxo'} onClick={(event) => { event.stopPropagation(); removeNode(node.id) }} onKeyDown={(event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); event.stopPropagation(); removeNode(node.id) } }}><Trash2 size={11} /></span>}</span></span>
                  <span className="flow-node-title">{node.label}</span><span className="flow-node-subtitle">{node.sublabel}</span>
                  <span className="flow-node-footer"><span>{node.connector}</span><MoreHorizontal size={13} /></span>
                </button>
              })}
            </div>
            <div className="canvas-minimap"><div className="mini-line one" /><div className="mini-line two" /><div className="mini-line three" /><div className="mini-node" /><div className="mini-node second" /><div className="mini-node third" /></div>
            <div className="canvas-hint">{connectionMode ? <><span className="keyboard-key">1</span> origem <ArrowRight size={11} /><span className="keyboard-key">2</span> destino</> : <><span className="keyboard-key">⌘</span><span className="keyboard-key">K</span> command palette</>}</div>
          </div>

          <section className="run-console">
            <div className="run-console-header">
              <div className="run-title"><div className={`run-status-icon ${runIsActive ? 'active' : 'complete'}`}>{runIsActive ? <LoaderCircle size={15} className="spin" /> : <Check size={15} />}</div><div><strong>{runIsActive ? 'Running workflow' : 'Workflow ready'}</strong><span>{statusLabel} {run?.id ? `· ${run.id.slice(0, 14)}` : '· waiting for execution'}</span></div></div>
              <div className="run-actions"><span className="run-duration"><Clock3 size={13} /> {runIsActive ? 'processing…' : '06.4s last run'}</span><button className="secondary-button" onClick={() => void startRun()} disabled={loading}><Play size={13} /> Execute</button>{runIsActive && <button className="stop-button" onClick={() => void cancelRun()}><Square size={12} fill="currentColor" /> Stop</button>}</div>
            </div>
            <div className="run-metrics"><Metric label="p_repetitividade" value={formatProbability(result.repetitividade)} tone="purple" /><Metric label="p_êxito" value={formatProbability(result.exito)} tone="green" /><Metric label="evidências verificadas" value={`${result.evidence_ids?.length || 0}`} tone="blue" /><Metric label="calibration" value={result.calibration_status || 'not measured'} tone="yellow" /><div className="review-note"><ShieldCheck size={15} /><span>Revisão humana obrigatória</span></div></div>
          </section>
        </main>

        <aside className="inspector">
          <div className="inspector-tabs"><button className={rightTab === 'execution' ? 'active' : ''} onClick={() => setRightTab('execution')}>Execution</button><button className={rightTab === 'data' ? 'active' : ''} onClick={() => setRightTab('data')}>Data</button><button className={rightTab === 'logs' ? 'active' : ''} onClick={() => setRightTab('logs')}>Logs <span className="tab-count">{events.length}</span></button></div>
          {rightTab === 'execution' && <>
            <div className="inspector-node-title"><span className="selected-icon" style={{ color: selected.color, background: `${selected.color}18` }}><selected.icon size={18} /></span><div><div className="eyebrow">Selected node</div><h2>{selected.label}</h2><span>{selected.sublabel}</span></div><button className="icon-button subtle"><MoreHorizontal size={17} /></button></div>
            <div className="inspector-divider" />
            <InspectorField label="Purpose"><p>{selected.detail}</p></InspectorField>
            <InspectorField label="Connector"><div className="connector-value"><span className="connector-bullet" style={{ background: selected.color }} />{selected.connector}<span className="configured-badge">{selected.connector && currentConnectorIds.has(selected.connector) ? 'configured' : 'local'}</span></div></InspectorField>
            <InspectorField label="Status"><div className="inspector-status"><span className={`status-pip ${statusForNode(selectedNode, activeNode, completedNodes, run?.status === 'blocked')}`} />{statusForNode(selectedNode, activeNode, completedNodes, run?.status === 'blocked')}</div></InspectorField>
            <InspectorField label="Configuration"><div className="config-row"><span>Input schema</span><strong>validated</strong></div><div className="config-row"><span>Policy</span><strong>v0.1</strong></div><div className="config-row"><span>Deadline</span><strong>60s</strong></div></InspectorField>
            <InspectorField label={`Connections · ${incomingEdges.length + outgoingEdges.length}`}>
              <div className="connections-list">
                {incomingEdges.map(([from, to]) => <div className="connection-row" key={`${from}-${to}`}>
                  <span className="connection-direction input">in</span>
                  <span className="connection-label">{nodeById[from]?.label || from}</span>
                  <button className="connection-remove" title="Remover conexão" onClick={() => removeEdge(from, to)}><X size={12} /></button>
                </div>)}
                {outgoingEdges.map(([from, to]) => <div className="connection-row" key={`${from}-${to}`}>
                  <span className="connection-direction output">out</span>
                  <span className="connection-label">{nodeById[to]?.label || to}</span>
                  <button className="connection-remove" title="Remover conexão" onClick={() => removeEdge(from, to)}><X size={12} /></button>
                </div>)}
                {!incomingEdges.length && !outgoingEdges.length && <span className="no-connections">Nenhuma conexão neste componente.</span>}
              </div>
            </InspectorField>
            <div className="inspector-bottom"><button className="full-button" onClick={() => startConnectionFrom(selectedNode)}><GitBranch size={14} /> Conectar a partir daqui</button><button className="full-button ghost" onClick={() => void testSelectedNode()} disabled={testingNode}><Send size={14} /> {testingNode ? 'Testando…' : 'Testar etapa'}</button><button className="full-button danger" onClick={() => removeNode(selectedNode)} disabled={selectedNode === 'intake' || loading}><Trash2 size={14} /> Remover do fluxo</button></div>
          </>}
          {rightTab === 'data' && <DataPanel result={result} mode={mode} />}
          {rightTab === 'logs' && <LogsPanel events={events} />}
        </aside>
      </div>
      {showNodePicker && <div className="node-picker-backdrop" onClick={() => setShowNodePicker(false)}>
        <section className="node-picker" onClick={(event) => event.stopPropagation()}>
          <div className="node-picker-header"><div><div className="eyebrow">Component library</div><h2>Add a component</h2><p>Each component maps to an operation and connector in the backend.</p></div><button className="icon-button" onClick={() => setShowNodePicker(false)}><X size={17} /></button></div>
          <div className="node-picker-grid">
            {nodeCatalog.map((template) => {
              const Icon = template.icon
              const configured = template.connector ? currentConnectorIds.has(template.connector) : false
              return <button className="component-card" key={`${template.connector}-${template.operation}`} onClick={() => addNode(template)}>
                <span className="component-icon" style={{ color: template.color, background: `${template.color}18` }}><Icon size={18} /></span>
                <span className="component-copy"><strong>{template.label}</strong><span>{template.detail}</span><em><b style={{ background: template.color }} />{template.connector} · {configured ? 'configured' : 'fixture/local'}</em></span>
                <Plus size={15} className="component-plus" />
              </button>
            })}
          </div>
          <div className="node-picker-footer"><ShieldCheck size={14} /> The selected mode is sent with the workflow request. Live connectors require backend configuration.</div>
        </section>
      </div>}
      {toast && <div className="toast"><AlertCircle size={16} /><span>{toast}</span><button onClick={() => setToast(null)}><X size={14} /></button></div>}
    </div>
  )
}

function Metric({ label, value, tone }: { label: string; value: string; tone: string }) {
  return <div className="metric"><span className={`metric-dot ${tone}`} /><div><span>{label}</span><strong>{value}</strong></div></div>
}

function InspectorField({ label, children }: { label: string; children: React.ReactNode }) {
  return <div className="inspector-field"><div className="field-label">{label}</div>{children}</div>
}

function DataPanel({ result, mode }: { result: AnalysisResult; mode: RunMode }) {
  return <div className="panel-content"><div className="panel-heading"><div className="eyebrow">Validated output</div><h2>AnalysisResult</h2><span>schema v0.1 · {mode}</span></div><div className="json-card"><div><span>repetitividade</span><strong>{result.repetitividade ?? null}</strong></div><div><span>exito</span><strong>{result.exito ?? null}</strong></div><div><span>evidence_ids</span><strong>[{result.evidence_ids?.map((id) => `"${id}"`).join(', ') || ''}]</strong></div><div><span>calibration_status</span><strong>{result.calibration_status || null}</strong></div></div><div className="null-note"><AlertCircle size={14} /> null significa desconhecido ou não medido; zero é um valor observado.</div></div>
}

function LogsPanel({ events }: { events: Event[] }) {
  return <div className="panel-content"><div className="panel-heading"><div className="eyebrow">Event sink</div><h2>Run events</h2><span>sequence monotônica · {events.length} eventos</span></div><div className="event-list">{events.map((event) => <div className="event-row" key={`${event.event_id}-${event.sequence}`}><span className="event-sequence">{String(event.sequence).padStart(2, '0')}</span><span className="event-pip"><Check size={10} /></span><div><strong>{event.kind.replaceAll('_', ' ')}</strong><p>{event.message_safe}</p></div><time>{event.timestamp}</time></div>)}</div></div>
}

export default App
