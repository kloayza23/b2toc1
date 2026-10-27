import { useEffect, useState } from 'react'
import { ArrowRight, BarChart3, BookOpen, BrainCircuit, Check, ChevronRight, CircleUserRound, Headphones, LogOut, MessageCircle, PenLine, Play, RotateCcw, Sparkles, Target, Volume2, X } from 'lucide-react'
import { api, session } from './api'

const levels = ['A1', 'A2', 'B1', 'B2', 'C1']
const moduleMeta = {
  speech: { label: 'Speaking', Icon: MessageCircle, color: '#7c3aed' },
  writing: { label: 'Writing', Icon: PenLine, color: '#e14b72' },
  reading: { label: 'Reading', Icon: BookOpen, color: '#0284c7' },
  listening: { label: 'Listening', Icon: Headphones, color: '#ea580c' },
}

function Logo() {
  return <div className="logo"><span><BrainCircuit size={22} /></span><b>LevelUp</b><small>ENGLISH</small></div>
}

function Auth({ onAuth }) {
  const [register, setRegister] = useState(false)
  const [form, setForm] = useState({ username: '', name: '', email: '', user: '', password: '' })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  async function submit(e) {
    e.preventDefault(); setError(''); setLoading(true)
    try {
      const data = await api(`/auth/${register ? 'register' : 'login'}`, { method: 'POST', body: JSON.stringify(form) })
      session.token = data.access_token; onAuth(data.user)
    } catch (err) { setError(err.message) } finally { setLoading(false) }
  }
  return <main className="auth-page">
    <section className="auth-story">
      <Logo />
      <div className="story-content"><span className="eyebrow light">TU SIGUIENTE NIVEL EMPIEZA AQUÍ</span><h1>Inglés real.<br/><em>Progreso medible.</em></h1><p>Descubre con precisión dónde estás y recibe una ruta de práctica diseñada a partir de tus resultados.</p><div className="proof"><div className="avatars">JL</div><span><b>Evaluación integral</b><br/>4 habilidades · 100 preguntas</span></div></div>
    </section>
    <section className="auth-panel"><div className="auth-card"><div className="mobile-logo"><Logo /></div><span className="eyebrow">BIENVENIDO</span><h2>{register ? 'Crea tu cuenta' : 'Continúa tu progreso'}</h2><p>{register ? 'Empieza con un diagnóstico completo.' : 'Ingresa para retomar justo donde lo dejaste.'}</p>
      <form onSubmit={submit}>{register ? <><label>Usuario<input required minLength="3" maxLength="50" pattern="[A-Za-z0-9_.-]+" value={form.username} onChange={e => setForm({...form, username: e.target.value})} placeholder="tu_usuario" /></label><label>Nombre completo<input required minLength="2" value={form.name} onChange={e => setForm({...form, name: e.target.value})} placeholder="Tu nombre" /></label><label>Correo electrónico<input required type="email" value={form.email} onChange={e => setForm({...form, email: e.target.value})} placeholder="tu@correo.com" /></label></> : <label>Usuario o correo<input required value={form.user} onChange={e => setForm({...form, user: e.target.value})} placeholder="tu_usuario" /></label>}<label>Contraseña<input required minLength="8" type="password" value={form.password} onChange={e => setForm({...form, password: e.target.value})} placeholder="Mínimo 8 caracteres" /></label>{error && <div className="error">{error}</div>}<button className="primary wide" disabled={loading}>{loading ? 'Un momento…' : register ? 'Crear cuenta' : 'Iniciar sesión'} <ArrowRight size={18}/></button></form>
      <div className="switch">{register ? '¿Ya tienes una cuenta?' : '¿Primera vez aquí?'} <button onClick={() => { setRegister(!register); setError('') }}>{register ? 'Inicia sesión' : 'Crea una gratis'}</button></div>
    </div></section>
  </main>
}

function Header({ user, onLogout }) {
  return <header><Logo/><nav><span className="user-chip"><CircleUserRound size={20}/>{user.name.split(' ')[0]}</span><button className="icon-btn" onClick={onLogout} title="Cerrar sesión"><LogOut size={19}/></button></nav></header>
}

function ModuleCards({ scores }) {
  return <div className="module-grid">{Object.entries(moduleMeta).map(([key, meta]) => { const Icon = meta.Icon; const score = scores?.[key]; return <article className="module-card" key={key}><div className="module-icon" style={{ color: meta.color, background: `${meta.color}12` }}><Icon/></div><div><span>{score == null ? `Módulo · ${meta.label}` : meta.label}</span><strong>{score == null ? '25 preguntas · incluido' : `${score}%`}</strong></div>{score != null && <div className="mini-bar"><i style={{width:`${score}%`, background:meta.color}}/></div>}</article> })}</div>
}

