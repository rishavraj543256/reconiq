import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity, AlertTriangle, ArrowRightLeft, BarChart3, Bot, CheckCircle2, Database, Download, FileUp, History, Menu, Moon, Play, RefreshCw, Scale, Settings, ShieldCheck, Sun, X } from "lucide-react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

const API = import.meta.env.VITE_API_URL || "";
async function downloadReport() {
  const token = localStorage.getItem("reconiq_token");
  const response = await fetch(`${API}/api/v1/reports/matches.csv`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!response.ok) throw new Error(`Report download failed (${response.status}).`);
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = "reconiq-matches.csv";
  link.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}
type Dashboard = {total_transactions:number;matched_transactions:number;match_percentage:number;unmatched_transactions:number;discrepancy_amount:string;anomalies:number;pending_approvals:number;recent_runs:{id:string;status:string;matched:number;total:number;duration_ms:number}[]};
async function request<T>(path:string, options:RequestInit={}):Promise<T>{const token=localStorage.getItem("reconiq_token");const response=await fetch(`${API}${path}`,{...options,headers:{...(options.body instanceof FormData?{}:{"Content-Type":"application/json"}),...(token?{Authorization:`Bearer ${token}`}:{})},});if(!response.ok)throw new Error((await response.json().catch(()=>({detail:"Request failed"}))).detail||"Request failed");return response.json();}

const nav=[['Overview',BarChart3],['Data Sources',Database],['Upload Transactions',FileUp],['Reconciliation',ArrowRightLeft],['Matching Rules',Scale],['Discrepancies',AlertTriangle],['Anomaly Detection',Activity],['Review Queue',CheckCircle2],['AI Assistant',Bot],['Reports',Download],['Audit Logs',History],['Settings',Settings]] as const;

