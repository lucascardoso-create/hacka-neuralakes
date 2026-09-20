import { useCallback, useEffect, useMemo, useState } from 'react'
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
  if (completed.has(id)) return 'done'
  if (id === active) return 'running'
  return 'idle'
}

function App() {
  const [nodes, setNodes] = useState<FlowNode[]>(flowNodes)
  const [edges, setEdges] = useState<Array<[NodeId, NodeId]>>(initialEdges)
  const [selectedNode, setSelectedNode] = useState<NodeId>('intake')
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
  const [completedNodes, setCompletedNodes] = useState<Set<NodeId>>(new Set(nodes.map((node) => node.id)))
  const [loading, setLoading] = useState(false)
  const [toast, setToast] = useState<string | null>(null)
  const [rightTab, setRightTab] = useState<'execution' | 'data' | 'logs'>('execution')
  const [showNodePicker, setShowNodePicker] = useState(false)
  const [testingNode, setTestingNode] = useState(false)
  const [connectionMode, setConnectionMode] = useState(false)
  const [connectionSource, setConnectionSource] = useState<NodeId | null>(null)

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

  const addNode = (template: NodeTemplate) => {
    const id = `${template.operation || 'node'}_${crypto.randomUUID().slice(0, 6)}`
    const column = nodes.length % 6
    const row = Math.floor(nodes.length / 6)
    const newNode: FlowNode = { ...template, id, x: 54 + column * 198, y: 204 + row * 142 }
    const previous = nodes.at(-1)
    setNodes((current) => [...current, newNode])
    if (previous) setEdges((current) => [...current, [previous.id, id]])
    setSelectedNode(id)
    setShowNodePicker(false)
    setCompletedNodes((current) => {
      const next = new Set(current)
      next.delete(id)
      return next
    })
    setToast(`${template.label} adicionado ao fluxo.`)
  }

  const handleNodeClick = (nodeId: NodeId) => {
    setSelectedNode(nodeId)
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
    setSelectedNode(nodeId)
    if (port === 'output') {
      setConnectionMode(true)
      setConnectionSource(nodeId)
      setToast('Saída selecionada. Clique no nó que deve receber os dados.')
      return
    }
    if (connectionSource && connectionSource !== nodeId) handleNodeClick(nodeId)
  }

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

  const runLive = useCallback(async (runId: string) => {
    let cursor = 0
    let current: Run = { id: runId, status: 'running' }
    while (!['completed', 'awaiting_review', 'failed', 'blocked', 'partial', 'cancelled'].includes(current.status)) {
      current = await api.getRun(runId)
      setRun(current)
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
    setActiveNode(null)
  }, [])

  const startRun = async () => {
    if (loading) return
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
      const started = await api.startRun(createdCase.id, mode, nodes.map(({ id, label, connector, operation }) => ({ id, label, connector, operation })), edges)
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
              return <button key={node.id} className={`node-list-item ${selectedNode === node.id ? 'selected' : ''}`} onClick={() => setSelectedNode(node.id)}>
                <span className="node-list-icon" style={{ color: node.color, background: `${node.color}16` }}><Icon size={15} /></span>
                <span className="node-list-copy"><strong>{node.label}</strong><span>{node.sublabel}</span></span>
                <span className={`mini-status ${state}`} />
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
            <div className="toolbar-left"><button className="toolbar-button" onClick={() => setShowNodePicker(true)}><Plus size={15} /> Add node</button><button className={`toolbar-button ${connectionMode ? 'active' : ''}`} onClick={() => { setConnectionMode((current) => !current); setConnectionSource(null) }}><GitBranch size={15} /> {connectionMode ? 'Connecting…' : 'Connect'}</button><span className="toolbar-divider" /><button className="toolbar-icon"><RotateCcw size={15} /></button><button className="toolbar-icon"><ArrowDownToLine size={15} /></button></div>
            <div className="toolbar-right"><span className="zoom-label">100%</span><button className="toolbar-icon"><Search size={15} /></button><button className="toolbar-icon"><LockKeyhole size={15} /></button></div>
          </div>

          <div className="canvas-area">
            <div className="canvas-grid" />
            <div className="canvas-badge"><Activity size={13} /> {nodes.length} nodes <span /> <Network size={13} /> {edges.length} connections</div>
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
            <div className="canvas-nodes">
              {nodes.map((node) => {
                const Icon = node.icon
                const state = statusForNode(node.id, activeNode, completedNodes, run?.status === 'blocked')
                return <button key={node.id} className={`flow-node ${selectedNode === node.id ? 'selected' : ''} ${connectionSource === node.id ? 'connecting-source' : ''} state-${state}`} style={{ left: node.x, top: node.y }} onClick={() => handleNodeClick(node.id)}>
                  <span className="node-port input" title="Conectar entrada" onClick={(event) => handlePortClick(event, node.id, 'input')} /><span className="node-port output" title="Conectar saída" onClick={(event) => handlePortClick(event, node.id, 'output')} />
                  <span className="flow-node-header"><span className="flow-node-icon" style={{ color: node.color, background: `${node.color}19` }}><Icon size={16} /></span><span className="node-state-indicator">{state === 'done' ? <Check size={11} /> : state === 'running' ? <LoaderCircle size={12} className="spin" /> : state === 'blocked' ? <X size={11} /> : <span />}</span></span>
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
            <div className="inspector-bottom"><button className="full-button"><Settings2 size={14} /> Edit node</button><button className="full-button ghost" onClick={() => void testSelectedNode()} disabled={testingNode}><Send size={14} /> {testingNode ? 'Testing…' : 'Test step'}</button></div>
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
