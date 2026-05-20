"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Box, Lock, Mail, ArrowRight, Shield, RefreshCw } from "lucide-react";
import { getLocalSession, saveLocalSession } from "@/utils/supabase";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setErrorMessage("");

    try {
      // 1. 보안 체크 및 인위적 딜레이로 실전 B2B SaaS 감성 탑재
      await new Promise((resolve) => setTimeout(resolve, 1200));

      if (!email.includes("@")) {
        setErrorMessage("유효한 회사 이메일 형식을 입력해 주십시오.");
        setIsLoading(false);
        return;
      }
      if (password.length < 4) {
        setErrorMessage("비밀번호는 최소 4자리 이상이어야 합니다.");
        setIsLoading(false);
        return;
      }

      // 2. 가상 B2B 세션 구성 (Supabase DB 연동 서킷 브레이커)
      const mockSession = {
        email: email,
        tenant_id: "tenant_" + Math.random().toString(36).substring(2, 9),
        company_name: email.split("@")[0].toUpperCase() + " 주식회사 (일본지사)",
        subscription_tier: "ENTERPRISE" as const,
        credits: 400
      };

      // 세션 저장 및 대시보드 리다이렉트
      saveLocalSession(mockSession);
      router.push("/dashboard");
    } catch (err) {
      setErrorMessage("서버 응답 오류가 발생했습니다. 잠시 후 다시 시도해 주십시오.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-neutral-950 text-white flex flex-col justify-center items-center relative overflow-hidden font-sans">
      {/* 백그라운드 광채 그라데이션 (Vibrant Blue & Purple Glow) */}
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[500px] h-[500px] bg-gradient-to-tr from-blue-600/20 to-purple-600/20 rounded-full blur-[120px] pointer-events-none z-0"></div>

      {/* 로그인 메인 컨테이너 */}
      <div className="w-full max-w-md p-8 bg-neutral-900/60 backdrop-blur-2xl border border-neutral-800 rounded-3xl shadow-2xl z-10 animate-in fade-in slide-in-from-bottom-8 duration-700">
        
        {/* 상단 로고 & 브랜딩 */}
        <div className="flex flex-col items-center mb-8">
          <div className="p-4 bg-gradient-to-tr from-blue-600 to-purple-600 rounded-2xl shadow-xl shadow-blue-500/10 mb-4 animate-pulse">
            <Box className="w-8 h-8 text-white" />
          </div>
          <h1 className="text-2xl font-bold tracking-wider bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent">
            Japanbuild BIM3D SaaS
          </h1>
          <p className="text-xs text-neutral-400 mt-1">일본 국토교통성(MLIT) 규격 적합성 인공지능 자가진단</p>
        </div>

        {errorMessage && (
          <div className="mb-6 p-4 bg-red-500/10 border border-red-500/20 rounded-xl flex items-center gap-3 text-red-400 text-xs animate-shake">
            <Shield className="w-4 h-4 flex-shrink-0" />
            <span>{errorMessage}</span>
          </div>
        )}

        {/* 로그인 폼 */}
        <form onSubmit={handleLogin} className="space-y-5">
          <div>
            <label className="block text-xs font-semibold text-neutral-400 tracking-wider mb-2 uppercase">회사 이메일 계정</label>
            <div className="relative">
              <span className="absolute inset-y-0 left-0 pl-3.5 flex items-center text-neutral-500">
                <Mail className="w-4 h-4" />
              </span>
              <input
                type="email"
                required
                placeholder="example@gilppon-const.co.jp"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full pl-11 pr-4 py-3 bg-neutral-950 border border-neutral-800 hover:border-neutral-700 focus:border-blue-500 rounded-xl text-sm focus:outline-none transition-all placeholder-neutral-600 text-neutral-200"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-neutral-400 tracking-wider mb-2 uppercase">비밀번호</label>
            <div className="relative">
              <span className="absolute inset-y-0 left-0 pl-3.5 flex items-center text-neutral-500">
                <Lock className="w-4 h-4" />
              </span>
              <input
                type="password"
                required
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full pl-11 pr-4 py-3 bg-neutral-950 border border-neutral-800 hover:border-neutral-700 focus:border-blue-500 rounded-xl text-sm focus:outline-none transition-all placeholder-neutral-600 text-neutral-200"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={isLoading}
            className="w-full mt-6 py-3.5 bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-500 hover:to-purple-500 disabled:from-neutral-800 disabled:to-neutral-800 disabled:text-neutral-500 font-semibold text-sm rounded-xl shadow-lg hover:shadow-blue-500/20 transition-all duration-300 flex justify-center items-center gap-2 cursor-pointer"
          >
            {isLoading ? (
              <RefreshCw className="w-4 h-4 animate-spin" />
            ) : (
              <>
                <span>B2B 안전 로그인</span>
                <ArrowRight className="w-4 h-4" />
              </>
            )}
          </button>
        </form>

        {/* 하단 푸터 링크 */}
        <div className="mt-8 pt-6 border-t border-neutral-800 flex justify-between items-center text-xs text-neutral-400">
          <span>아직 계정이 없으십니까?</span>
          <Link href="/signup" className="text-blue-400 hover:text-blue-300 font-bold transition-colors">
            무료 B2B 회원가입
          </Link>
        </div>
      </div>

      <div className="mt-8 text-neutral-600 text-[10px] tracking-widest uppercase">
        © 2026 KODARI CAD DEVELOPMENT DIVISION. ALL RIGHTS RESERVED.
      </div>
    </div>
  );
}
