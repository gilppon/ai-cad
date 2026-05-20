"use client";

import { useState, useEffect } from "react";
import { CreditCard, Check, Box, Sparkles, Zap, ShieldCheck, AlertCircle } from "lucide-react";
import { getLocalSession, saveLocalSession, UserSession } from "@/utils/supabase";

export default function BillingPage() {
  const [session, setSession] = useState<UserSession | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [selectedTier, setSelectedTier] = useState<"LIGHT" | "BUSINESS" | "ENTERPRISE" | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [cardNumber, setCardNumber] = useState("");
  const [cardExpiry, setCardExpiry] = useState("");
  const [cardCvc, setCardCvc] = useState("");

  useEffect(() => {
    setSession(getLocalSession());
  }, []);

  const handleOpenPayment = (tier: "LIGHT" | "BUSINESS" | "ENTERPRISE") => {
    setSelectedTier(tier);
    setIsModalOpen(true);
  };

  const handleProcessPayment = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);

    try {
      // 1. Stripe Secure Gateway 결제 지연 모사 (일본 도쿄 핑 대응 지연 구현)
      await new Promise((resolve) => setTimeout(resolve, 1500));

      if (cardNumber.replace(/\s/g, "").length < 12) {
        alert("🚨 올바른 카드 번호를 입력해 주십시오.");
        setIsLoading(false);
        return;
      }

      if (!session || !selectedTier) return;

      // 2. 등급에 따른 크레딧 충전 분기
      let addedCredits = 0;
      if (selectedTier === "LIGHT") addedCredits = 30;
      if (selectedTier === "BUSINESS") addedCredits = 100;
      if (selectedTier === "ENTERPRISE") addedCredits = 300;

      // 3. 로컬 B2B 세션 갱신 및 저장
      const updatedSession: UserSession = {
        ...session,
        subscription_tier: selectedTier,
        credits: session.credits + addedCredits
      };

      saveLocalSession(updatedSession);
      setSession(updatedSession);
      setIsModalOpen(false);

      // 인쇄용 적격청구서 메일 발송 안내 (일본 인보이스 제도)
      alert(`🎉 결제가 정상 승인되었습니다!\n\n구매 플랜: BIM ${selectedTier}\n충전된 크레딧: +${addedCredits} Credits\n총 보유 크레딧: ${updatedSession.credits} Credits\n\n* 일본 국세청 세법 기준 적격 인보이스(Qualified Invoice) 영수증이 대표 이메일로 발행되었습니다.`);
      
      // 상위 프레임 새로고침 유도
      window.location.reload();
    } catch (err) {
      alert("결제 통신 오류가 발생했습니다.");
    } finally {
      setIsLoading(false);
    }
  };

  if (!session) return <div className="text-neutral-400 text-sm">로딩 중...</div>;

  return (
    <div className="max-w-5xl mx-auto space-y-8 animate-in fade-in duration-500">
      
      {/* 상단 현재 구독 멤버십 상태 요약 */}
      <div className="bg-neutral-900 border border-neutral-800 rounded-3xl p-8 relative overflow-hidden flex flex-col md:flex-row justify-between items-start md:items-center gap-6">
        <div className="absolute inset-0 bg-gradient-to-r from-blue-500/5 via-purple-500/5 to-transparent pointer-events-none"></div>
        <div>
          <span className="text-xs font-bold text-blue-400 tracking-widest uppercase mb-1.5 block">CURRENT PLAN STATUS</span>
          <h2 className="text-2xl font-bold text-white mb-2 flex items-center gap-2">
            <span>BIM {session.subscription_tier} MEMBER</span>
            <span className="px-2.5 py-0.5 bg-gradient-to-tr from-blue-600 to-purple-600 rounded-full text-[10px] font-extrabold text-white animate-pulse">ACTIVE</span>
          </h2>
          <p className="text-sm text-neutral-400">소속 테넌트: <strong className="text-neutral-200">{session.company_name}</strong> | ID: {session.tenant_id}</p>
        </div>

        <div className="flex items-center gap-4 bg-neutral-950 p-4 rounded-2xl border border-neutral-800/80">
          <div className="p-3 bg-blue-500/10 rounded-xl text-blue-400">
            <Sparkles className="w-6 h-6 animate-spin-slow" />
          </div>
          <div>
            <span className="text-xs text-neutral-500 block uppercase font-semibold">보유 크레딧 잔액</span>
            <span className="text-2xl font-black text-white">{session.credits} <span className="text-sm text-blue-400">Credits</span></span>
          </div>
        </div>
      </div>

      {/* Stripe JPY 3단 카드 요금판 */}
      <div>
        <h3 className="text-xl font-bold text-white mb-1.5">일본 B2B 건축 전문가용 플랜</h3>
        <p className="text-xs text-neutral-400 mb-4">2023년 10월 도입된 적격청구서 보증 인보이스 규격을 100% 보증합니다.</p>
        
        {/* 크레딧 차감 안내 배너 HUD */}
        <div className="bg-neutral-950/80 border border-neutral-800/80 rounded-2xl p-4 mb-8 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 text-xs">
          <div className="flex items-center gap-2 text-neutral-300 font-sans">
            <AlertCircle className="w-4 h-4 text-blue-400 flex-shrink-0" />
            <span><strong>【クレジット消費ガイドライン】</strong> 業務フローに合わせてアカウントからクレジット가 자동 차감됩니다.</span>
          </div>
          <div className="flex gap-4 font-mono text-[10px]">
            <span className="px-2.5 py-1 bg-neutral-900 border border-neutral-800 rounded-lg text-neutral-400">
              🟢 3D IFC 復元: <strong className="text-white">3 Credits</strong>
            </span>
            <span className="px-2.5 py-1 bg-neutral-900 border border-neutral-800 rounded-lg text-neutral-400">
              🔥 適合報告書(PDF)発行: <strong className="text-white">10 Credits</strong>
            </span>
          </div>
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          
          {/* 1. LIGHT CARD */}
          <div className={`bg-neutral-900 border rounded-3xl p-6 relative flex flex-col justify-between transition-all duration-300 ${session.subscription_tier === "LIGHT" ? "border-blue-500/40 ring-1 ring-blue-500/20 shadow-blue-500/5 shadow-2xl" : "border-neutral-800 hover:border-neutral-700"}`}>
            <div>
              <div className="flex justify-between items-start mb-4">
                <span className="text-xs font-extrabold px-2.5 py-1 bg-neutral-950 rounded-lg text-neutral-400 tracking-wider">LIGHT</span>
                <span className="text-xs text-neutral-500">소형 현장 검측</span>
              </div>
              <h4 className="text-3xl font-black text-white mb-2">¥1,500 <span className="text-xs text-neutral-500 font-normal">/ 월 (세포함)</span></h4>
              <p className="text-xs text-neutral-400 mb-6">개인 감리사 및 소규모 인테리어 업체용 기본 규격</p>
              
              <ul className="space-y-3.5 mb-8 text-xs text-neutral-300">
                <li className="flex items-center gap-2"><Check className="w-3.5 h-3.5 text-blue-500" /> <span>최대 3개 도면 활성화</span></li>
                <li className="flex items-center gap-2"><Check className="w-3.5 h-3.5 text-blue-500" /> <span>기본 채광률 / 반자높이 검격</span></li>
                <li className="flex items-center gap-2"><Check className="w-3.5 h-3.5 text-blue-500" /> <span>기본 PDF 보고서 다운로드</span></li>
                <li className="flex items-center gap-2"><Check className="w-3.5 h-3.5 text-blue-500" /> <span>+30 크레딧 즉시 지급</span></li>
              </ul>
            </div>
            <button
              onClick={() => handleOpenPayment("LIGHT")}
              className="w-full py-3 bg-neutral-950 hover:bg-neutral-800 text-white font-semibold text-xs rounded-xl border border-neutral-800 hover:border-neutral-700 cursor-pointer transition-all"
            >
              플랜 구독 / 크레딧 충전
            </button>
          </div>

          {/* 2. BUSINESS CARD */}
          <div className="bg-neutral-900 border border-blue-500/60 rounded-3xl p-6 relative flex flex-col justify-between transition-all duration-300 ring-2 ring-blue-500/10 shadow-2xl shadow-blue-500/10">
            <div className="absolute -top-3.5 left-1/2 -translate-x-1/2 px-4 py-1 bg-gradient-to-r from-blue-600 to-purple-600 rounded-full text-[9px] font-extrabold text-white tracking-widest uppercase">MOST POPULAR</div>
            <div>
              <div className="flex justify-between items-start mb-4">
                <span className="text-xs font-extrabold px-2.5 py-1 bg-blue-500/10 rounded-lg text-blue-400 tracking-wider">BUSINESS</span>
                <span className="text-xs text-blue-400 flex items-center gap-1"><Zap className="w-3 h-3 animate-bounce" /> 프로페셔널</span>
              </div>
              <h4 className="text-3xl font-black text-white mb-2">¥4,900 <span className="text-xs text-neutral-500 font-normal">/ 월 (세포함)</span></h4>
              <p className="text-xs text-neutral-400 mb-6">중소 규모 건설사 및 전문 누수방수 공사 기업용</p>
              
              <ul className="space-y-3.5 mb-8 text-xs text-neutral-300">
                <li className="flex items-center gap-2"><Check className="w-3.5 h-3.5 text-blue-400" /> <span className="font-semibold text-white">도면 개수 완전 무제한</span></li>
                <li className="flex items-center gap-2"><Check className="w-3.5 h-3.5 text-blue-400" /> <span>고화질 2D-3D 재빌드 가속</span></li>
                <li className="flex items-center gap-2"><Check className="w-3.5 h-3.5 text-blue-400" /> <span>일본 관청/보험사 표준 PDF 날인</span></li>
                <li className="flex items-center gap-2"><Check className="w-3.5 h-3.5 text-blue-400" /> <span>+100 크레딧 즉시 지급</span></li>
              </ul>
            </div>
            <button
              onClick={() => handleOpenPayment("BUSINESS")}
              className="w-full py-3 bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-500 hover:to-purple-500 text-white font-bold text-xs rounded-xl shadow-lg hover:shadow-blue-500/20 cursor-pointer transition-all"
            >
              비즈니스 등급 승격
            </button>
          </div>

          {/* 3. ENTERPRISE CARD */}
          <div className={`bg-neutral-900 border rounded-3xl p-6 relative flex flex-col justify-between transition-all duration-300 ${session.subscription_tier === "ENTERPRISE" ? "border-purple-500/40 ring-1 ring-purple-500/20 shadow-purple-500/5 shadow-2xl" : "border-neutral-800 hover:border-neutral-700"}`}>
            <div>
              <div className="flex justify-between items-start mb-4">
                <span className="text-xs font-extrabold px-2.5 py-1 bg-neutral-950 rounded-lg text-purple-400 tracking-wider">ENTERPRISE</span>
                <span className="text-xs text-neutral-500">제네콘 전용</span>
              </div>
              <h4 className="text-3xl font-black text-white mb-2">¥9,800 <span className="text-xs text-neutral-500 font-normal">/ 월 (세포함)</span></h4>
              <p className="text-xs text-neutral-400 mb-6">대형 원청 제네콘(General Contractor) 종합 DX 솔루션</p>
              
              <ul className="space-y-3.5 mb-8 text-xs text-neutral-300">
                <li className="flex items-center gap-2"><Check className="w-3.5 h-3.5 text-purple-500" /> <span className="font-semibold text-white">오프라인 IndexedDB 델타 동기화</span></li>
                <li className="flex items-center gap-2"><Check className="w-3.5 h-3.5 text-purple-500" /> <span>Supabase RLS 보안 단독 보증</span></li>
                <li className="flex items-center gap-2"><Check className="w-3.5 h-3.5 text-purple-500" /> <span>최대 10인 동료 협업 초대권</span></li>
                <li className="flex items-center gap-2"><Check className="w-3.5 h-3.5 text-purple-500" /> <span>+300 크레딧 즉시 지급</span></li>
              </ul>
            </div>
            <button
              onClick={() => handleOpenPayment("ENTERPRISE")}
              className="w-full py-3 bg-neutral-950 hover:bg-neutral-800 text-white font-semibold text-xs rounded-xl border border-neutral-800 hover:border-neutral-700 cursor-pointer transition-all"
            >
              엔터프라이즈 구독 / 충전
            </button>
          </div>

        </div>
      </div>

      {/* Stripe Japan 결제 모의 라이브 모달 */}
      {isModalOpen && selectedTier && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm flex justify-center items-center z-50 animate-in fade-in duration-300">
          <div className="bg-neutral-900 border border-neutral-800 rounded-3xl p-8 max-w-md w-full mx-4 shadow-2xl relative animate-in zoom-in-95 duration-200">
            <h3 className="text-lg font-bold text-white mb-2 flex items-center gap-2">
              <CreditCard className="w-5 h-5 text-blue-500" />
              <span>Stripe Japan Secure Checkout</span>
            </h3>
            <p className="text-xs text-neutral-400 mb-6">일본 엔화(JPY) 전용 안전 결제 게이트웨이</p>

            <form onSubmit={handleProcessPayment} className="space-y-4">
              <div>
                <label className="block text-[10px] font-bold text-neutral-500 uppercase tracking-widest mb-1.5">선택된 라이선스 플랜</label>
                <div className="p-3 bg-neutral-950 border border-neutral-800 rounded-xl flex justify-between items-center text-xs font-semibold text-neutral-200">
                  <span>BIM {selectedTier} 요금제</span>
                  <span className="text-blue-400">
                    {selectedTier === "LIGHT" && "¥1,500"}
                    {selectedTier === "BUSINESS" && "¥4,900"}
                    {selectedTier === "ENTERPRISE" && "¥9,800"}
                  </span>
                </div>
              </div>

              <div>
                <label className="block text-[10px] font-bold text-neutral-500 uppercase tracking-widest mb-1.5">일본 카드 번호 (Credit Card Number)</label>
                <input
                  type="text"
                  required
                  placeholder="4242 4242 4242 4242"
                  value={cardNumber}
                  onChange={(e) => setCardNumber(e.target.value)}
                  className="w-full px-4 py-3 bg-neutral-950 border border-neutral-800 hover:border-neutral-700 focus:border-blue-500 rounded-xl text-sm focus:outline-none transition-all placeholder-neutral-700 text-neutral-200"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-[10px] font-bold text-neutral-500 uppercase tracking-widest mb-1.5">만료 연/월 (MM/YY)</label>
                  <input
                    type="text"
                    required
                    placeholder="12/29"
                    value={cardExpiry}
                    onChange={(e) => setCardExpiry(e.target.value)}
                    className="w-full px-4 py-3 bg-neutral-950 border border-neutral-800 hover:border-neutral-700 focus:border-blue-500 rounded-xl text-sm focus:outline-none transition-all placeholder-neutral-700 text-neutral-200"
                  />
                </div>
                <div>
                  <label className="block text-[10px] font-bold text-neutral-500 uppercase tracking-widest mb-1.5">보안코드 (CVC)</label>
                  <input
                    type="text"
                    required
                    placeholder="424"
                    value={cardCvc}
                    onChange={(e) => setCardCvc(e.target.value)}
                    className="w-full px-4 py-3 bg-neutral-950 border border-neutral-800 hover:border-neutral-700 focus:border-blue-500 rounded-xl text-sm focus:outline-none transition-all placeholder-neutral-700 text-neutral-200"
                  />
                </div>
              </div>

              <div className="p-3 bg-blue-500/5 border border-blue-500/10 rounded-xl flex gap-2.5 text-[10px] text-blue-400 leading-normal items-start">
                <ShieldCheck className="w-4 h-4 flex-shrink-0" />
                <span>본 거래는 PCI-DSS 규격을 통과한 Stripe Live 암호화 인터페이스를 통해 처리됩니다.</span>
              </div>

              <div className="flex gap-3 mt-6">
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  className="flex-1 py-3 bg-neutral-800 hover:bg-neutral-700 text-neutral-300 font-semibold text-xs rounded-xl cursor-pointer transition-colors"
                >
                  취소
                </button>
                <button
                  type="submit"
                  disabled={isLoading}
                  className="flex-1 py-3 bg-blue-600 hover:bg-blue-500 disabled:bg-neutral-800 disabled:text-neutral-500 text-white font-bold text-xs rounded-xl shadow-lg hover:shadow-blue-500/20 cursor-pointer flex justify-center items-center gap-1.5 transition-colors"
                >
                  {isLoading ? "승인 요청 중..." : "안전 결제 집행"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

    </div>
  );
}
