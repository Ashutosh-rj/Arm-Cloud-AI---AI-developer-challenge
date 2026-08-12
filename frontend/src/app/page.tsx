'use client';

import React, { useState, useEffect } from 'react';
import { AgentGraph } from '../components/AgentGraph';
import { OptimizationCertificate, CertificateData } from '../components/OptimizationCertificate';
import { Play, Zap, BarChart3, Cpu, ShieldCheck, DollarSign, Activity, LogOut } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import { useAuth } from '../contexts/AuthContext';
import { LoginScreen } from '../components/LoginScreen';
import { apiClient, WS_BASE } from '../lib/apiClient';

export default function CommandCenter() {
  const { isAuthenticated, token, logout } = useAuth();
  
  const [modelUrl, setModelUrl] = useState('meta-llama/Llama-3.2-3B-Instruct');
  const [targetCloud, setTargetCloud] = useState('graviton4');
  const [isRunning, setIsRunning] = useState(false);
  const [runId, setRunId] = useState<string | null>(null);
  const [currentPhase, setCurrentPhase] = useState('idle');
  const [certificate, setCertificate] = useState<CertificateData | null>(null);
  const [tpsHistory, setTpsHistory] = useState<any[]>([]);
  const [dailyTokens, setDailyTokens] = useState<number>(100); // Millions of tokens per day
  const [tpsGain, setTpsGain] = useState<string | null>(null);
  const [costDrop, setCostDrop] = useState<string | null>(null);
  const [qualityDelta, setQualityDelta] = useState<string | null>(null);
  const [cloudPricing, setCloudPricing] = useState<any>({ x86_cost_per_1m: null, arm_cost_per_1m: null, x86_tps_baseline: null });

  useEffect(() => {
    if (!isAuthenticated) return;
    const fetchPricing = async () => {
      try {
        const data = await apiClient(`/api/v1/analytics?cloud=${targetCloud}`);
        if (data && data.pricing) {
          setCloudPricing((prev: any) => ({ ...prev, ...data.pricing }));
        }
      } catch (err) {
        console.warn('Failed to fetch pricing:', err);
      }
    };
    fetchPricing();
  }, [targetCloud, isAuthenticated]);

  const handleStartRun = async () => {
    setIsRunning(true);
    setCertificate(null);
    setCurrentPhase('planning');
    setTpsHistory([]);
    setTpsGain(null);
    setCostDrop(null);
    setQualityDelta(null);

    try {
      const data = await apiClient('/api/v1/optimize', {
        method: 'POST',
        body: JSON.stringify({
          model_url: modelUrl,
          target_clouds: ['graviton4', 'cobalt100', 'axion'],
          quality_floor: 0.98,
        }),
      });

      if (data && data.run_id) {
        setRunId(data.run_id);
        connectWebSocket(data.run_id);
      }
    } catch (err) {
      console.error('Backend API offline or failed to start run:', err);
      setIsRunning(false);
      setCurrentPhase('error');
    }
  };

  const connectWebSocket = (id: string) => {
    const wsUrl = `${WS_BASE}/ws/${id}?token=${token}`;
    const ws = new WebSocket(wsUrl);

    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      
      // Update phase from canonical event schema
      if (msg.phase) setCurrentPhase(msg.phase);
      
      if (msg.data?.certificate) {
        setCertificate(msg.data.certificate);
        setIsRunning(false);
      }
      
      if (msg.data?.benchmark_results && msg.data.benchmark_results.length > 0) {
        const res = msg.data.benchmark_results[0];
        
        setTpsHistory(prev => {
          const x86Baseline = cloudPricing?.x86_tps_baseline;
          const currentTps = res.tps_p50;
          return [
            ...prev,
            { time: `${prev.length * 4}s`, x86_xeon: x86Baseline, graviton4_spec: currentTps }
          ];
        });

        if (res.tps_p50 && res.x86_baseline_tps) {
           const gain = ((res.tps_p50 - res.x86_baseline_tps) / res.x86_baseline_tps * 100);
           setTpsGain(`+${gain.toFixed(0)}% TPS`);
        }
        if (res.cost_per_1m_tokens_usd && res.x86_baseline_cost) {
           const drop = ((res.x86_baseline_cost - res.cost_per_1m_tokens_usd) / res.x86_baseline_cost * 100);
           setCostDrop(`-${drop.toFixed(0)}% USD`);
        }
      }
      
      if (msg.data?.quality_reports && msg.data.quality_reports.length > 0) {
        const qRes = msg.data.quality_reports[0];
        if (qRes.score_delta !== undefined) {
           setQualityDelta(`${qRes.score_delta > 0 ? '+' : ''}${qRes.score_delta.toFixed(3)} (${qRes.passed ? 'PASS' : 'FAIL'})`);
        }
      }
    };

    ws.onerror = () => {
      console.error('WebSocket error. Connection to agent swarm lost.');
      setIsRunning(false);
      setCurrentPhase('error');
    };
  };

  if (!isAuthenticated) {
    return <LoginScreen />;
  }

  const calculatedMonthlySavings = cloudPricing?.x86_cost_per_1m && cloudPricing?.arm_cost_per_1m 
    ? ((cloudPricing.x86_cost_per_1m - cloudPricing.arm_cost_per_1m) * dailyTokens * 30).toLocaleString('en-US', {
        maximumFractionDigits: 0
      })
    : null;

  return (
    <main className="min-h-screen p-6 space-y-6 max-w-[1600px] mx-auto text-gray-100">
      {/* Top Header */}
      <div
        aria-live="polite"
        aria-atomic="true"
        className="sr-only"
        style={{ position: 'absolute', width: '1px', height: '1px', padding: 0, margin: '-1px', overflow: 'hidden', clip: 'rect(0,0,0,0)', border: 0 }}
      >
        {isRunning ? `Optimization in progress: ${currentPhase || 'initializing'} phase` : 
         certificate ? 'Optimization complete. Results available.' : ''}
      </div>
      <header className="flex justify-between items-center glass-panel p-4 rounded-2xl border border-white/10 shadow-xl">
        <div className="flex items-center gap-3">
          <div className="w-11 h-11 rounded-xl bg-gradient-to-br from-indigo-500 to-red-600 flex items-center justify-center text-white font-black text-2xl shadow-lg">
            ⚡
          </div>
          <div>
            <h1 className="text-xl font-bold text-white tracking-tight flex items-center gap-2">
              InferaV22 Command Center
              <span className="text-xs bg-red-500/10 text-red-400 border border-red-500/30 px-2.5 py-0.5 rounded-full font-mono">
                Arm Cloud AI
              </span>
            </h1>
            <p className="text-xs text-gray-400 font-medium">Every Version. Faster. Smarter. Optimized.</p>
          </div>
        </div>

        <div className="flex items-center gap-4 text-xs font-mono">
          <button 
            onClick={logout}
            className="flex items-center gap-1.5 text-gray-400 hover:text-white transition px-3 py-1.5 rounded-lg border border-white/5 bg-white/5"
          >
            <LogOut className="w-3.5 h-3.5" /> Sign Out
          </button>
          <div className="flex items-center gap-2 bg-black/40 px-3 py-1.5 rounded-lg border border-white/5">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            AWS Graviton4 (Neoverse V2): ONLINE
          </div>
          <div className="flex items-center gap-2 bg-black/40 px-3 py-1.5 rounded-lg border border-white/5">
            <span className="w-2 h-2 rounded-full bg-blue-400" />
            Azure Cobalt 100: ONLINE
          </div>
          <div className="flex items-center gap-2 bg-black/40 px-3 py-1.5 rounded-lg border border-white/5">
            <span className="w-2 h-2 rounded-full bg-purple-400" />
            GCP Axion: ONLINE
          </div>
        </div>
      </header>

      {/* Model Optimization Trigger Form */}
      <section className="glass-panel p-5 rounded-2xl flex flex-wrap gap-4 items-center justify-between border border-white/10">
        <div className="flex-1 min-w-[320px]">
          <label htmlFor="model-url" className="text-xs font-medium text-gray-400 block mb-1">HuggingFace Model / GGUF URL</label>
          <input
            id="model-url"
            type="text"
            value={modelUrl}
            onChange={(e) => setModelUrl(e.target.value)}
            className="w-full bg-black/50 border border-white/10 rounded-xl px-4 py-2.5 text-sm text-white font-mono focus:outline-none focus:border-indigo-500 transition"
          />
        </div>

        <div className="w-56">
          <label htmlFor="target-cloud" className="text-xs font-medium text-gray-400 block mb-1">Target Cloud Target</label>
          <select
            id="target-cloud"
            value={targetCloud}
            onChange={(e) => setTargetCloud(e.target.value)}
            className="w-full bg-black/50 border border-white/10 rounded-xl px-3 py-2.5 text-sm text-white font-mono focus:outline-none focus:border-indigo-500"
          >
            <option value="graviton4">AWS Graviton4 (Neoverse V2)</option>
            <option value="cobalt100">Azure Cobalt 100</option>
            <option value="axion">GCP Axion</option>
          </select>
        </div>

        <button
          onClick={handleStartRun}
          disabled={isRunning}
          className="mt-5 bg-gradient-to-r from-indigo-600 to-indigo-500 hover:from-indigo-500 hover:to-indigo-400 text-white font-semibold px-6 py-2.5 rounded-xl flex items-center gap-2 text-sm shadow-lg shadow-indigo-500/20 transition disabled:opacity-50"
        >
          {isRunning ? <Zap className="w-4 h-4 animate-spin text-amber-300" /> : <Play className="w-4 h-4 fill-current" />}
          {isRunning ? 'Optimizing Swarm Active...' : 'Launch Optimization Swarm'}
        </button>
      </section>

      {/* Dynamic Agent Graph Visualization */}
      <div className="w-full overflow-x-auto" role="region" aria-label="Agent execution pipeline">
        <AgentGraph currentPhase={currentPhase} />
      </div>

      {/* Live Benchmark & TPS Comparison */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 glass-panel p-5 rounded-2xl space-y-4 border border-white/10">
          <div className="flex justify-between items-center">
            <div>
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <BarChart3 className="w-5 h-5 text-indigo-400" />
                Live Inference Throughput Comparison (Tokens/Sec)
              </h3>
              <p className="text-xs text-gray-400">Comparing x86 Xeon baseline vs. InferaV22-optimized Arm ({targetCloud})</p>
            </div>
            <div className="flex items-center gap-4 text-xs font-mono">
              <span className="flex items-center gap-1.5 text-red-400">
                <span className="w-2.5 h-2.5 rounded-full bg-red-500" /> x86 Xeon (Baseline)
              </span>
              <span className="flex items-center gap-1.5 text-emerald-400">
                <span className="w-2.5 h-2.5 rounded-full bg-emerald-500" /> Arm {targetCloud} (InferaV22)
              </span>
            </div>
          </div>

          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={tpsHistory.length > 0 ? tpsHistory : [{ time: '0s', x86_xeon: cloudPricing?.x86_tps_baseline, graviton4_spec: null }]}>
                <XAxis dataKey="time" stroke="#4B5563" />
                <YAxis stroke="#4B5563" />
                <Tooltip contentStyle={{ background: '#12121A', borderColor: 'rgba(255,255,255,0.1)' }} />
                <Line type="monotone" dataKey="x86_xeon" stroke="#EF4444" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="graviton4_spec" stroke="#10B981" strokeWidth={3} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Real-time KPI Card */}
        <div className="glass-panel p-5 rounded-2xl space-y-4 flex flex-col justify-between border border-white/10">
          <div>
            <h3 className="text-base font-bold text-white flex items-center gap-2 mb-3">
              <Zap className="w-5 h-5 text-emerald-400" />
              Optimization Telemetry
            </h3>

            <div className="space-y-3">
              <div className="bg-black/30 p-3 rounded-xl border border-white/5 flex justify-between items-center">
                <span className="text-xs text-gray-400">Throughput Gain</span>
                <span className="text-lg font-black text-emerald-400 font-mono">{tpsGain || '—'}</span>
              </div>
              <div className="bg-black/30 p-3 rounded-xl border border-white/5 flex justify-between items-center">
                <span className="text-xs text-gray-400">Inference Cost Drop</span>
                <span className="text-lg font-black text-indigo-400 font-mono">{costDrop || '—'}</span>
              </div>
              <div className="bg-black/30 p-3 rounded-xl border border-white/5 flex justify-between items-center">
                <span className="text-xs text-gray-400">MMLU Quality Delta</span>
                <span className="text-sm font-bold text-gray-200 font-mono">{qualityDelta || '—'}</span>
              </div>
            </div>
          </div>

          <div className="p-3 bg-indigo-500/10 border border-indigo-500/20 rounded-xl">
            <div className="text-[11px] text-indigo-300 font-medium flex items-center gap-1">
              <Cpu className="w-3.5 h-3.5 text-indigo-400" /> KleidiAI Micro-kernel Active
            </div>
            <div className="text-[10px] text-gray-400 mt-0.5">
              INT4 micro-kernels exploiting SDOT/UDOT instructions & 256-bit SVE vector registers.
            </div>
          </div>
        </div>
      </div>

      {/* Enterprise ROI Savings Calculator */}
      <section className="glass-panel p-5 rounded-2xl border border-white/10 space-y-4">
        <div className="flex justify-between items-center flex-wrap gap-4">
          <div>
            <h3 className="text-base font-bold text-white flex items-center gap-2">
              <DollarSign className="w-5 h-5 text-emerald-400" />
              Enterprise Arm Cloud ROI Calculator
            </h3>
            <p className="text-xs text-gray-400">Calculate estimated cost savings by replacing x86 GPU/CPU inference with InferaV22 on Arm64</p>
          </div>

          <div className="flex items-center gap-3">
            <label className="text-xs text-gray-400">Daily Inference Volume:</label>
            <input
              type="range"
              min="10"
              max="1000"
              step="10"
              value={dailyTokens}
              onChange={(e) => setDailyTokens(Number(e.target.value))}
              className="accent-indigo-500 w-36"
            />
            <span className="text-xs font-mono font-bold text-indigo-400 bg-indigo-500/10 px-2.5 py-1 rounded-lg border border-indigo-500/20">
              {dailyTokens}M Tokens/day
            </span>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 font-mono text-center">
          <div className="bg-black/30 p-4 rounded-xl border border-white/5">
            <div className="text-xs text-gray-400 mb-1">x86 Baseline Cost / Mo</div>
            <div className="text-xl font-bold text-red-400">
              {cloudPricing?.x86_cost_per_1m ? `$${(cloudPricing.x86_cost_per_1m * dailyTokens * 30).toLocaleString(undefined, { maximumFractionDigits: 0 })}` : '—'}
            </div>
          </div>
          <div className="bg-black/30 p-4 rounded-xl border border-white/5">
            <div className="text-xs text-gray-400 mb-1">InferaV22 Arm Cost / Mo</div>
            <div className="text-xl font-bold text-emerald-400">
              {cloudPricing?.arm_cost_per_1m ? `$${(cloudPricing.arm_cost_per_1m * dailyTokens * 30).toLocaleString(undefined, { maximumFractionDigits: 0 })}` : '—'}
            </div>
          </div>
          <div className="bg-indigo-950/40 p-4 rounded-xl border border-indigo-500/30">
            <div className="text-xs text-indigo-300 mb-1">Projected Monthly Savings</div>
            <div className="text-2xl font-black text-transparent bg-clip-text bg-gradient-to-r from-emerald-400 to-indigo-400">
              {calculatedMonthlySavings ? `$${calculatedMonthlySavings} / mo` : '—'}
            </div>
          </div>
        </div>
        <div className="text-[10px] text-gray-500 text-center mt-2">
          *Pricing estimates based on on-demand instance rates. Actual savings may vary.
        </div>
      </section>

      {/* Dynamic Optimization Certificate View */}
      {certificate && <OptimizationCertificate certificateData={certificate} />}
    </main>
  );
}