function Dashboard({ user, onStart, onResume }) {
  const [data, setData] = useState(null)
  const [level, setLevel] = useState('B2')
  const [error, setError] = useState('')
  const [generating, setGenerating] = useState(false)
  useEffect(() => { api('/dashboard').then(setData).catch(e => setError(e.message)) }, [])
  async function start() { setGenerating(true); setError(''); try { onStart(await api('/assessments', { method: 'POST', body: JSON.stringify({ level }) })) } catch (e) { setError(e.message); setGenerating(false) } }
  if (!data) return <div className="center-loader">{error || 'Preparando tu espacio…'}</div>
  const last = data.history[0]
  return <div className="dashboard page"><section className="welcome"><div><span className="eyebrow">TU ESPACIO DE APRENDIZAJE</span><h1>Hola, {user.name.split(' ')[0]} <span>👋</span></h1><p>{data.active ? 'Tu evaluación te está esperando. Continúa sin perder tu avance.' : last ? 'Estos son tus resultados más recientes y tu siguiente foco.' : 'Comencemos por descubrir tu nivel real de inglés.'}</p></div>{last && <div className="score-ring" style={{'--score':`${last.score * 3.6}deg`}}><div><strong>{last.score}</strong><small>/ 100</small></div></div>}</section>
    {error && <div className="error dashboard-error">{error}</div>}{data.active ? <section className="resume-card"><div className="resume-icon"><Play fill="currentColor"/></div><div className="resume-info"><span className="eyebrow light">GENERAL EN PROGRESO · NIVEL {data.active.level}</span><h2>Continúa tu evaluación</h2><p>{data.active.answered} de 100 respuestas guardadas</p><div className="progress"><i style={{width:`${data.active.progress_percent}%`}}/></div></div><button className="light-btn" onClick={() => onResume(data.active)}>Retomar <ChevronRight size={18}/></button></section> : <section className="start-card"><div><span className="eyebrow">EVALUACIÓN DISPONIBLE · GENERAL</span><h2>{generating ? 'Creando tu evaluación…' : '¿Listo para conocer tu nivel?'}</h2><p>{generating ? 'La IA está generando 100 preguntas únicas. Puede tardar unos minutos; no cierres esta pantalla.' : '100 preguntas: 25 por cada uno de los cuatro módulos.'}</p></div><div className="level-picker"><label>Nivel objetivo</label><div>{levels.map(l => <button disabled={generating} key={l} className={level === l ? 'selected' : ''} onClick={() => setLevel(l)}>{l}</button>)}</div></div><button className="primary" disabled={generating} onClick={start}>{generating ? 'Generando…' : 'Comenzar General'} {!generating && <ArrowRight size={18}/>}</button></section>}
    <section className="section"><div className="section-title"><div><span className="eyebrow">{last ? 'PANORAMA' : 'MÓDULOS DE GENERAL'}</span><h2>{last ? 'Tu última evaluación General' : 'Speaking, Writing, Reading y Listening'}</h2></div>{last && <span className="date-pill">Nivel {last.level}</span>}</div><ModuleCards scores={last?.module_scores}/></section>
    <section className="lower-grid"><article className="suggestions"><div className="section-title"><div><span className="eyebrow">RUTA PERSONAL</span><h2>Recomendado para ti</h2></div><Sparkles color="#7c3aed"/></div>{data.suggestions.map((s,i)=><div className="suggestion" key={s}><span>{i+1}</span><p>{s}</p></div>)}</article><article className="history"><div className="section-title"><div><span className="eyebrow">HISTORIAL</span><h2>Tu progreso</h2></div><BarChart3/></div>{data.history.length ? data.history.slice(0,4).map(x=><div className="history-row" key={x.id}><div><b>Nivel {x.level}</b><small>{new Date(x.completed_at).toLocaleDateString('es')}</small></div><strong>{x.score}%</strong></div>) : <div className="empty"><Target/><p>Tus evaluaciones completadas aparecerán aquí.</p></div>}</article></section>
  </div>
}

