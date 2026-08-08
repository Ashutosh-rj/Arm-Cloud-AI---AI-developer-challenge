'use client';

import React from 'react';
import { ShieldCheck, Download, ExternalLink, Cpu } from 'lucide-react';

export interface CertificateData {
  inferav22_version: string;
  tagline: string;
  certification_id: string;
  model: string;
  score: number;
  signature: string;
  public_url: string;
  optimal_config?: Record<string, any>;
  benchmarks?: Record<string, any>;
  quality_delta?: Record<string, any>;
}

interface CertificateProps {
  certificateData: CertificateData;
}

export const OptimizationCertificate: React.FC<CertificateProps> = ({ certificateData }) => {
  if (!certificateData) return null;

  const handleDownloadHelmChart = async (runId: string) => {
    try {
      const authToken = typeof window !== 'undefined' ? localStorage.getItem('authToken') || '' : '';
      const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      const response = await fetch(`${API_BASE_URL}/api/v1/runs/${runId}/helm-chart`, {
        headers: {
          'Authorization': authToken ? `Bearer ${authToken}` : '',
        },
      });
      if (!response.ok) {
        throw new Error(`Download failed: ${response.statusText}`);
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `inferav22-${runId.substring(0, 8)}.tgz`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Helm chart download failed:', error);
    }
  };

  return (
    <div className="glass-panel rounded-2xl p-6 relative overflow-hidden border border-indigo-500/30 max-w-xl mx-auto my-6 shadow-2xl">
      <div className="absolute -right-12 -top-12 w-40 h-40 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none" />
      
      <div className="flex justify-between items-start border-b border-white/10 pb-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500 to-red-600 flex items-center justify-center text-white font-black text-xl shadow-lg">
            ⚡
          </div>
          <div>
            <h2 className="text-xl font-bold text-white tracking-tight">InferaV22</h2>
            <p className="text-[10px] text-gray-400 font-medium">{certificateData.tagline || 'Every Version. Faster. Smarter. Optimized.'}</p>
          </div>
        </div>
        <div className="flex items-center gap-1.5 text-xs bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 px-3 py-1 rounded-full font-mono">
          <ShieldCheck className="w-4 h-4" />
          VERIFIED OPTIMAL
        </div>
      </div>

      <div className="py-6 space-y-4">
        <div className="flex justify-between items-center bg-black/30 p-3 rounded-lg border border-white/5">
          <div>
            <div className="text-xs text-gray-400">Target Model</div>
            <div className="text-sm font-semibold text-white font-mono">{certificateData.model}</div>
          </div>
          <Cpu className="w-6 h-6 text-indigo-400" />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div className="bg-black/30 p-3 rounded-lg border border-white/5 text-center">
            <div className="text-xs text-gray-400 mb-1">Optimization Score</div>
            <div className="text-3xl font-black text-transparent bg-clip-text bg-gradient-to-r from-emerald-400 to-indigo-400 font-mono">
              {certificateData.score}/100
            </div>
          </div>

          <div className="bg-black/30 p-3 rounded-lg border border-white/5 text-center">
            <div className="text-xs text-gray-400 mb-1">Arm Target Architecture</div>
            <div className="text-sm font-bold text-white font-mono mt-1">Neoverse V2 (SVE256)</div>
            <div className="text-[9px] text-emerald-400 mt-0.5">KleidiAI Micro-kernels Active</div>
          </div>
        </div>

        <div className="bg-black/40 p-3 rounded-lg border border-white/5 font-mono text-[10px] space-y-1 text-gray-400">
          <div className="flex justify-between">
            <span>Cert ID:</span>
            <span className="text-gray-200">{certificateData.certification_id}</span>
          </div>
          <div className="flex justify-between truncate">
            <span>Signature:</span>
            <span className="text-indigo-400 truncate max-w-[240px]">{certificateData.signature}</span>
          </div>
        </div>
      </div>

      <div className="flex gap-3 pt-2">
        <button 
          onClick={() => handleDownloadHelmChart(certificateData.certification_id)}
          className="flex-1 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold py-2.5 px-4 rounded-xl flex items-center justify-center gap-2 transition shadow-lg shadow-indigo-600/20"
        >
          <Download className="w-4 h-4" />
          Download Helm Chart (.tgz)
        </button>
        <a
          href={certificateData.public_url || '#'}
          target="_blank"
          rel="noreferrer"
          className="bg-white/5 hover:bg-white/10 text-white text-xs font-semibold py-2.5 px-4 rounded-xl border border-white/10 flex items-center justify-center gap-1.5 transition"
        >
          <ExternalLink className="w-4 h-4" />
          Verify
        </a>
      </div>
    </div>
  );
};