export default function App(){
 const [theme,setTheme]=useState(localStorage.getItem('theme')||'dark');const [sidebar,setSidebar]=useState(false);const [active,setActive]=useState('Overview');const [notice,setNotice]=useState('');const qc=useQueryClient();
 useEffect(()=>{document.documentElement.dataset.theme=theme;localStorage.setItem('theme',theme)},[theme]);
 const demo=useMutation({mutationFn:()=>request<{access_token:string}>('/api/v1/demo/session',{method:'POST'}),onSuccess:d=>{localStorage.setItem('reconiq_token',d.access_token);qc.invalidateQueries();setNotice('Secure demo session ready with synthetic data.')},onError:e=>setNotice(e.message)});
 const dashboard=useQuery({queryKey:['dashboard',localStorage.getItem('reconiq_token')],queryFn:()=>request<Dashboard>('/api/v1/dashboard'),enabled:!!localStorage.getItem('reconiq_token')});
 const run=useMutation({mutationFn:()=>request<{matched_records:number;total_records:number}>('/api/v1/reconciliations/run',{method:'POST'}),onSuccess:d=>{setNotice(`Reconciliation completed: ${d.matched_records} of ${d.total_records} invoices matched.`);qc.invalidateQueries({queryKey:['dashboard']})},onError:e=>setNotice(e.message)});
 const anomaly=useMutation({mutationFn:()=>request<{detected:number}>('/api/v1/anomalies/detect',{method:'POST'}),onSuccess:d=>{setNotice(`${d.detected} statistically unusual transactions detected (not confirmed fraud).`);qc.invalidateQueries({queryKey:['dashboard']})},onError:e=>setNotice(e.message)});
 const d=dashboard.data;
 return <div className="app">
  <aside className={sidebar?'sidebar open':'sidebar'}><div className="brand"><span className="brandmark">R</span><div><b>ReconIQ</b><small>Financial Intelligence</small></div><button className="mobile-close" onClick={()=>setSidebar(false)} aria-label="Close navigation"><X/></button></div><nav aria-label="Primary">{nav.map(([label,Icon])=><button className={active===label?'nav active':'nav'} key={label} onClick={()=>{setActive(label);setSidebar(false)}}><Icon size={18}/>{label}</button>)}</nav><div className="secure"><ShieldCheck/><div><b>Demo-safe workspace</b><small>Synthetic records only</small></div></div></aside>
  <main><header><button className="menu" onClick={()=>setSidebar(true)} aria-label="Open navigation"><Menu/></button><div><p className="eyebrow">WORKSPACE / {active.toUpperCase()}</p><h1>{active}</h1></div><div className="header-actions"><button className="icon" onClick={()=>setTheme(theme==='dark'?'light':'dark')} aria-label="Toggle theme">{theme==='dark'?<Sun/>:<Moon/>}</button><span className="status"><i/> API connected</span></div></header>
  {!localStorage.getItem('reconiq_token')?<section className="welcome"><span className="pill">OPEN-SOURCE FINANCIAL OPERATIONS</span><h2>Reconcile financial data with evidence, not guesswork.</h2><p>Run deterministic matching and machine-learning anomaly detection against a safe synthetic dataset. Every metric is calculated by the backend.</p><button className="primary big" onClick={()=>demo.mutate()} disabled={demo.isPending}>{demo.isPending?<RefreshCw className="spin"/>:<Play/>} Try Live Demo</button></section>:
  <div className="content">{notice&&<div className="notice" role="status">{notice}<button onClick={()=>setNotice('')} aria-label="Dismiss"><X size={16}/></button></div>}
  {active==='Overview'&&<><section className="hero-row"><div><span className="pill">LIVE TENANT METRICS</span><h2>Financial control, continuously explained.</h2><p>Metrics below come directly from imported and reconciled records.</p></div><div className="actions"><button className="secondary" onClick={()=>anomaly.mutate()} disabled={anomaly.isPending}><Activity/> Detect anomalies</button><button className="primary" onClick={()=>run.mutate()} disabled={run.isPending}><Play/> Run reconciliation</button></div></section>
  {dashboard.isLoading?<div className="loading">Calculating tenant metrics…</div>:dashboard.error?<div className="error">{dashboard.error.message}</div>:<><section className="metrics"><Metric label="Imported transactions" value={d?.total_transactions??0}/><Metric label="Match rate" value={`${d?.match_percentage??0}%`} accent/><Metric label="Unmatched invoices" value={d?.unmatched_transactions??0}/><Metric label="Discrepancy total" value={`$${Number(d?.discrepancy_amount??0).toLocaleString()}`}/><Metric label="Anomaly signals" value={d?.anomalies??0}/></section><section className="grid"><article className="panel chart"><div className="panel-title"><div><span>RECONCILIATION RUNS</span><h3>Matched vs reviewed</h3></div></div>{d?.recent_runs.length?<ResponsiveContainer width="100%" height={280}><BarChart data={d.recent_runs.map((r,i)=>({name:`Run ${d.recent_runs.length-i}`,matched:r.matched,unmatched:r.total-r.matched}))}><CartesianGrid strokeDasharray="3 3" vertical={false}/><XAxis dataKey="name"/><YAxis/><Tooltip/><Bar dataKey="matched" fill="#35c69a" radius={[5,5,0,0]}/><Bar dataKey="unmatched" fill="#f5a15d" radius={[5,5,0,0]}/></BarChart></ResponsiveContainer>:<Empty text="Run your first reconciliation to populate this chart."/>}</article><article className="panel"><div className="panel-title"><div><span>RECENT EXECUTION</span><h3>Evidence trail</h3></div></div>{d?.recent_runs.length?<div className="runs">{d.recent_runs.map(r=><div className="run-item" key={r.id}><CheckCircle2/><div><b>{r.matched} / {r.total} matched</b><small>{r.id.slice(0,8)} · {r.duration_ms} ms</small></div><span>{r.status}</span></div>)}</div>:<Empty text="No completed runs yet."/>}</article></section></>}
  </>}
  {active==='Reconciliation'&&<Feature title="Deterministic reconciliation engine" description="Executes amount, date and fuzzy-reference strategies with stable tie-breaking and no double matching." action="Run reconciliation" onAction={()=>run.mutate()}/>} 
  {active==='Anomaly Detection'&&<Feature title="Isolation Forest anomaly detection" description="Analyzes actual tenant payment distributions. Signals are explicitly not labelled as confirmed fraud." action="Detect anomalies" onAction={()=>anomaly.mutate()}/>} 
  {active==='Reports'&&<Feature title="Auditable exports" description="Download the tenant's actual reconciliation match evidence as CSV." action="Download match report" onAction={()=>void downloadReport().catch(error=>setNotice(error.message))}/>} 
  {!['Overview','Reconciliation','Anomaly Detection','Reports'].includes(active)&&<Feature title={active} description="This module is backed by the versioned API and tenant-isolated financial data model. Use the OpenAPI documentation for the complete operational workflow."/>}
  </div>}</main></div>
}
function Metric({label,value,accent=false}:{label:string;value:string|number;accent?:boolean}){return <article className={accent?'metric accent':'metric'}><span>{label}</span><strong>{value}</strong><small>Current tenant</small></article>}
function Empty({text}:{text:string}){return <div className="empty"><Database/><p>{text}</p></div>}
function Feature({title,description,action,onAction}:{title:string;description:string;action?:string;onAction?:()=>void}){return <section className="feature"><span className="pill">FUNCTIONAL MODULE</span><h2>{title}</h2><p>{description}</p>{action&&<button className="primary" onClick={onAction}><Play/>{action}</button>}</section>}
