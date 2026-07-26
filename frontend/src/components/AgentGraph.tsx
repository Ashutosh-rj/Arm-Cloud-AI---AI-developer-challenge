'use client';

import React from 'react';
import { motion } from 'framer-motion';

export interface AgentNodeState {
  id: string;
  name: string;
  role: string;
  status: 'idle' | 'active' | 'complete' | 'failed';
  x: number;
  y: number;
}

interface AgentGraphProps {
  currentPhase?: string;
  agentsState?: Record<string, 'idle' | 'active' | 'complete' | 'failed'>;
}

const DEFAULT_NODES: Omit<AgentNodeState, 'status'>[] = [
  { id: 'planner', name: 'Planner Agent', role: 'Strategy Decomposition', x: 80, y: 120 },
  { id: 'profiler', name: 'Profiler Agent', role: 'Arm Hardware Inspection', x: 200, y: 60 },
  { id: 'optimizer', name: 'Optimizer Agent', role: 'KleidiAI & Quantization', x: 320, y: 120 },
  { id: 'quality', name: 'Quality Agent', role: 'MMLU Regression Gate', x: 440, y: 60 },
  { id: 'benchmarker', name: 'Benchmark Agent', role: 'Multi-Cloud Load Test', x: 560, y: 120 },
  { id: 'speculative', name: 'Speculative Agent', role: 'Draft Model Orchestration', x: 680, y: 60 },
  { id: 'deployer', name: 'Deployment Agent', role: 'Helm & K8s Generator', x: 800, y: 120 },
  { id: 'verifier', name: 'Verification Agent', role: 'SLA Smoke Validation', x: 920, y: 60 },
  { id: 'certifier', name: 'Certification Agent', role: 'Cryptographic Signing', x: 1040, y: 120 },
  { id: 'monitor', name: 'Monitor Agent', role: 'Drift Telemetry Tracking', x: 1160, y: 60 },
];

export const AgentGraph: React.FC<AgentGraphProps> = ({ currentPhase = 'idle', agentsState = {} }) => {
  const getStatus = (id: string): 'idle' | 'active' | 'complete' | 'failed' => {
    if (agentsState[id]) return agentsState[id];
    
    // Dynamic mapping based on workflow phase
    const phasesOrder = [
      'planning', 'profiling', 'optimizing', 'qualifying',
      'benchmarking', 'speculative', 'deploying', 'verifying', 'certifying', 'monitoring', 'completed'
    ];
    const currentIndex = phasesOrder.indexOf(currentPhase.toLowerCase());
    const agentIndex = DEFAULT_NODES.findIndex(n => n.id === id);

    if (currentIndex === -1) return 'idle';
    if (agentIndex < currentIndex) return 'complete';
    if (agentIndex === currentIndex) return 'active';
    return 'idle';
  };

  return (
    <div className="w-full overflow-x-auto p-4 glass-panel rounded-xl my-4">
      <div className="flex justify-between items-center mb-4">
        <div>
          <h3 className="text-lg font-bold text-white flex items-center gap-2">
            <span className={`w-2.5 h-2.5 rounded-full ${currentPhase === 'completed' ? 'bg-emerald-500' : 'bg-indigo-500 animate-ping'}`} />
            10-Agent Swarm Orchestration (LangGraph)
          </h3>
          <p className="text-xs text-gray-400">Live agent execution state driven by backend WebSockets</p>
        </div>
        <span className="text-xs bg-indigo-500/10 text-indigo-400 px-3 py-1 rounded-full border border-indigo-500/20 font-mono uppercase">
          Phase: {currentPhase}
        </span>
      </div>

      <div className="relative min-w-[1260px] h-[200px] border border-white/5 rounded-lg bg-black/40 overflow-hidden">
        <svg className="absolute inset-0 w-full h-full pointer-events-none">
          {DEFAULT_NODES.map((node, i) => {
            if (i === DEFAULT_NODES.length - 1) return null;
            const nextNode = DEFAULT_NODES[i + 1];
            const status = getStatus(node.id);
            return (
              <line
                key={`line-${node.id}`}
                x1={node.x}
                y1={node.y}
                x2={nextNode.x}
                y2={nextNode.y}
                stroke={status === 'complete' ? '#10B981' : status === 'active' ? '#6366F1' : '#374151'}
                strokeWidth="2"
                strokeDasharray={status === 'active' ? '6 6' : undefined}
              />
            );
          })}
        </svg>

        {DEFAULT_NODES.map((agent) => {
          const status = getStatus(agent.id);
          return (
            <motion.div
              key={agent.id}
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              style={{ left: agent.x - 55, top: agent.y - 30 }}
              className={`absolute w-28 p-2 rounded-lg border text-center transition-all cursor-pointer ${
                status === 'complete'
                  ? 'bg-emerald-950/40 border-emerald-500/50 text-emerald-300'
                  : status === 'active'
                  ? 'bg-indigo-950/60 border-indigo-500 text-indigo-200 shadow-lg shadow-indigo-500/20 ring-2 ring-indigo-500/30'
                  : 'bg-zinc-900/60 border-zinc-800 text-zinc-500'
              }`}
            >
              <div className="text-[10px] font-bold truncate">{agent.name}</div>
              <div className="text-[8px] text-gray-400 mt-0.5 truncate">{agent.role}</div>
              <div className="mt-1 flex justify-center">
                <span
                  className={`text-[7px] uppercase font-mono px-1.5 py-0.5 rounded ${
                    status === 'complete'
                      ? 'bg-emerald-500/20 text-emerald-400'
                      : status === 'active'
                      ? 'bg-indigo-500/20 text-indigo-300 animate-pulse'
                      : 'bg-zinc-800 text-zinc-600'
                  }`}
                >
                  {status}
                </span>
              </div>
            </motion.div>
          );
        })}
      </div>
    </div>
  );
};
