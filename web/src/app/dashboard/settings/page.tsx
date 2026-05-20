"use client";

import { useState, useEffect } from "react";
import { Users, UserPlus, Key, Building, Shield, Clipboard, Check } from "lucide-react";
import { getLocalSession, UserSession } from "@/utils/supabase";

export default function SettingsPage() {
  const [session, setSession] = useState<UserSession | null>(null);
  const [inviteCode, setInviteCode] = useState("KODARI-BIM-9982-GLPN");
  const [copied, setCopied] = useState(false);
  const [newEmail, setNewEmail] = useState("");
  const [teamMembers, setTeamMembers] = useState([
    { email: "representative@gilppon-const.co.jp", role: "WORKSPACE OWNER (대표자)", status: "ACTIVE" },
    { email: "inspector_osaka@gilppon-const.co.jp", role: "FIELD INSPECTOR (현장 감리원)", status: "ACTIVE" },
    { email: "subcontractor_tokyo@partner.jp", role: "EXTERNAL CONSULTANT (협력사 자문위원)", status: "PENDING" }
  ]);

  useEffect(() => {
    const active = getLocalSession();
    setSession(active);
    if (active) {
      setTeamMembers(prev => [
        { email: active.email, role: "WORKSPACE OWNER (대표자)", status: "ACTIVE" },
        ...prev.filter(m => m.email !== active.email)
      ]);
    }
  }, []);

  const handleCopyCode = () => {
    navigator.clipboard.writeText(inviteCode);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleInvite = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newEmail.includes("@")) {
      alert("올바른 이메일 형식을 입력해 주십시오.");
      return;
    }

    setTeamMembers([...teamMembers, {
      email: newEmail,
      role: "FIELD INSPECTOR (현장 감리원)",
      status: "PENDING"
    }]);
    alert(`🎉 ${newEmail} 계정으로 워크스페이스 초대장을 발송했습니다!`);
    setNewEmail("");
  };

  if (!session) return <div className="text-neutral-400 text-sm">로딩 중...</div>;

  return (
    <div className="max-w-4xl mx-auto space-y-8 animate-in fade-in duration-500">
      
      {/* 1. 기업 프로필 요약 카드 */}
      <div className="bg-neutral-900 border border-neutral-800 rounded-3xl p-6 relative overflow-hidden">
        <div className="absolute inset-y-0 right-0 w-1/3 bg-gradient-to-l from-blue-500/5 to-transparent pointer-events-none"></div>
        
        <h3 className="text-sm font-bold text-neutral-400 tracking-widest uppercase mb-4 flex items-center gap-2">
          <Building className="w-4 h-4 text-blue-400" />
          <span>B2B 기업 테넌트 정보</span>
        </h3>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="space-y-1">
            <span className="text-[10px] font-bold text-neutral-500 uppercase tracking-wider block">소속 회사명</span>
            <span className="text-lg font-bold text-white block">{session.company_name}</span>
          </div>
          <div className="space-y-1">
            <span className="text-[10px] font-bold text-neutral-500 uppercase tracking-wider block">고유 테넌트 ID (Supabase RLS 격리 키)</span>
            <code className="text-xs px-2.5 py-1 bg-neutral-950 border border-neutral-800 rounded-lg text-blue-400 font-mono block w-fit">{session.tenant_id}</code>
          </div>
          <div className="space-y-1">
            <span className="text-[10px] font-bold text-neutral-500 uppercase tracking-wider block">계정 등급 및 크레딧</span>
            <span className="text-sm font-semibold text-neutral-200 block">
              BIM {session.subscription_tier} Plam ({session.credits} Credits 보유)
            </span>
          </div>
          <div className="space-y-1">
            <span className="text-[10px] font-bold text-neutral-500 uppercase tracking-wider block">데이터 주권 지역 (Region)</span>
            <span className="text-xs text-neutral-400 flex items-center gap-1.5 mt-0.5">
              <Shield className="w-3.5 h-3.5 text-emerald-400" />
              <span>AWS Tokyo (ap-northeast-1) - 일본 법령 APPI 완벽 규격 준수</span>
            </span>
          </div>
        </div>
      </div>

      {/* 2. 동료 협업 관리 (Workspace Members) */}
      <div className="bg-neutral-900 border border-neutral-800 rounded-3xl p-6">
        <h3 className="text-sm font-bold text-neutral-400 tracking-widest uppercase mb-6 flex items-center gap-2">
          <Users className="w-4 h-4 text-purple-400" />
          <span>워크스페이스 멤버십 관리 ({teamMembers.length}인 활성)</span>
        </h3>

        {/* 초대 코드 영역 */}
        <div className="p-4 bg-neutral-950 border border-neutral-800 rounded-2xl flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-6">
          <div className="flex items-center gap-3">
            <div className="p-2.5 bg-purple-500/10 rounded-xl text-purple-400">
              <Key className="w-5 h-5" />
            </div>
            <div>
              <span className="text-[10px] font-semibold text-neutral-500 block">공용 워크스페이스 초대 코드</span>
              <span className="text-sm font-mono font-bold text-white tracking-wide">{inviteCode}</span>
            </div>
          </div>
          <button
            onClick={handleCopyCode}
            className="flex items-center gap-1.5 px-4 py-2 bg-neutral-900 hover:bg-neutral-800 border border-neutral-800 rounded-xl text-xs font-semibold text-neutral-300 transition-colors cursor-pointer"
          >
            {copied ? (
              <>
                <Check className="w-3.5 h-3.5 text-emerald-400" />
                <span className="text-emerald-400">복사 완료</span>
              </>
            ) : (
              <>
                <Clipboard className="w-3.5 h-3.5" />
                <span>코드 복사</span>
              </>
            )}
          </button>
        </div>

        {/* 개별 이메일 직접 초대 */}
        <form onSubmit={handleInvite} className="flex gap-3 mb-8">
          <input
            type="email"
            required
            placeholder="동료의 회사 이메일 입력"
            value={newEmail}
            onChange={(e) => setNewEmail(e.target.value)}
            className="flex-1 px-4 py-3 bg-neutral-950 border border-neutral-800 hover:border-neutral-700 focus:border-purple-500 rounded-xl text-xs focus:outline-none transition-all placeholder-neutral-700 text-neutral-200"
          />
          <button
            type="submit"
            className="px-5 py-3 bg-purple-600 hover:bg-purple-500 text-white font-bold text-xs rounded-xl shadow-lg hover:shadow-purple-500/20 flex items-center gap-1.5 cursor-pointer transition-colors"
          >
            <UserPlus className="w-4 h-4" />
            <span>멤버 초대</span>
          </button>
        </form>

        {/* 현재 멤버 리스트 */}
        <div className="space-y-3">
          <span className="text-[10px] font-bold text-neutral-500 uppercase tracking-widest block mb-2.5">워크스페이스 활성 멤버 리스트</span>
          
          {teamMembers.map((m, idx) => (
            <div key={idx} className="p-3.5 bg-neutral-950 border border-neutral-800/60 rounded-xl flex justify-between items-center text-xs">
              <div className="space-y-1">
                <span className="font-semibold text-neutral-200 block">{m.email}</span>
                <span className="text-[10px] text-neutral-500 block uppercase font-bold">{m.role}</span>
              </div>
              <span className={`px-2 py-0.5 rounded text-[9px] font-extrabold tracking-wider ${m.status === "ACTIVE" ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20" : "bg-orange-500/10 text-orange-400 border border-orange-500/20 animate-pulse"}`}>
                {m.status}
              </span>
            </div>
          ))}
        </div>

      </div>

    </div>
  );
}
