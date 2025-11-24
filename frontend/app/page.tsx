'use client';

import React, { useState } from 'react';
import {
  Play,
  Pause,
  Command,
  Sparkles,
  ChevronDown,
  Layers,
  Settings2,
  Share2,
  Undo2,
  Redo2,
  Maximize2,
  Image as ImageIcon,
  Paperclip,
  Zap,
  History,
  MoreHorizontal,
  Plus
} from 'lucide-react';

export default function ContinuityStudio() {
  const [activeTab, setActiveTab] = useState('generate');
  const [prompt, setPrompt] = useState("Cinematic wide shot, Cyberpunk detective Sarah walking through neon rain, reflection in puddles, 8k resolution, volumetric lighting");

  return (
    <div className="h-screen w-full bg-[#000000] text-white font-sans overflow-hidden flex flex-col selection:bg-purple-500/30">

      {/* --- 1. THE HEADER (Minimal, Technical) --- */}
      <header className="h-12 border-b border-white/10 bg-black/50 backdrop-blur-md flex items-center justify-between px-4 z-50">
        <div className="flex items-center gap-4">
          <div className="w-8 h-8 bg-gradient-to-tr from-purple-600 to-blue-600 rounded-lg flex items-center justify-center shadow-[0_0_15px_rgba(124,58,237,0.3)]">
            <div className="w-3 h-3 bg-white rounded-full" />
          </div>
          <div className="flex flex-col">
            <span className="text-xs font-medium tracking-wide text-zinc-300">Continuity AI</span>
            <span className="text-[10px] text-zinc-500 font-mono uppercase tracking-widest">Project: NEON_01</span>
          </div>
        </div>

        <div className="flex items-center gap-1 bg-zinc-900/50 rounded-lg p-1 border border-white/5">
          <TabButton active={activeTab === 'generate'} onClick={() => setActiveTab('generate')} label="Generate" />
          <TabButton active={activeTab === 'assets'} onClick={() => setActiveTab('assets')} label="Assets" />
          <TabButton active={activeTab === 'edit'} onClick={() => setActiveTab('edit')} label="Editor" />
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1 px-2 py-1 rounded-md bg-purple-500/10 border border-purple-500/20 text-[10px] text-purple-400 font-mono">
            <Zap size={10} />
            <span>VEO-2 ACTIVE</span>
          </div>
          <button className="p-2 hover:bg-white/10 rounded-md text-zinc-400 hover:text-white transition-colors">
            <Share2 size={16} />
          </button>
          <div className="w-8 h-8 rounded-full bg-zinc-800 border border-white/10" />
        </div>
      </header>

      {/* --- MAIN WORKSPACE --- */}
      <div className="flex-1 relative flex overflow-hidden">

        {/* --- 2. LEFT HUD: The "Brain" (Floating Panel) --- */}
        <div className="absolute left-4 top-4 bottom-4 w-[280px] flex flex-col gap-4 z-40 pointer-events-none">
          {/* Panel Container */}
          <div className="flex-1 bg-[#09090b]/90 backdrop-blur-xl border border-white/10 rounded-xl overflow-hidden pointer-events-auto flex flex-col shadow-2xl">

            {/* Panel Header */}
            <div className="p-3 border-b border-white/5 flex items-center justify-between">
              <h3 className="text-[11px] font-bold text-zinc-400 uppercase tracking-widest">Memory Layers</h3>
              <Settings2 size={14} className="text-zinc-600 hover:text-zinc-300 cursor-pointer" />
            </div>

            {/* Active Anchor (The Hero) */}
            <div className="p-4 bg-gradient-to-b from-purple-900/20 to-transparent border-b border-white/5">
              <div className="flex items-center gap-3 mb-3">
                <div className="w-10 h-10 rounded-full ring-2 ring-purple-500/50 p-0.5">
                  <div className="w-full h-full rounded-full bg-zinc-800 overflow-hidden relative">
                    {/* Placeholder for User Avatar */}
                    <div className="absolute inset-0 flex items-center justify-center text-[10px] font-bold">SARAH</div>
                  </div>
                </div>
                <div>
                  <div className="text-xs font-bold text-white">Sarah (Protagonist)</div>
                  <div className="text-[10px] text-purple-400 flex items-center gap-1">
                    <div className="w-1.5 h-1.5 rounded-full bg-purple-400 animate-pulse" />
                    Identity Locked
                  </div>
                </div>
              </div>
              <div className="flex gap-2">
                <button className="flex-1 bg-white/5 hover:bg-white/10 border border-white/10 rounded text-[10px] py-1.5 transition-colors">Edit Ref</button>
                <button className="flex-1 bg-white/5 hover:bg-white/10 border border-white/10 rounded text-[10px] py-1.5 transition-colors">View Nodes</button>
              </div>
            </div>

            {/* Context Rules */}
            <div className="flex-1 p-4 overflow-y-auto">
              <div className="mb-6">
                <Label>Global Consistency</Label>
                <div className="space-y-2 mt-2">
                  <ToggleRow label="Facial Structure" active />
                  <ToggleRow label="Outfit (Leather Jacket)" active />
                  <ToggleRow label="Cinematography Style" active />
                  <ToggleRow label="Color Grading" />
                </div>
              </div>

              <div>
                <Label>Scene Context</Label>
                <textarea
                  className="w-full bg-black/40 border border-white/10 rounded-lg p-3 text-xs text-zinc-300 min-h-[100px] resize-none focus:outline-none focus:border-purple-500/50 placeholder-zinc-700 mt-2 font-mono leading-relaxed"
                  defaultValue="Cyberpunk City, Rainy, Neon lights reflecting on wet pavement. High contrast, noir atmosphere."
                />
              </div>
            </div>
          </div>
        </div>

        {/* --- 3. CENTER STAGE: The Viewport --- */}
        <div className="flex-1 bg-[#050505] relative flex flex-col items-center justify-center">

          {/* Grid Background */}
          <div className="absolute inset-0 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-20 pointer-events-none"></div>
          <div className="absolute inset-0" style={{ backgroundImage: 'radial-gradient(circle at 50% 50%, #1a1a1a 1px, transparent 1px)', backgroundSize: '40px 40px', opacity: 0.2 }}></div>

          {/* Main Video Player / Preview */}
          <div className="relative w-[80%] max-w-5xl aspect-video bg-black border border-white/10 rounded-lg shadow-2xl flex items-center justify-center overflow-hidden group">
            <div className="text-zinc-700 flex flex-col items-center gap-4">
              <div className="w-16 h-16 rounded-full border border-white/10 flex items-center justify-center">
                <Play className="fill-zinc-700 text-zinc-700" />
              </div>
              <p className="text-xs font-mono text-zinc-600">PREVIEW GENERATION [EMPTY]</p>
            </div>

            {/* On-Canvas Controls */}
            <div className="absolute bottom-6 left-1/2 -translate-x-1/2 flex items-center gap-4 bg-black/80 backdrop-blur-md px-6 py-3 rounded-full border border-white/10 opacity-0 group-hover:opacity-100 transition-all duration-300 translate-y-2 group-hover:translate-y-0">
              <ControlIcon icon={<Undo2 size={16} />} />
              <ControlIcon icon={<Pause size={16} />} />
              <ControlIcon icon={<Redo2 size={16} />} />
              <div className="h-4 w-px bg-white/20 mx-2"></div>
              <span className="text-xs font-mono text-zinc-400">00:00:00:00</span>
            </div>
          </div>

        </div>

        {/* --- 4. RIGHT HUD: Parameters (Floating Panel) --- */}
        <div className="absolute right-4 top-4 bottom-4 w-[280px] flex flex-col z-40 pointer-events-none">
          <div className="w-full bg-[#09090b]/90 backdrop-blur-xl border border-white/10 rounded-xl p-4 pointer-events-auto shadow-2xl">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-[11px] font-bold text-zinc-400 uppercase tracking-widest">Settings</h3>
              <div className="text-[10px] text-green-500 font-mono">READY</div>
            </div>

            <div className="space-y-6">
              <ControlGroup label="Model Engine">
                <select className="w-full bg-black/40 border border-white/10 rounded px-2 py-2 text-xs text-zinc-300 outline-none focus:border-purple-500/50">
                  <option>Google Veo (High Res)</option>
                  <option>Runway Gen-3 Alpha</option>
                  <option>OpenAI Sora</option>
                </select>
              </ControlGroup>

              <ControlGroup label="Aspect Ratio">
                <div className="grid grid-cols-3 gap-2">
                  <AspectRatioBtn label="16:9" active />
                  <AspectRatioBtn label="9:16" />
                  <AspectRatioBtn label="2.35:1" />
                </div>
              </ControlGroup>

              <ControlGroup label="Motion Scale (1-10)">
                <input type="range" className="w-full accent-purple-500 h-1 bg-zinc-800 rounded-lg appearance-none cursor-pointer" />
                <div className="flex justify-between text-[10px] text-zinc-600 mt-1 font-mono">
                  <span>LOW</span>
                  <span>HIGH</span>
                </div>
              </ControlGroup>

              <ControlGroup label="Seed">
                <div className="flex gap-2">
                  <input type="text" value="2938472" className="flex-1 bg-black/40 border border-white/10 rounded px-2 py-1.5 text-xs text-zinc-500 font-mono" readOnly />
                  <button className="p-1.5 hover:bg-white/10 rounded border border-white/10 text-zinc-400"><History size={12} /></button>
                </div>
              </ControlGroup>
            </div>
          </div>
        </div>

      </div>

      {/* --- 5. THE SEQUENCER & PROMPT (Bottom Dock) --- */}
      <div className="h-[280px] bg-[#09090b] border-t border-white/10 flex flex-col z-50">

        {/* Toolbar */}
        <div className="h-10 border-b border-white/5 flex items-center justify-between px-4 bg-black/20">
          <div className="flex items-center gap-4">
            <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest">Timeline</span>
            <div className="h-3 w-px bg-white/10"></div>
            <div className="flex gap-2">
              <TimeTool icon={<Layers size={12} />} label="Tracks" />
              <TimeTool icon={<MoreHorizontal size={12} />} />
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[10px] text-zinc-600 font-mono">AUTO-SAVE: 2s AGO</span>
          </div>
        </div>

        <div className="flex flex-1 overflow-hidden">
          {/* Timeline Left Header */}
          <div className="w-48 border-r border-white/5 bg-black/20 flex flex-col">
            <div className="flex-1 border-b border-white/5 p-2 flex items-center gap-2 group hover:bg-white/5 transition-colors cursor-pointer">
              <div className="w-1 bg-purple-500 h-full rounded-full opacity-0 group-hover:opacity-100"></div>
              <span className="text-[10px] font-medium text-zinc-400">Video Track 1</span>
            </div>
            <div className="flex-1 border-b border-white/5 p-2 flex items-center gap-2 group hover:bg-white/5 transition-colors cursor-pointer">
              <div className="w-1 bg-blue-500 h-full rounded-full opacity-0 group-hover:opacity-100"></div>
              <span className="text-[10px] font-medium text-zinc-400">Audio Track</span>
            </div>
          </div>

          {/* Timeline Tracks (Visual) */}
          <div className="flex-1 relative overflow-x-auto bg-[#050505]">
            {/* Time Ruler */}
            <div className="h-6 border-b border-white/5 flex items-end px-2 gap-20 text-[9px] font-mono text-zinc-600">
              <span>00:00</span><span>00:05</span><span>00:10</span><span>00:15</span><span>00:20</span>
            </div>

            {/* Playhead */}
            <div className="absolute top-0 bottom-0 left-[120px] w-px bg-red-500 z-10 flex flex-col items-center">
              <div className="w-2 h-2 bg-red-500 rotate-45 -mt-1"></div>
            </div>

            {/* Clips */}
            <div className="p-2 relative">
              {/* Clip 1 */}
              <div className="absolute left-[10px] top-2 w-[100px] h-12 bg-zinc-800 rounded border border-white/10 overflow-hidden group cursor-pointer ring-1 ring-transparent hover:ring-purple-500 transition-all">
                <div className="w-full h-full opacity-50 bg-[url('/api/placeholder/100/48')] bg-cover"></div>
                <div className="absolute bottom-1 left-1 text-[9px] font-mono text-white truncate w-full px-1">Shot_01</div>
              </div>
              {/* Clip 2 */}
              <div className="absolute left-[115px] top-2 w-[140px] h-12 bg-purple-900/30 rounded border border-purple-500/30 overflow-hidden group cursor-pointer ring-1 ring-transparent hover:ring-purple-500 transition-all">
                <div className="absolute inset-0 flex items-center justify-center">
                  <Sparkles size={12} className="text-purple-400 animate-pulse" />
                </div>
                <div className="absolute bottom-1 left-1 text-[9px] font-mono text-purple-200 truncate w-full px-1">Generating...</div>
              </div>
            </div>
          </div>
        </div>

        {/* --- THE MEGA PROMPT BAR (Floating Overlay) --- */}
        <div className="absolute bottom-8 left-1/2 -translate-x-1/2 w-[600px] max-w-full z-50">
          <div className="bg-[#18181b]/90 backdrop-blur-2xl border border-white/10 rounded-2xl shadow-[0_0_50px_rgba(0,0,0,0.5)] p-2 ring-1 ring-white/5">

            {/* Input Area */}
            <div className="flex items-start gap-3 p-2">
              <div className="mt-1.5">
                <Sparkles className="text-purple-500" size={18} />
              </div>
              <textarea
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                className="w-full bg-transparent text-sm text-zinc-100 placeholder-zinc-500 resize-none focus:outline-none min-h-[48px] leading-relaxed"
                placeholder="Describe your shot..."
              />
            </div>

            {/* Prompt Actions */}
            <div className="flex items-center justify-between px-2 pb-1 pt-2 border-t border-white/5">
              <div className="flex items-center gap-2">
                <button className="p-1.5 hover:bg-white/10 rounded-md text-zinc-400 hover:text-zinc-200 transition-colors">
                  <ImageIcon size={16} />
                </button>
                <button className="p-1.5 hover:bg-white/10 rounded-md text-zinc-400 hover:text-zinc-200 transition-colors">
                  <Paperclip size={16} />
                </button>
                <div className="h-4 w-px bg-white/10 mx-1"></div>
                <button className="text-[10px] font-medium text-purple-400 hover:text-purple-300 transition-colors">
                  + Enhance Prompt
                </button>
              </div>
              <button className="bg-white text-black px-4 py-1.5 rounded-lg text-xs font-bold hover:bg-zinc-200 transition-colors flex items-center gap-2 shadow-[0_0_15px_rgba(255,255,255,0.2)]">
                Generate <span className="opacity-50 text-[10px]">⌘G</span>
              </button>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}

// --- SUB-COMPONENTS for Cleanliness ---

const TabButton = ({ active, onClick, label }: { active: boolean, onClick: () => void, label: string }) => (
  <button
    onClick={onClick}
    className={`px-3 py-1 text-[11px] font-medium rounded-md transition-all duration-200 ${active
        ? 'bg-zinc-800 text-white shadow-sm'
        : 'text-zinc-500 hover:text-zinc-300 hover:bg-white/5'
      }`}
  >
    {label}
  </button>
);

const Label = ({ children }: { children: React.ReactNode }) => (
  <h4 className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest mb-2">{children}</h4>
);

const ToggleRow = ({ label, active }: { label: string, active?: boolean }) => (
  <div className="flex items-center justify-between group cursor-pointer">
    <span className={`text-xs ${active ? 'text-zinc-300' : 'text-zinc-500 group-hover:text-zinc-400'}`}>{label}</span>
    <div className={`w-8 h-4 rounded-full relative transition-colors ${active ? 'bg-purple-600' : 'bg-zinc-800'}`}>
      <div className={`absolute top-0.5 w-3 h-3 bg-white rounded-full shadow-sm transition-all ${active ? 'left-4.5' : 'left-0.5'}`}></div>
    </div>
  </div>
);

const ControlIcon = ({ icon }: { icon: React.ReactNode }) => (
  <button className="text-white hover:text-purple-400 transition-colors">
    {icon}
  </button>
);

const ControlGroup = ({ label, children }: { label: string, children: React.ReactNode }) => (
  <div>
    <div className="text-[10px] text-zinc-500 font-mono mb-2 uppercase">{label}</div>
    {children}
  </div>
);

const AspectRatioBtn = ({ label, active }: { label: string, active?: boolean }) => (
  <button className={`text-[10px] py-1.5 rounded border ${active
      ? 'bg-zinc-100 text-black border-zinc-100 font-bold'
      : 'bg-transparent text-zinc-500 border-white/10 hover:border-white/30'
    }`}>
    {label}
  </button>
);

const TimeTool = ({ icon, label }: { icon: React.ReactNode, label?: string }) => (
  <button className="flex items-center gap-1.5 text-zinc-500 hover:text-zinc-300 transition-colors px-2 py-1 rounded hover:bg-white/5">
    {icon}
    {label && <span className="text-[10px] font-medium">{label}</span>}
  </button>
);