function Assessment({ initial, onDone, onExit }) {
  const [assessment, setAssessment] = useState(initial)
  const [selected, setSelected] = useState('')
  const [feedback, setFeedback] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const q = assessment.question
  const meta = q ? moduleMeta[q.module] : moduleMeta.speech
  const Icon = meta.Icon
  function listen() { if (!q?.context) return; speechSynthesis.cancel(); const u = new SpeechSynthesisUtterance(q.context); u.lang='en-US'; u.rate=.9; speechSynthesis.speak(u) }
  async function submit() {
    if (!selected || loading) return; setLoading(true); setError('')
    try { const result = await api(`/assessments/${assessment.id}/answers`, { method:'POST', body:JSON.stringify({question_id:q.id, selected_answer:selected}) }); setFeedback(result) } catch(e) { setError(e.message) } finally { setLoading(false) }
  }
  function next() { if (feedback.assessment.status === 'completed') onDone(assessment.id); else { setAssessment(feedback.assessment); setSelected(''); setFeedback(null) } }
  const withinModule = (assessment.answered % 25) + 1
  return <div className="test-page"><div className="test-top"><Logo/><button className="exit-btn" onClick={onExit}><X size={18}/> Guardar y salir</button></div><div className="test-progress"><div className="test-progress-label"><span>Progreso general</span><b>{assessment.answered}/100</b></div><div className="progress"><i style={{width:`${assessment.progress_percent}%`}}/></div><div className="step-dots">{Object.entries(moduleMeta).map(([key,m],i)=>{const MI=m.Icon; const complete=assessment.answered >= (i+1)*25; const active=q?.module===key; return <div className={`${active?'active ':''}${complete?'complete':''}`} key={key}><span>{complete?<Check size={16}/>:<MI size={16}/>}</span><small>{m.label}</small></div>})}</div></div>
    <main className="question-wrap"><div className="question-head"><div className="question-type" style={{color:meta.color}}><Icon size={20}/>{meta.label}</div><span>Pregunta {withinModule} de 25</span></div><article className="question-card">{q?.context && <div className={`context-box ${q.module}`}><div className="context-label">{q.module==='listening' ? <><Volume2/> Escucha el audio</> : <><BookOpen/> Lee el texto</>}</div>{q.module==='listening' ? <button className="audio-btn" onClick={listen}><Play fill="currentColor"/> Reproducir</button> : <p>{q.context}</p>}</div>}<h1>{q?.prompt}</h1><div className="choices">{q?.choices.map((choice,i)=>{let cls=selected===choice?'selected':''; if(feedback){if(choice===feedback.correct_answer) cls='correct'; else if(choice===selected) cls='wrong'} return <button disabled={!!feedback} className={cls} key={choice} onClick={()=>setSelected(choice)}><span>{String.fromCharCode(65+i)}</span>{choice}{cls==='correct'&&<Check/>}{cls==='wrong'&&<X/>}</button>})}</div>{feedback && <div className={`feedback ${feedback.correct?'ok':'no'}`}><b>{feedback.correct ? '¡Muy bien!' : 'Casi. Revisa esta idea.'}</b><p>{feedback.explanation}</p></div>}{error&&<div className="error">{error}</div>}</article><div className="question-actions"><span>{selected && !feedback ? 'Respuesta seleccionada' : 'Elige una opción para continuar'}</span>{feedback?<button className="primary" onClick={next}>{feedback.assessment.status==='completed'?'Ver resultados':'Siguiente'} <ArrowRight size={18}/></button>:<button className="primary" disabled={!selected||loading} onClick={submit}>{loading?'Guardando…':'Comprobar'} <ArrowRight size={18}/></button>}</div></main>
  </div>
}

function Results({ id, onHome }) {
  const [result,setResult]=useState(null)
  const [error,setError]=useState('')
  useEffect(()=>{api(`/assessments/${id}/results`).then(setResult).catch(e=>setError(e.message))},[id])
  if(!result)return <div className="center-loader">{error || 'Calculando resultados…'}</div>
  return <main className="result-page"><div className="result-hero"><div className="trophy">🏆</div><span className="eyebrow light">EVALUACIÓN COMPLETADA</span><h1>¡Gran trabajo!</h1><p>Ya tienes un punto de partida claro para seguir avanzando.</p><div className="big-score"><strong>{result.score}</strong><span>/100</span></div><small>Nivel evaluado: {result.level}</small></div><section className="result-body"><span className="eyebrow">RESULTADO POR HABILIDAD</span><h2>Tu perfil de inglés</h2><ModuleCards scores={result.module_scores}/><button className="primary" onClick={onHome}>Ver mi plan personalizado <Sparkles size={18}/></button></section></main>
}

export default function App() {
  const [user,setUser]=useState(null), [view,setView]=useState(() => session.token ? 'loading' : 'auth'), [assessment,setAssessment]=useState(null), [resultId,setResultId]=useState(null)
  useEffect(()=>{ if(session.token) api('/auth/me').then(u=>{setUser(u);setView('dashboard')}).catch(()=>setView('auth')) },[])
  useEffect(()=>{ const expired=()=>{setUser(null);setView('auth')}; window.addEventListener('session-expired',expired); return()=>window.removeEventListener('session-expired',expired) },[])
  function logout(){session.token=null;setUser(null);setView('auth')}
  if(view==='loading')return <div className="center-loader">Cargando…</div>
  if(view==='auth')return <Auth onAuth={u=>{setUser(u);setView('dashboard')}}/>
  if(view==='assessment')return <Assessment initial={assessment} onDone={id=>{setResultId(id);setView('results')}} onExit={()=>setView('dashboard')}/>
  if(view==='results')return <Results id={resultId} onHome={()=>setView('dashboard')}/>
  return <><Header user={user} onLogout={logout}/><Dashboard key={view} user={user} onStart={a=>{setAssessment(a);setView('assessment')}} onResume={a=>{setAssessment(a);setView('assessment')}}/></>
}

