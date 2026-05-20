"use client";

import Link from "next/link";
import { LayoutDashboard, FileUp, Settings, HelpCircle, Box } from "lucide-react";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex h-screen w-full bg-neutral-950 text-neutral-50 overflow-hidden">
      {/* LNB (Sidebar) */}
      <aside className="w-64 border-r border-neutral-800 bg-neutral-900/50 flex flex-col backdrop-blur-xl">
        <div className="h-16 flex items-center px-6 border-b border-neutral-800">
          <Box className="w-6 h-6 text-blue-500 mr-3" />
          <span className="font-bold text-lg tracking-wide">Kodari CAD</span>
        </div>
        
        <div className="flex-1 px-4 py-6 space-y-2">
          <div className="text-xs font-medium text-neutral-500 mb-4 px-2">MAIN MENU</div>
          <Link href="/dashboard" className="flex items-center px-3 py-2.5 rounded-lg bg-blue-500/10 text-blue-400 font-medium transition-colors hover:bg-blue-500/20">
            <LayoutDashboard className="w-5 h-5 mr-3" />
            Dashboard
          </Link>
          <Link 
            href="/dashboard" 
            onClick={(e) => {
              e.preventDefault();
              alert("🇯🇵 [업로드 가이드]\n도면 업로드는 대시보드 중앙의 'Drag & Drop architectural PDF' 영역 또는 'Browse Files' 버튼을 이용해 주십시오!");
            }}
            className="flex items-center px-3 py-2.5 rounded-lg text-neutral-400 font-medium transition-colors hover:bg-neutral-800 hover:text-neutral-50"
          >
            <FileUp className="w-5 h-5 mr-3" />
            Upload PDF
          </Link>
        </div>

        <div className="px-4 py-6 border-t border-neutral-800 space-y-2">
          <Link 
            href="/dashboard" 
            onClick={(e) => {
              e.preventDefault();
              alert("🔒 [기능 제한]\nSettings 메뉴는 상용 라이브 런칭(Enterprise Tier) 이후 활성화되는 본사 전용 관리 도구입니다.");
            }}
            className="flex items-center px-3 py-2.5 rounded-lg text-neutral-400 font-medium transition-colors hover:bg-neutral-800 hover:text-neutral-50"
          >
            <Settings className="w-5 h-5 mr-3" />
            Settings
          </Link>
          <Link 
            href="/dashboard" 
            onClick={(e) => {
              e.preventDefault();
              alert("ℹ️ [고객 지원]\nHelp & Support 채널은 상용 런칭 SOP 구축 이후 활성화될 예정입니다. 기술 문의는 코다리 개발본부로 직접 연락주십시오!");
            }}
            className="flex items-center px-3 py-2.5 rounded-lg text-neutral-400 font-medium transition-colors hover:bg-neutral-800 hover:text-neutral-50"
          >
            <HelpCircle className="w-5 h-5 mr-3" />
            Help & Support
          </Link>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col relative overflow-hidden">
        {/* Header / GNB */}
        <header className="h-16 flex items-center justify-between px-8 border-b border-neutral-800 bg-neutral-950/80 backdrop-blur-sm z-10">
          <h1 className="text-xl font-semibold text-neutral-100">Overview</h1>
          <div className="flex items-center space-x-4">
            <div className="flex items-center px-3 py-1.5 rounded-full border border-blue-500/30 bg-blue-500/10 text-sm font-medium text-blue-400">
              <span className="w-2 h-2 rounded-full bg-blue-500 mr-2 animate-pulse"></span>
              400 Credits
            </div>
            <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-blue-600 to-purple-600 flex items-center justify-center text-sm font-bold shadow-lg ring-2 ring-neutral-900">
              A
            </div>
          </div>
        </header>
        
        {/* Page Content */}
        <div className="flex-1 overflow-y-auto p-8">
          {children}
        </div>
      </main>
    </div>
  );
}
