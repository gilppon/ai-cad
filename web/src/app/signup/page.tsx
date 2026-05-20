"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Box, Lock, Mail, Building, ArrowRight, ShieldCheck, RefreshCw } from "lucide-react";
import { saveLocalSession } from "@/utils/supabase";

export default function SignupPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  const handleSignup = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setErrorMessage("");

    try {
      // 1. 가상 딜레이
      await new Promise((resolve) => setTimeout(resolve, 1500));

      if (!email.includes("@")) {
        setErrorMessage("유효한 회사 이메일 형식을 입력해 주십시오.");
        setIsLoading(false);
        return;
      }
      if (password.length < 6) {
        setErrorMessage("보안상 비밀번호는 최소 6자리 이상 설정하셔야 합니다.");
        setIsLoading(false);
        return;
      }
      if (companyName.trim().length < 2) {
        setErrorMessage("올바른 회사명 또는 지사명을 입력해 주십시오.");
        setIsLoading(false);
        return;
      }

      // 2. 가상 B2B 테넌트 세션 생성 (Supabase 격리 프로토콜 자동 탑재)
      const newTenantId = "tenant_" + Math.random().toString(36).substring(2, 9);
      const newSession = {
        email: email,
        tenant_id: newTenantId,
        company_name: companyName,
        subscription_tier: "LIGHT" as const, // 기본적으로 라이트 플랜부터 출발
        credits: 10 // 가입 보너스로 10 크레딧 제공!
      };

      saveLocalSession(newSession);
      alert(`🎉 B2B 테넌트가 개설되었습니다!\n\n회사명: ${companyName}\n고유 테넌트 ID: ${newTenantId}\n\n대시보드로 이동합니다!`);
      router.push("/dashboard");
    } catch (err) {
      setErrorMessage("서버 개설 실패. 서비스 상태를 점검해 주십시오.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-neutral-950 text-white flex flex-col justify-center items-center relative overflow-hidden font-sans">
      {/* 백그라운드 광채 그라데이션 */}
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[550px] h-[550px] bg-gradient-to-tr from-purple-600/20 to-blue-600/20 rounded-full blur-[130px] pointer-events-none z-0"></div>

      {/* 가입 메인 컨테이너 */}
      <div className="w-full max-w-md p-8 bg-neutral-900/60 backdrop-blur-2xl border border-neutral-800 rounded-3xl shadow-2xl z-10 animate-in fade-in slide-in-from-bottom-8 duration-700">
        
        {/* 상단 타이틀 */}
        <div className="flex flex-col items-center mb-8">
          <div className="p-4 bg-gradient-to-tr from-purple-600 to-blue-600 rounded-2xl shadow-xl shadow-purple-500/10 mb-4 animate-pulse">
            <Box className="w-8 h-8 text-white" />
          </div>
          <h1 className="text-2xl font-bold tracking-wider bg-gradient-to-r from-purple-400 to-blue-400 bg-clip-text text-transparent">
            B2B 테넌트 무료 개설
          </h1>
          <p className="text-xs text-neutral-400 mt-1">일본 B2B 건축 현업을 위한 3D BIM 클라우드</p>
        </div>

        {errorMessage && (
          <div className="mb-6 p-4 bg-red-500/10 border border-red-500/20 rounded-xl flex items-center gap-3 text-red-400 text-xs animate-shake">
            <ShieldCheck className="w-4 h-4 text-red-500 flex-shrink-0" />
            <span>{errorMessage}</span>
          </div>
        )}

        {/* 회원가입 폼 */}
        <form onSubmit={handleSignup} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-neutral-400 tracking-wider mb-2 uppercase">회사 및 단체명</label>
            <div className="relative">
              <span className="absolute inset-y-0 left-0 pl-3.5 flex items-center text-neutral-500">
                <Building className="w-4 h-4" />
              </span>
              <input
                type="text"
                required
                placeholder="ギルポン建設株式会社 (길폰 건설 주식회사)"
                value={companyName}
                onChange={(e) => setCompanyName(e.target.value)}
                className="w-full pl-11 pr-4 py-3 bg-neutral-950 border border-neutral-800 hover:border-neutral-700 focus:border-purple-500 rounded-xl text-sm focus:outline-none transition-all placeholder-neutral-600 text-neutral-200"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-neutral-400 tracking-wider mb-2 uppercase">회사 이메일 계정</label>
            <div className="relative">
              <span className="absolute inset-y-0 left-0 pl-3.5 flex items-center text-neutral-500">
                <Mail className="w-4 h-4" />
              </span>
              <input
                type="email"
                required
                placeholder="representative@company.co.jp"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full pl-11 pr-4 py-3 bg-neutral-950 border border-neutral-800 hover:border-neutral-700 focus:border-purple-500 rounded-xl text-sm focus:outline-none transition-all placeholder-neutral-600 text-neutral-200"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-neutral-400 tracking-wider mb-2 uppercase">비밀번호 설정</label>
            <div className="relative">
              <span className="absolute inset-y-0 left-0 pl-3.5 flex items-center text-neutral-500">
                <Lock className="w-4 h-4" />
              </span>
              <input
                type="password"
                required
                placeholder="비밀번호 6자리 이상"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full pl-11 pr-4 py-3 bg-neutral-950 border border-neutral-800 hover:border-neutral-700 focus:border-purple-500 rounded-xl text-sm focus:outline-none transition-all placeholder-neutral-600 text-neutral-200"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={isLoading}
            className="w-full mt-6 py-3.5 bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-500 hover:to-blue-500 disabled:from-neutral-800 disabled:to-neutral-800 disabled:text-neutral-500 font-semibold text-sm rounded-xl shadow-lg hover:shadow-purple-500/20 transition-all duration-300 flex justify-center items-center gap-2 cursor-pointer"
          >
            {isLoading ? (
              <RefreshCw className="w-4 h-4 animate-spin" />
            ) : (
              <>
                <span>B2B 계정 및 격리 공간 생성</span>
                <ArrowRight className="w-4 h-4" />
              </>
            )}
          </button>
        </form>

        {/* 하단 로그인 이동 */}
        <div className="mt-8 pt-6 border-t border-neutral-800 flex justify-between items-center text-xs text-neutral-400">
          <span>이미 계정이 있으십니까?</span>
          <Link href="/login" className="text-purple-400 hover:text-purple-300 font-bold transition-colors">
            기존 계정으로 로그인
          </Link>
        </div>
      </div>

      <div className="mt-8 text-neutral-600 text-[10px] tracking-widest uppercase">
        © 2026 KODARI CAD DEVELOPMENT DIVISION. ALL RIGHTS RESERVED.
      </div>
    </div>
  );
}
